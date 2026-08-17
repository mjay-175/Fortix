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
- [x] `manifest.json` (Manifest V3)
- [x] `popup.html` + `popup.css` + `popup.js` — shows current tab's URL
      and a "Check this page" button
- [x] `background.js` — service worker owning all backend communication,
      with a 5s timeout via AbortController
- [x] Wire popup → background (message passing) → backend → render verdict
- [x] Icons (16/48/128px)

## M5 — Integration + error handling
- [x] Enable CORS on the Flask side (`flask-cors`) for the extension's
      origin, verified with a simulated `chrome-extension://` origin header
- [x] Handle backend-unreachable / timeout in the popup UI (shown as an
      inline error box with a specific "is app.py running?" hint)
- [x] Loading state (spinner + disabled button) while waiting on prediction
- [x] Non-http(s) tabs (chrome://, about:) handled — check button disabled
      with an explanation instead of erroring
- [x] End-to-end manual test: `spot_check.py` re-run against the live
      server (not just the offline pipeline) — still 16/16
- [x] Confirmed exact failure mode when backend is down (connection
      refused) matches what `background.js`'s try/catch expects

## M6 — Polish
- [x] Icons for the extension
- [ ] Screenshots/GIF in README (needs a real Chrome load — do this once
      you've loaded the unpacked extension yourself)
- [ ] Optional: deploy backend (Render/Railway) so it's not just localhost
- [x] Final README pass — setup steps someone else could follow
