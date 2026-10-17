# camera-wifi-autoimport

## Goal

A single-file Python importer (standard library only, Python 3.11+) that moves camera JPEGs from a NAS inbox into a self-hosted Immich library, with duplicate detection via Immich's SHA-1 check, album assignment and retries, for people running Immich on their own NAS. A release is finished when the tests and ruff pass in CI, `scripts/check_public_tree.py` and gitleaks report nothing, and the behaviour has been verified on real hardware as recorded in `docs/verification.md`.

## Environments

Local only for development: `uv run pytest` and `uv run ruff check`; CI (`.github/workflows/ci.yml`) runs Linux and macOS with Python 3.11 to 3.14. Production use is on Olli's Synology NAS with Immich running on the same NAS, where the script runs on a schedule from a private config.

## Manual checks

Before a release, run the importer against a real Immich on the NAS with a photo already in the library and a new photo from the camera: dry run must report `waiting` then `would_duplicate`/`would_create`, the real run must create the album and asset or record the duplicate, and source files must stay in place. Record the result in `docs/verification.md`, and confirm no API key, hostname or private path appears in the public tree or in the log output.
