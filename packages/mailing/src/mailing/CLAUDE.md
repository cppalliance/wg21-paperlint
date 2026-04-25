# mailing - Agent Rules

## What this is

Two narrow modules for getting WG21 paper sources off open-std.org and into a paperstore workspace.

## Invariants

- **`scrape.py` has no storage dependency.** It returns plain dicts. Don't import `paperstore` from `scrape.py` - downstream callers add storage.
- **`download.py` writes through `store.put_source`** and never to a side-channel cache directory. The legacy `.paperlint_cache/` is gone; do not reintroduce it.
- **`requests.get` is the stubbing seam.** Tests monkeypatch the `requests` attribute on `mailing.download`; keep the `import requests` at module level so the seam stays at one location.
- **`source_url` is required.** `download_paper` raises if missing - the URL must come from the authoritative mailing-index row, not be reconstructed locally.
- **`upsert_mailing_index` preserves `added` timestamps** for rows already on disk. The first time we see a paper is information; later refetches must not clobber it.
