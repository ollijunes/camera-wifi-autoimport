# Changelog

## 0.1.1

- Permanent verdicts (size limit, JPEG markers, Immich format rejection) are
  reported once and recorded as `rejected`; the file is rechecked only after it
  changes. Earlier every scheduled run failed again on the same file.
- An unreadable inbox subfolder no longer aborts the whole pass. Other files are
  processed and the pass reports one failure per unreadable folder.
- The state identity is now a salted HMAC instead of a plain digest of the
  configuration and key. Existing 0.1.0 state is verified once and upgraded.
- Documented Immich 3.0 as the minimum server version: earlier releases require
  upload fields this importer does not send.
- Removed the internal release-review diary from `docs/`; verification notes
  live in `docs/verification.md`. Added Dependabot for pinned GitHub Actions.

## 0.1.0

- Brand-independent JPEG inbox import into Immich.
- Exact-file duplicate check, album assignment and retry state.
- Source retention, two-pass stability checks and private snapshot uploads.
- Sony A7 IV / Synology setup, camera requirements and troubleshooting.
- Automated tests and secret-scanning CI.
