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

- [ ] **M1 — Project scaffolding** (this commit): repo structure, README,
      requirements, .gitignore
- [ ] **M2 — ML classifier**: dataset, feature extraction, training script,
      saved model + evaluation metrics
- [ ] **M3 — Flask backend**: `/predict` endpoint wrapping the model,
      request/response schema, local testing
- [ ] **M4 — Chrome extension shell**: manifest v3, popup UI, background
      service worker, calling the backend
- [ ] **M5 — Integration + error handling**: CORS, loading/error states,
      manual end-to-end test pass
- [ ] **M6 — Polish**: README screenshots/gif, packaging, optional
      deployment of the backend

## Local setup (filled in as each milestone lands)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then load `extension/` as an unpacked extension in `chrome://extensions`
(Developer mode → Load unpacked).

## Status

Currently at M1. See `docs/roadmap.md` for task-level detail per milestone.
