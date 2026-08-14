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
- [ ] **M4 — Chrome extension shell**: manifest v3, popup UI, background
      service worker, calling the backend
- [ ] **M5 — Integration + error handling**: CORS, loading/error states,
      manual end-to-end test pass
- [ ] **M6 — Polish**: README screenshots/gif, packaging, optional
      deployment of the backend

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

Then load `extension/` as an unpacked extension in `chrome://extensions`
(Developer mode → Load unpacked) — once M4 lands.

## Status

Currently at M3. See `docs/roadmap.md` for task-level detail per
milestone and `docs/model_notes.md` for the full ML write-up (dataset,
feature engineering, model comparison, metrics, and — worth reading —
two real bugs found and fixed along the way).
