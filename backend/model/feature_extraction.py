"""
feature_extraction.py

Turns a raw URL string into the numeric feature vector the Fortix model
expects.

Design decision: every feature here is computable from the URL string
ALONE — no DNS lookup, WHOIS query, SSL handshake, or "is this indexed by
Google" check. The public dataset this model was trained on (Vrbancic et
al., "Datasets for Phishing Websites Detection", Data in Brief, 2020)
ships 111 features, but ~13 of them (time_response, domain_spf, asn_ip,
time_domain_activation, time_domain_expiration, qty_ip_resolved,
qty_nameservers, qty_mx_servers, ttl_hostname, tls_ssl_certificate,
qty_redirects, url_google_index, domain_google_index) require a live
network round-trip to compute.

For a browser extension that has to return a verdict while someone is
mid-navigation, a feature that takes 200ms+ of DNS/WHOIS latency per
request is a non-starter — and it also means the model would silently
degrade to "unknown" the moment the backend has no network access. So
this project deliberately trains on the ~98-feature lexical/structural
subset only. That's a real accuracy/latency trade-off, not an oversight —
see docs/model_notes.md for the measured cost of dropping those features.

Known simplification: TLD extraction here uses "last dot-separated label"
(e.g. "co" out of "example.co.uk" rather than "co.uk"). A production
system would use the public suffix list (e.g. the `tldextract` package)
for exact TLD boundaries; this project notes it as a limitation rather
than pulling in a library that needs a network fetch of the suffix list
on first run.
"""
import re
from urllib.parse import urlparse

PUNCT_CHARS = {
    "dot": ".", "hyphen": "-", "underline": "_", "slash": "/",
    "questionmark": "?", "equal": "=", "at": "@", "and": "&",
    "exclamation": "!", "space": " ", "tilde": "~", "comma": ",",
    "plus": "+", "asterisk": "*", "hashtag": "#", "dollar": "$",
    "percent": "%",
}

VOWELS = set("aeiouAEIOU")

KNOWN_SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "shorte.st", "tiny.cc", "cutt.ly", "rebrand.ly",
    "shorturl.at", "bl.ink",
}

IP_PATTERN = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?$"
)
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _punct_counts(segment: str, prefix: str) -> dict:
    return {f"qty_{name}_{prefix}": segment.count(ch) for name, ch in PUNCT_CHARS.items()}


def _split_url(url: str):
    """Break a URL into domain / directory / file / params segments."""
    if "://" not in url:
        url = "http://" + url  # urlparse needs a scheme to find netloc correctly

    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path or ""
    query = parsed.query or ""

    segments = [s for s in path.split("/") if s != ""]
    if segments and "." in segments[-1]:
        file_part = segments[-1]
        directory = "/".join(segments[:-1])
    else:
        file_part = ""
        directory = "/".join(segments)

    return domain, directory, file_part, query


def extract_features(url: str) -> dict:
    """Return the full feature dict for one URL. Column order matches
    FEATURE_ORDER below; callers should reindex with FEATURE_ORDER before
    handing the vector to the model."""
    url = url.strip()
    domain, directory, file_part, params = _split_url(url)

    features = {}
    features.update(_punct_counts(url, "url"))
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    features["qty_tld_url"] = len(tld)
    features["length_url"] = len(url)

    features.update(_punct_counts(domain, "domain"))
    features["qty_vowels_domain"] = sum(1 for c in domain if c in VOWELS)
    features["domain_length"] = len(domain)
    host = domain.split(":")[0]
    features["domain_in_ip"] = int(bool(IP_PATTERN.match(host)))
    features["server_client_domain"] = int(
        "server" in domain.lower() or "client" in domain.lower()
    )

    features.update(_punct_counts(directory, "directory"))
    features["directory_length"] = len(directory)

    features.update(_punct_counts(file_part, "file"))
    features["file_length"] = len(file_part)

    features.update(_punct_counts(params, "params"))
    features["params_length"] = len(params)
    features["tld_present_params"] = int(bool(tld) and tld in params)
    features["qty_params"] = 0 if params == "" else len(params.split("&"))

    features["email_in_url"] = int(bool(EMAIL_PATTERN.search(url)))
    features["url_shortened"] = int(host.lower() in KNOWN_SHORTENERS)

    return features


# Exact column order the model was trained on (mirrors the dataset schema,
# minus the 13 network-dependent columns). Populated by train.py after
# feature selection and re-exported here so the backend imports one source
# of truth. Kept as a plain list (not derived at import time) so a missing
# training run doesn't break imports.
FEATURE_ORDER = [
    "qty_dot_url", "qty_hyphen_url", "qty_underline_url", "qty_slash_url",
    "qty_questionmark_url", "qty_equal_url", "qty_at_url", "qty_and_url",
    "qty_exclamation_url", "qty_space_url", "qty_tilde_url", "qty_comma_url",
    "qty_plus_url", "qty_asterisk_url", "qty_hashtag_url", "qty_dollar_url",
    "qty_percent_url", "qty_tld_url", "length_url",
    "qty_dot_domain", "qty_hyphen_domain", "qty_underline_domain",
    "qty_slash_domain", "qty_questionmark_domain", "qty_equal_domain",
    "qty_at_domain", "qty_and_domain", "qty_exclamation_domain",
    "qty_space_domain", "qty_tilde_domain", "qty_comma_domain",
    "qty_plus_domain", "qty_asterisk_domain", "qty_hashtag_domain",
    "qty_dollar_domain", "qty_percent_domain", "qty_vowels_domain",
    "domain_length", "domain_in_ip", "server_client_domain",
    "qty_dot_directory", "qty_hyphen_directory", "qty_underline_directory",
    "qty_slash_directory", "qty_questionmark_directory", "qty_equal_directory",
    "qty_at_directory", "qty_and_directory", "qty_exclamation_directory",
    "qty_space_directory", "qty_tilde_directory", "qty_comma_directory",
    "qty_plus_directory", "qty_asterisk_directory", "qty_hashtag_directory",
    "qty_dollar_directory", "qty_percent_directory", "directory_length",
    "qty_dot_file", "qty_hyphen_file", "qty_underline_file", "qty_slash_file",
    "qty_questionmark_file", "qty_equal_file", "qty_at_file", "qty_and_file",
    "qty_exclamation_file", "qty_space_file", "qty_tilde_file",
    "qty_comma_file", "qty_plus_file", "qty_asterisk_file",
    "qty_hashtag_file", "qty_dollar_file", "qty_percent_file", "file_length",
    "qty_dot_params", "qty_hyphen_params", "qty_underline_params",
    "qty_slash_params", "qty_questionmark_params", "qty_equal_params",
    "qty_at_params", "qty_and_params", "qty_exclamation_params",
    "qty_space_params", "qty_tilde_params", "qty_comma_params",
    "qty_plus_params", "qty_asterisk_params", "qty_hashtag_params",
    "qty_dollar_params", "qty_percent_params", "params_length",
    "tld_present_params", "qty_params", "email_in_url", "url_shortened",
]


if __name__ == "__main__":
    # quick manual sanity check
    samples = [
        "https://www.google.com/search?q=test",
        "http://192.168.1.1/login.php?user=admin&pass=1234",
        "http://paypal-secure-login.verify-account.tk/update.html",
    ]
    for s in samples:
        f = extract_features(s)
        print(s)
        print({k: f[k] for k in list(f)[:8]}, "...")
