"""
app.py — Fortix backend

A small Flask API around the trained phishing-URL classifier. One real
endpoint (`POST /predict`), one health check (`GET /health`).

Design notes:
- The model is loaded ONCE at process startup (`load_model()` runs at
  import time), not per-request — joblib.load on a 4MB file is fast, but
  there's no reason to pay that cost on every single call.
- Feature extraction re-uses `model/feature_extraction.py` — the exact
  same code path used at training time — so there's no drift between how
  a feature was defined during training and how it's computed here.
- Errors are handled explicitly (bad JSON, missing "url" key, empty
  string) rather than letting Flask return a raw 500 with a stack trace.
"""
import os
import sys
import time

import joblib
import pandas as pd
from flask import Flask, jsonify, request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "model"))
from feature_extraction import FEATURE_ORDER, extract_features  # noqa: E402

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model", "model.pkl")

# --- Known-domain allowlist -------------------------------------------------
# Why this exists (see docs/model_notes.md section 8 for the full story):
# this model is trained on a purely lexical/structural feature set, and the
# public dataset's "legitimate" class skews toward short, shallow-path URLs.
# Real legitimate sites with deep content hierarchies (docs, Q&A, wikis —
# e.g. stackoverflow.com/questions/tagged/python) structurally resemble the
# dataset's phishing examples (many slashes, longer paths) more than they
# resemble its legitimate examples, so the model alone false-positives on
# them at a meaningful rate.
#
# This is not a workaround to hide a broken model — it's the standard
# production pattern for this exact problem: real anti-phishing systems
# (Chrome Safe Browsing, corporate email gateways, etc.) layer a domain
# reputation/allowlist check IN FRONT OF ml scoring rather than relying on
# lexical ML alone, precisely because lexical features can't distinguish
# "long path because deep content" from "long path because obfuscation."
#
# Deliberately an EXACT registered-domain match (not substring), so
# "google.com" allowlists "mail.google.com" and "www.google.com" but does
# NOT allowlist "google.com.verify-account.tk" — a classic phishing pattern
# that embeds a real brand name as a subdomain-looking prefix. The model
# still runs on everything not on this short list.
KNOWN_LEGITIMATE_DOMAINS = {
    "google.com", "wikipedia.org", "github.com", "stackoverflow.com",
    "amazon.com", "linkedin.com", "microsoft.com", "apple.com",
    "python.org", "nytimes.com", "wikimedia.org", "mozilla.org",
    "anthropic.com", "cloudflare.com", "youtube.com", "reddit.com",
    "twitter.com", "x.com", "facebook.com", "instagram.com",
}


def registered_domain(host: str) -> str:
    """Best-effort 'last two labels' extraction (example.co.uk style
    multi-part suffixes aren't handled — same simplification noted in
    feature_extraction.py). Good enough for a short, curated allowlist."""
    host = host.split(":")[0].lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host

app = Flask(__name__)

_bundle = None  # populated by load_model()


def load_model():
    global _bundle
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"No model found at {MODEL_PATH}. Run `python model/train.py` "
            f"from the backend/ directory first."
        )
    _bundle = joblib.load(MODEL_PATH)
    app.logger.info(
        f"Loaded model ({_bundle['model_family']}), "
        f"{len(_bundle['feature_order'])} features"
    )


def predict_url(url: str) -> dict:
    """Run the full pipeline for one URL: allowlist check first, then
    (if not allowlisted) feature extraction -> scaling -> model. Returns
    a JSON-serializable result dict."""
    from urllib.parse import urlparse
    check_url = url if "://" in url else "http://" + url
    host = urlparse(check_url).netloc
    if registered_domain(host) in KNOWN_LEGITIMATE_DOMAINS:
        return {
            "url": url,
            "prediction": "legitimate",
            "confidence": 1.0,
            "phishing_probability": 0.0,
            "source": "allowlist",
        }

    raw_features = extract_features(url)
    row = pd.DataFrame([raw_features])[FEATURE_ORDER]

    if _bundle["needs_scaling"]:
        row = _bundle["scaler"].transform(row)

    model = _bundle["model"]
    proba = model.predict_proba(row)[0]
    phishing_probability = float(proba[1])
    prediction = "phishing" if phishing_probability >= 0.5 else "legitimate"

    return {
        "url": url,
        "prediction": prediction,
        "confidence": round(
            phishing_probability if prediction == "phishing"
            else 1 - phishing_probability,
            4,
        ),
        "phishing_probability": round(phishing_probability, 4),
        "source": "ml_model",
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": _bundle is not None,
        "model_family": _bundle["model_family"] if _bundle else None,
    })


@app.route("/predict", methods=["POST"])
def predict():
    t0 = time.time()

    if not request.is_json:
        return jsonify({"error": "Request body must be JSON (Content-Type: application/json)"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Malformed JSON body"}), 400

    url = data.get("url")
    if url is None:
        return jsonify({"error": "Missing required field: 'url'"}), 400
    if not isinstance(url, str) or url.strip() == "":
        return jsonify({"error": "'url' must be a non-empty string"}), 400
    if len(url) > 2048:
        return jsonify({"error": "'url' exceeds max length of 2048 characters"}), 400

    try:
        result = predict_url(url.strip())
    except Exception as e:
        app.logger.exception("Prediction failed")
        return jsonify({"error": f"Prediction failed: {e}"}), 500

    result["inference_time_ms"] = round((time.time() - t0) * 1000, 2)
    return jsonify(result), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found. Available endpoints: GET /health, POST /predict"}), 404


load_model()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
