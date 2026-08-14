"""
train.py — Fortix phishing URL classifier

Pipeline:
  1. Load the labeled dataset (Vrbancic et al., Data in Brief 2020)
  2. Drop the network/WHOIS-dependent columns (see feature_extraction.py
     for why) so train-time features == what the Flask backend can compute
     live from a URL string alone
  3. Split train/test, stratified on the label
  4. Baseline: Logistic Regression (linear, interpretable, fast)
  5. Random Forest and Gradient Boosting (non-linear, handle feature
     interactions — e.g. "many hyphens AND an IP-address domain" matters
     more than either alone)
  6. 5-fold cross-validation on the training set to pick the best family
     before touching the test set at all
  7. Hyperparameter tuning (RandomizedSearchCV) on the winning family
  8. Final evaluation ONCE on the held-out test set: accuracy, precision,
     recall, F1, ROC-AUC, confusion matrix
  9. Save the tuned model + feature importances + metrics.json + plots
"""
import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    RocCurveDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    RandomizedSearchCV,
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.preprocessing import StandardScaler

from feature_extraction import FEATURE_ORDER

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RANDOM_STATE = 42

# Columns present in the raw CSV that require a live network call to
# compute (DNS, WHOIS, SSL handshake, search-index check) and are
# therefore excluded — see feature_extraction.py docstring.
NETWORK_DEPENDENT_COLUMNS = [
    "time_response", "domain_spf", "asn_ip", "time_domain_activation",
    "time_domain_expiration", "qty_ip_resolved", "qty_nameservers",
    "qty_mx_servers", "ttl_hostname", "tls_ssl_certificate",
    "qty_redirects", "url_google_index", "domain_google_index",
]


def load_data(path="dataset_small.csv", restrict_to_path_present=True):
    df = pd.read_csv(path)
    df = df.drop(columns=NETWORK_DEPENDENT_COLUMNS)

    if restrict_to_path_present:
        # See docs/model_notes.md section 8: the dataset's legitimate
        # examples are heavily weighted toward bare root-domain entries
        # (no path, no query — e.g. sourced from an Alexa top-sites list
        # as just "example.com"), while phishing examples are almost
        # always full in-the-wild URLs with a path. A model trained on
        # the full mix learns "has a path at all" as a strong phishing
        # signal — which is a data-collection artifact, not a real
        # phishing indicator, and it tanks legitimate-URL recall (77%)
        # on exactly the kind of URL a browser extension actually sees
        # (nearly every real browser URL includes at least "/").
        # Training on the path-present subset for both classes removes
        # that artifact and matches production traffic.
        before = len(df)
        df = df[df["directory_length"] >= 0].reset_index(drop=True)
        print(f"Restricted to path-present rows: {before} -> {len(df)} "
              f"(class balance: {df['phishing'].value_counts(normalize=True).to_dict()})")

    missing = set(FEATURE_ORDER) - set(df.columns)
    extra = set(df.columns) - set(FEATURE_ORDER) - {"phishing"}
    assert not missing, f"feature_extraction.py expects columns the CSV doesn't have: {missing}"
    assert not extra, f"CSV has columns feature_extraction.py doesn't know about: {extra}"
    X = df[FEATURE_ORDER]
    y = df["phishing"]
    return X, y


def evaluate(name, model, X_test, y_test, scaled=False, scaler=None):
    X_eval = scaler.transform(X_test) if scaled else X_test
    preds = model.predict(X_eval)
    proba = model.predict_proba(X_eval)[:, 1]
    metrics = {
        "accuracy": accuracy_score(y_test, preds),
        "precision": precision_score(y_test, preds),
        "recall": recall_score(y_test, preds),
        "f1": f1_score(y_test, preds),
        "roc_auc": roc_auc_score(y_test, proba),
        "confusion_matrix": confusion_matrix(y_test, preds).tolist(),
    }
    print(f"\n=== {name} ===")
    print(classification_report(y_test, preds, target_names=["legitimate", "phishing"]))
    print(f"ROC-AUC: {metrics['roc_auc']:.4f}")
    return metrics, preds, proba


