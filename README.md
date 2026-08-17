# Fortix — ML-Based Phishing URL Detector (Chrome Extension)

Fortix is a Chrome extension that checks the URL of the page you're on (or a
URL you paste in) against a machine-learning model served by a small Flask
backend, and returns a real-time phishing / safe prediction.

## Architecture

```
extension/  → Chrome extension (Manifest V3): popup UI + background service
              worker that calls the backend on the active tab's URL
backend/    → Flask API that loads a trained scikit-learn model and exposes
              POST /predict
backend/model/ → feature extraction + training script + saved model artifact
```

Flow: user opens a tab → extension grabs the URL → sends it to
`POST /predict` on the local Flask server → server extracts lexical/host
features from the URL → runs the ML classifier → returns
`{ "prediction": "phishing" | "safe", "confidence": 0.93 }` → popup renders
the verdict.

## Build roadmap (matches the commit history)

- [x] **M1 — Project scaffolding**: repo structure, README,
      requirements, .gitignore
- [x] **M2 — ML classifier**: dataset, feature extraction, training script,
      saved model + evaluation metrics — **90.2% accuracy, 0.90 F1,
      0.962 ROC-AUC**, 98 URL-lexical features, 4MB Random Forest.
      Full write-up: `docs/model_notes.md`.
- [x] **M3 — Flask backend**: `POST /predict` + `GET /health`, input
      validation, and a hybrid pipeline (domain allowlist + ML model).
      Along the way: found and fixed a feature-encoding bug, diagnosed a
      dataset collection bias, retrained to partially correct it, and
      added a domain-reputation layer to handle what retraining alone
      couldn't fix. Full diagnostic writeup: `docs/model_notes.md` §8.
- [x] **M4 — Chrome extension shell**: Manifest V3, popup UI, background
      service worker (message-passing architecture, not a direct fetch
      from the popup — keeps all backend calls in one place)
- [x] **M5 — Integration + error handling**: CORS enabled and verified
      against a real `chrome-extension://` origin, backend-down and
      timeout states handled in the popup, non-http(s) tabs handled,
      `spot_check.py` re-run against the live server end-to-end
- [x] **M6 — Polish**: icons, README setup instructions. Screenshots and
      backend deployment left as optional follow-ups (see roadmap.md)

## Local setup

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Server runs at `http://127.0.0.1:5000`. Try it:

```bash
curl -X POST http://127.0.0.1:5000/predict \
  -H "Content-Type: application/json" \
  -d '{"url": "http://paypal-secure-login.verify-account.tk/signin.php"}'
```

Then load `extension/` as an unpacked extension:

1. Go to `chrome://extensions`
2. Turn on **Developer mode** (top-right toggle)
3. Click **Load unpacked**, select the `extension/` folder
4. Pin the Fortix icon, visit any page, click it, click **Check this page**

The backend must be running (`python app.py`) for the extension to work —
it only talks to `127.0.0.1:5000`, nothing external.

## Status

Everything through M6 is built: trained model, Flask API, and a working
Chrome extension. See `docs/roadmap.md` for task-level detail per
milestone and `docs/model_notes.md` for the full ML write-up (dataset,
feature engineering, model comparison, metrics, and — worth reading —
two real bugs found and fixed along the way).

Two things intentionally left open, noted rather than hidden:
- No README screenshots yet (needs a real Chrome load on your end)
- Backend is localhost-only; deploying it (Render/Railway free tier)
  would make this shareable as a live link instead of "clone the repo"
