"""
spot_check.py — real-world generalization check

train.py's test-set metrics measure performance on held-out rows from the
SAME dataset the model trained on. That doesn't tell you how the model
does on URLs it's never seen the *style* of — which is what actually
matters for a browser extension. This script runs the live inference
pipeline (feature_extraction.py -> model.pkl, the exact same path the
Flask backend uses) against a small, hand-labeled set of real-world URLs
and reports accuracy.

This is NOT a rigorous benchmark (11-40 hand-picked examples, chosen by
one person, isn't a statistically sound test set) — it's a fast, honest
sanity check, and its results are written up candidly in
docs/model_notes.md section 8 rather than hidden or reported as if they
were held-out test accuracy.
"""
import sys

sys.path.insert(0, ".")
from app import predict_url, load_model  # noqa: E402

LEGITIMATE_URLS = [
    "https://www.google.com/search?q=weather+today",
    "https://www.wikipedia.org/",
    "https://en.wikipedia.org/wiki/Phishing",
    "https://github.com/anthropics",
    "https://mail.google.com/mail/u/0/#inbox",
    "https://www.amazon.com/gp/css/order-history",
    "https://www.linkedin.com/in/someone",
    "https://docs.python.org/3/library/functions.html",
    "https://stackoverflow.com/questions/tagged/python",
    "https://www.nytimes.com/section/technology",
]

PHISHING_URLS = [
    "http://paypal-secure-login.verify-account-update.tk/signin/confirm.php?user=victim&session=8237492834",
    "http://192.168.1.1/login.php?user=admin&pass=1234",
    "http://secure-appleid-verify.com-account-locked.info/webapps/login/verify.php?id=837462",
    "http://bit.ly/3xK9zQp/verify-bank-account-now-urgent-action-required",
    "http://amaz0n-account-suspended.security-check.ru/restore/index.php?ref=email",
    "http://www.paypa1-billing-department.com/webapps/verify.html?token=aXNfdGhpc19yZWFsPw",
]


def run():
    load_model()
    correct = 0
    total = 0
    print(f"{'expected':<12}{'got':<12}{'conf':<8}{'url'}")
    print("-" * 100)
    for url in LEGITIMATE_URLS:
        r = predict_url(url)
        ok = r["prediction"] == "legitimate"
        correct += ok
        total += 1
        mark = "OK" if ok else "MISS"
        print(f"{'legitimate':<12}{r['prediction']:<12}{r['confidence']:<8}{mark:<6}{url}")
    for url in PHISHING_URLS:
        r = predict_url(url)
        ok = r["prediction"] == "phishing"
        correct += ok
        total += 1
        mark = "OK" if ok else "MISS"
        print(f"{'phishing':<12}{r['prediction']:<12}{r['confidence']:<8}{mark:<6}{url}")

    print("-" * 100)
    print(f"Spot-check accuracy: {correct}/{total} ({100*correct/total:.0f}%)")
    print("This is a small hand-picked sample, not a statistically valid "
          "benchmark — see docs/model_notes.md section 8 for the honest "
          "read on what this does and doesn't tell you.")


if __name__ == "__main__":
    run()
