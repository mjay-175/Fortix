# Fortix — model notes

This is the write-up of everything the classifier does and why, in the
order the actual decisions were made — including two real bugs found
along the way and one limitation that's still open. Useful as interview
prep: each section is a question someone could reasonably ask, and
section 8 in particular is worth reading closely — it's the most
interesting part of this project, not the part to skip past.

## 1. Dataset

**Source**: Vrbančič, Jr. Fister, Podgorelec — *"Datasets for Phishing
Websites Detection"*, Data in Brief, Vol. 33, 2020.
DOI: [10.1016/j.dib.2020.106438](http://dx.doi.org/10.1016/j.dib.2020.106438)
Mirror: [github.com/GregaVrbancic/Phishing-Dataset](https://github.com/GregaVrbancic/Phishing-Dataset)

- `dataset_small.csv`: 58,645 URLs, 111 pre-extracted features + a binary
  `phishing` label.
- Class balance: 52.3% phishing / 47.7% legitimate overall.
- The dataset ships pre-computed features, not raw URL strings — no
  extractor source code is published either. That matters a lot for
  section 2 and section 8 below: there's no ground truth to diff against,
  only the feature values themselves to reverse-engineer from.

## 2. Feature selection — why 98 of the 111 columns

The raw dataset includes 13 features that require a **live network call**
to compute: DNS lookups (`qty_nameservers`, `qty_mx_servers`,
`ttl_hostname`, `qty_ip_resolved`), WHOIS queries (`time_domain_activation`,
`time_domain_expiration`), an SSL handshake (`tls_ssl_certificate`), a
search-engine index check (`url_google_index`, `domain_google_index`), and
a few others (`time_response`, `domain_spf`, `asn_ip`, `qty_redirects`).

Those columns were dropped. Reasoning:

- **Latency**: a browser extension answering "is this page safe" needs to
  respond in well under a second. A WHOIS lookup alone can take 200ms–2s.
- **Availability**: if the backend (or the user's network) can't reach an
  external DNS/WHOIS service, a model that depends on those features
  degrades to missing data instead of just working.
- **Consistency**: it also means the *exact same* feature-extraction code
  (`backend/model/feature_extraction.py`) runs at both training time and
  inference time — critical, given what section 8 describes.

That leaves 98 features, all derivable from the URL string alone:
punctuation counts (dots, hyphens, slashes, etc.) broken out by URL
segment (full URL / domain / directory / filename / query params),
segment lengths, whether the domain is a raw IP address, vowel count in
the domain, whether the domain matches a known URL-shortener, whether an
email address appears in the URL, and a few more — full list in
`feature_extraction.py`.

**Known simplification**: TLD length is computed as "characters after the
last dot" (e.g. `co` from `example.co.uk`, not `co.uk`). A fully correct
implementation would use the public suffix list (e.g. the `tldextract`
package), but that requires a network fetch of the suffix list on first
run — which would reintroduce the exact dependency this section is trying
to avoid. Documented as a limitation rather than silently glossed over.

## 3. Model comparison

Three model families, compared with 3-fold stratified cross-validation on
the training split (80/20 train/test split, stratified on the label,
`random_state=42` throughout for reproducibility) — **before** touching
the test set, so the family choice itself isn't test-set-fitted:

| Model | CV F1 |
|---|---|
| Logistic Regression (baseline) | 0.871 |
| Gradient Boosting (HistGradientBoosting) | 0.903 |
| **Random Forest** | **0.910** |

Random Forest won. That's consistent with the feature set: most of these
are simple counts and lengths, and phishing patterns tend to show up as
*combinations* of them ("long path AND many dots AND a hyphenated
domain") rather than one feature crossing a threshold — the kind of
interaction tree ensembles pick up and a single linear boundary
(logistic regression) can't.

## 4. Hyperparameter tuning

`RandomizedSearchCV` (8 iterations, 3-fold CV, scoring on F1) over
`n_estimators`, `max_depth`, `min_samples_split`, `min_samples_leaf`,
`max_features`.

**Trade-off worth calling out explicitly**: the first tuning pass allowed
unbounded tree depth (`max_depth=None`) and that config won on CV F1 —
but it produced a 201MB model file. That's over GitHub's 100MB hard
file-size limit, and it's slow to deserialize on every Flask process
start. Depth was bounded to `[10, 15, 20, 25]` and the search re-run.
Final model: **~4.2MB**, loads in well under a second, at a small cost in
F1. For a real-time extension backend, that's the right trade.

## 5. Final metrics (held-out test set, never touched during
   model/hyperparameter selection)

These are from the **corrected** training run described in section 8
(trained on the path-present subset, class-weight balanced) — not the
first pass, which is explicitly superseded because it was measuring
something misleading. See section 8 for why.

| Metric | Score |
|---|---|
| Accuracy | 0.861 |
| Precision (phishing) | 0.95 |
| Recall (phishing) | 0.86 |
| Precision (legitimate) | 0.70 |
| Recall (legitimate) | 0.87 |
| ROC-AUC | 0.936 |

Confusion matrix, ROC curve, and the top-15 feature importance chart are
saved as PNGs in `backend/model/` (regenerated by `train.py`).

**Top features by importance**: `directory_length`, `length_url`,
`qty_slash_url`, `qty_slash_directory`, `qty_dot_domain` — overall URL
length and path depth dominate. Consistent with a well-known phishing
pattern (attackers pad URLs with long, nested paths to push the real,
suspicious domain out of view) — but see section 8 for why this same
signal is also the model's biggest weakness.

Note this is a **lower** headline accuracy than the first training pass
(90.2%). That's not a regression — the first number was inflated by
easy examples, explained next.

## 6. Reproducing this

```bash
cd backend/model
python train.py
```

Regenerates `model.pkl`, `metrics.json`, and all three plots from
`dataset_small.csv`. Takes about a minute on a single CPU core. To spot-
check the live inference pipeline (not just the offline test-set
metrics) against a small hand-labeled set of real URLs:

```bash
cd backend
python spot_check.py
```

## 7. Simplifications and known scope boundaries

- **No raw-URL ground truth for the CSV features.** The dataset ships
  pre-extracted features, not the original URLs, and publishes no
  extractor source — `feature_extraction.py` was reverse-engineered from
  the feature *distributions themselves* (see section 8). Cross-checked
  against dozens of real URLs but not against the authors' original code,
  because that code isn't public.
- **Purely lexical/structural — no content or reputation signal.** A
  freshly-registered domain with a short, clean-looking URL can slip
  past this model; it has no notion of domain age, hosting reputation, or
  page content. Section 8 is the concrete story of where this scope
  boundary actually bites.
- **Static snapshot.** Phishing URL patterns shift over time; this model
  reflects the 2020 dataset's snapshot and would need periodic retraining
  in a real deployment.

## 8. The interesting part: two bugs and one dataset-bias finding

This section is the actual diagnostic trail from building this, kept
in order, because "I found a bug via distributional analysis, root-
caused it, and made an explicit trade-off" is a more useful thing to be
able to talk through than a model that just worked on the first try.

### 8a. Bug 1 — the sentinel-value bug (found via a false positive)

First test of the live `/predict` endpoint: `https://www.google.com` came
back "phishing" at 64% confidence. That's a red flag, not noise.

Root cause: the dataset encodes "this URL has no directory / no file /
no query params" as the literal value **`-1`** across every feature tied
to that segment — not `0`. My first version of `feature_extraction.py`
returned `0` for an absent segment (e.g. "zero dots in a directory that
doesn't exist"), which reads to the model as "this segment exists and is
simple" rather than "this segment doesn't exist" — two very different
signals it had learned to treat differently.

Found by comparing per-class feature means directly against the raw
CSV (`directory_length.min() == -1`, and every `qty_X_directory` column
had the same 17,507 negative rows), then reverse-engineering the actual
split rule empirically since no extractor source is public: directory =
path up to and including the last `/`; file = everything after it; both
flip to the `-1` sentinel only when the path has no `/` at all. Verified
against the CSV's exact value distribution (min directory length when
present, whether directory/file absence always co-occur, etc.) before
trusting the fix. Fixed in `feature_extraction.py`; no retraining needed
since the bug was only in the live inference path, not in the CSV the
model trained on.

### 8b. Bug fixed, but legitimate URLs were still flagged

After the sentinel fix, `google.com/search?q=weather` and several other
clearly-legitimate URLs were *still* scoring above 50% phishing. Time to
check whether the model itself, not just my feature extraction, had a
problem.

Measured accuracy separately on two subsets of the training data:

| Subset | Legit precision | Legit recall |
|---|---|---|
| URLs with **no** path (bare domain) | 0.96 | 1.00 |
| URLs **with** a path (realistic browsing) | 0.81 | 0.77 |

The 90.2% headline accuracy from the first training run was almost
entirely propped up by the bare-domain subset — which is the easy case
and, per the dataset's `directory_length == -1` counts, is **60% of the
"legitimate" class but only 2.4% of the "phishing" class**. In other
words: the dataset's legitimate examples are disproportionately bare
root-domain listings (consistent with being sourced from a top-sites
list), while its phishing examples are almost always full URLs with a
path (consistent with being sourced from PhishTank report links). The
model partly learned "has a path" as a proxy for phishing — a data-
collection artifact, not a real signal — and a browser extension will
see a URL *with* a path on nearly every real page view.

**Fix**: retrained on the path-present subset only (41,138 rows, with
`class_weight="balanced"` since that subset skews 73% phishing / 27%
legitimate once the easy bare-domain rows are removed). Legitimate
recall on realistic URLs improved from 77% to 87%. This is the run
section 5's metrics come from.

### 8c. Retraining helped, but didn't fully close the gap

Built `spot_check.py` — 10 real legitimate URLs (Google, Wikipedia,
GitHub, Amazon, LinkedIn, Stack Overflow, Python docs, NYT, ...) and 6
realistic phishing URLs — and ran them through the actual live pipeline.

Result: **100% recall on phishing** (all 6 caught), but only **1 of 10**
legitimate URLs correctly classified. The ones that failed had something
in common: multi-segment content paths — `stackoverflow.com/questions/
tagged/python`, `docs.python.org/3/library/functions.html`. Checked their
feature values against the class-conditional means directly: a URL like
Stack Overflow's has `qty_slash_directory=3`, closer to this dataset's
phishing mean (3.09) than its legitimate mean (1.64), purely because
legitimate sites with deep content hierarchies structurally resemble
this dataset's phishing examples more than they resemble its narrow,
shallow-path "legitimate" class. More retraining on the same dataset
won't fix this — the legitimate class itself doesn't contain enough
path-depth diversity to teach the model the difference.

This is a known, published limitation of purely lexical URL classifiers,
not a modeling mistake: lexical features alone can't reliably tell "long
path because deep content" from "long path because obfuscation."

**Mitigation, not a cover-up**: added a small exact-match domain
allowlist (`KNOWN_LEGITIMATE_DOMAINS` in `app.py`) that short-circuits
the ML call for ~20 well-known domains, checked against the exact
registered domain (last two labels of the host) — so `google.com`
allowlists `mail.google.com` and `www.google.com` but explicitly does
**not** allowlist `google.com.verify-account.tk`, a classic phishing
pattern that embeds a real brand name as a fake subdomain. Verified this
directly: `google.com.verify-account-security.tk`,
`paypal.com.confirm-billing.ru`, and `accounts-google.com` are all still
correctly flagged as phishing by the ML model, since none match the
allowlist. This mirrors how real anti-phishing products are actually
built — Chrome Safe Browsing and similar tools layer reputation/allow-
lists in front of ML scoring rather than relying on lexical ML alone —
so this isn't a hack to make the demo look better, it's the standard
production pattern for exactly this failure mode.

With the allowlist layer, `spot_check.py` goes to 16/16. Worth being
precise about what that number does and doesn't mean: it proves the
allowlist works and isn't naively bypassable, not that the underlying
model generalizes well to arbitrary legitimate URLs outside that list.
Any legitimate site with a deep content path that ISN'T on the allowlist
will still hit the same false-positive risk documented in 8c.

**What a real fix would look like**: expand the allowlist by data instead
of by hand (e.g. cross-reference a top-10k domains list), or better,
retrain with a legitimate-class dataset that actually includes deep
content URLs (blogs, docs sites, forums) rather than mostly homepages —
the dataset used here just doesn't have that diversity to learn from.
