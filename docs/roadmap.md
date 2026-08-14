# Fortix build roadmap — task checklist

Check items off as you finish them, commit, and push after each milestone
(one commit per milestone, or one per sub-task if you want a denser history).

## M1 — Project scaffolding
- [x] Repo structure (`backend/`, `extension/`, `docs/`)
- [x] README with architecture + roadmap
- [x] `.gitignore`, `requirements.txt`

## M2 — ML classifier
- [x] Pick/download a labeled phishing-vs-legitimate URL dataset
      (Vrbančič et al. 2020, 58,645 URLs)
- [x] Write `backend/model/feature_extraction.py` — lexical/host feature
      extraction from a raw URL string (no network calls needed at
      inference time), 98 features
- [x] Write `backend/model/train.py` — load data, compare 3 model
      families via CV, tune the winner, evaluate on a held-out test set
- [x] Save trained model artifact (`backend/model/model.pkl`, 4.0MB)
- [x] Record accuracy / precision / recall / F1 / ROC-AUC in
      `docs/model_notes.md`, with confusion matrix + ROC + feature
      importance plots

## M3 — Flask backend
- [x] `backend/app.py` with `POST /predict` (takes `{"url": "..."}`,
      returns `{"prediction": ..., "confidence": ..., "source": ...}`)
- [x] Input validation (rejects empty/malformed/oversized input, non-JSON)
- [x] Load model once at startup, not per-request
- [x] Manual test with `curl` (happy path + every error case)
- [x] Found + fixed a feature-encoding bug (dataset uses `-1` sentinels
      for absent URL segments; live extractor used `0`)
- [x] Diagnosed a dataset collection bias (legit class skews bare-domain,
      phishing class skews path-heavy) via subset accuracy analysis;
      retrained on path-present subset with class balancing
- [x] Built `spot_check.py` — real-world URLs run through the live
      pipeline, not just offline test-set metrics
- [x] Added a domain-reputation allowlist layer in front of the ML model
      (mirrors how real anti-phishing products are built); verified it
      can't be bypassed by brand-name-embedded lookalike domains

## M4 — Chrome extension shell
- [ ] `manifest.json` (Manifest V3)
- [ ] `popup.html` + `popup.js` — shows current tab's URL and a
      "Check this page" button
- [ ] `background.js` — service worker, fetches active tab URL
- [ ] Wire popup → background → backend → render verdict

## M5 — Integration + error handling
- [ ] Enable CORS on the Flask side for the extension's origin
- [ ] Handle backend-unreachable / timeout in the popup UI
- [ ] Loading state while waiting on prediction
- [ ] End-to-end manual test against a few known-safe and known-phishy URLs

## M6 — Polish
- [ ] Icons for the extension
- [ ] Screenshots/GIF in README
- [ ] Optional: deploy backend (Render/Railway) so it's not just localhost
- [ ] Final README pass — setup steps someone else could follow