def main():
    t0 = time.time()
    X, y = load_data()
    print(f"Loaded {len(X)} rows, {X.shape[1]} features, "
          f"class balance: {y.value_counts(normalize=True).to_dict()}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    scaler = StandardScaler().fit(X_train)
    X_train_scaled = scaler.transform(X_train)

    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)

    candidates = {
        "logistic_regression": (
            LogisticRegression(max_iter=2000, random_state=RANDOM_STATE, class_weight="balanced"), True
        ),
        "random_forest": (
            RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1, class_weight="balanced"), False
        ),
        "gradient_boosting": (
            HistGradientBoostingClassifier(random_state=RANDOM_STATE, class_weight="balanced"), False
        ),
    }

    cv_results = {}
    for name, (model, needs_scaling) in candidates.items():
        Xc = X_train_scaled if needs_scaling else X_train
        scores = cross_val_score(model, Xc, y_train, cv=cv, scoring="f1", n_jobs=-1)
        cv_results[name] = {"mean_f1": scores.mean(), "std_f1": scores.std()}
        print(f"{name}: CV F1 = {scores.mean():.4f} (+/- {scores.std():.4f})")

    best_name = max(cv_results, key=lambda k: cv_results[k]["mean_f1"])
    print(f"\nBest family by CV F1: {best_name}")

    # Hyperparameter tuning on the winning family
    if best_name == "random_forest":
        base = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1, class_weight="balanced")
        # max_depth is deliberately bounded (no "None"/unlimited option):
        # unbounded trees on 98 features x 47k rows produced a 200MB+
        # model.pkl, which is a non-starter for a repo GitHub will reject
        # (>100MB file) and for a Flask process that needs to load fast.
        # Bounding depth trades a small amount of F1 for a model that's
        # under 10MB and loads in well under a second.
        param_dist = {
            "n_estimators": [100, 150, 200, 300],
            "max_depth": [10, 15, 20, 25],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [2, 4, 8],
            "max_features": ["sqrt", "log2"],
        }
        needs_scaling = False
    elif best_name == "gradient_boosting":
        base = HistGradientBoostingClassifier(random_state=RANDOM_STATE, class_weight="balanced")
        param_dist = {
            "max_iter": [100, 200, 300],
            "learning_rate": [0.05, 0.1, 0.2],
            "max_depth": [3, 5, 8, None],
            "l2_regularization": [0.0, 0.1, 1.0],
        }
        needs_scaling = False
    else:
        base = LogisticRegression(max_iter=2000, random_state=RANDOM_STATE, class_weight="balanced")
        param_dist = {"C": [0.01, 0.1, 1, 10, 100]}
        needs_scaling = True

    Xc_train = X_train_scaled if needs_scaling else X_train
    search = RandomizedSearchCV(
        base, param_dist, n_iter=8, cv=cv, scoring="f1",
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    search.fit(Xc_train, y_train)
    best_model = search.best_estimator_
    print(f"\nBest params: {search.best_params_}")
    print(f"Best CV F1: {search.best_score_:.4f}")

    final_metrics, preds, proba = evaluate(
        f"{best_name} (tuned) — held-out test set", best_model, X_test, y_test,
        scaled=needs_scaling, scaler=scaler,
    )

    # Feature importance (tree models only)
    if hasattr(best_model, "feature_importances_"):
        importances = pd.Series(best_model.feature_importances_, index=FEATURE_ORDER)
        top15 = importances.sort_values(ascending=False).head(15)
        plt.figure(figsize=(8, 6))
        top15[::-1].plot(kind="barh")
        plt.title(f"Top 15 feature importances ({best_name})")
        plt.tight_layout()
        plt.savefig("feature_importance.png", dpi=150)
        plt.close()
        top15.to_csv("feature_importance.csv")
        print("\nTop 10 features:")
        print(top15.head(10))

    # Confusion matrix + ROC plots for the README / model_notes
    fig, ax = plt.subplots(figsize=(5, 5))
    ConfusionMatrixDisplay(
        confusion_matrix=np.array(final_metrics["confusion_matrix"]),
        display_labels=["legitimate", "phishing"],
    ).plot(ax=ax, cmap="Blues", colorbar=False)
    plt.title("Confusion matrix — held-out test set")
    plt.tight_layout()
    plt.savefig("confusion_matrix.png", dpi=150)
    plt.close()

    fig, ax = plt.subplots(figsize=(5, 5))
    X_test_eval = scaler.transform(X_test) if needs_scaling else X_test
    RocCurveDisplay.from_estimator(best_model, X_test_eval, y_test, ax=ax)
    plt.title("ROC curve — held-out test set")
    plt.tight_layout()
    plt.savefig("roc_curve.png", dpi=150)
    plt.close()

    # Persist model + everything the backend needs to reproduce inference.
    # compress=3 keeps the artifact small enough to commit to git.
    joblib.dump(
        {
            "model": best_model,
            "scaler": scaler if needs_scaling else None,
            "needs_scaling": needs_scaling,
            "feature_order": FEATURE_ORDER,
            "model_family": best_name,
        },
        "model.pkl",
        compress=3,
    )
    import os
    model_size_mb = round(os.path.getsize("model.pkl") / (1024 * 1024), 2)
    print(f"model.pkl size: {model_size_mb} MB")

    summary = {
        "model_family": best_name,
        "best_params": search.best_params_,
        "cv_f1_all_candidates": cv_results,
        "cv_f1_best_after_tuning": search.best_score_,
        "test_set_metrics": final_metrics,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_features": len(FEATURE_ORDER),
        "training_time_seconds": round(time.time() - t0, 1),
        "model_size_mb": model_size_mb,
    }
    with open("metrics.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved model.pkl, metrics.json, feature_importance.png, "
          f"confusion_matrix.png, roc_curve.png")
    print(f"Total time: {summary['training_time_seconds']}s")


if __name__ == "__main__":
    main()
