# Fortix build roadmap — task checklist

Check items off as you finish them, commit, and push after each milestone
(one commit per milestone, or one per sub-task if you want a denser history).

## M1 — Project scaffolding
- [x] Repo structure (`backend/`, `extension/`, `docs/`)
- [x] README with architecture + roadmap
- [x] `.gitignore`, `requirements.txt`

## M2 — ML classifier
- [ ] Pick/download a labeled phishing-vs-legitimate URL dataset
- [ ] Write `backend/model/features.py` — lexical/host feature extraction
      from a raw URL string (no network calls needed at inference time)
- [ ] Write `backend/model/train.py` — load data, extract features, train
      a classifier, print evaluation metrics
- [ ] Save trained model artifact (`backend/model/model.pkl`)
- [ ] Record accuracy / precision / recall in `docs/model_notes.md`

## M3 — Flask backend
- [ ] `backend/app.py` with `POST /predict` (takes `{"url": "..."}`,
      returns `{"prediction": ..., "confidence": ...}`)
- [ ] Input validation (reject empty/malformed input)
- [ ] Load model once at startup, not per-request
- [ ] Manual test with `curl` / Postman

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
