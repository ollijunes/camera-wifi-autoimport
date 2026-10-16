# Release verification

The public importer is a rewrite of an existing private Sony A7 IV / Synology
workflow. Verification of that earlier workflow does not substitute for testing
a release on physical hardware.

## v0.1.1

- 60 automated tests pass locally on macOS with Python 3.12; CI runs Linux and
  macOS with Python 3.11 to 3.14.
- Statement coverage: 93% for `camera_import.py`; the CI minimum is 85%.
- Ruff lint and format checks pass. Gitleaks and `scripts/check_public_tree.py`
  report no findings across the whole Git history.
- New tests cover one-time reporting of permanent rejections, retry of trashed
  duplicates, an unreadable inbox subfolder, and verification plus upgrade of a
  0.1.0 state database.
- The JPEG start/end marker check was compared with the private workflow that
  imported about 1,300 Sony A7 IV JPEGs using the same check; no Sony file was
  rejected by it.

## v0.1.0

- 53 automated tests passed locally on macOS with Python 3.11 and 3.12.
- Statement coverage: 92.57% for `camera_import.py`.
- Ruff lint and format checks passed; Gitleaks found no findings.
- An independent review on 15 October 2026 of commit `075b2c1` found no blocking
  code defect and confirmed source retention, album-confirmed completion, key
  handling, redirect/proxy refusal and symlink handling in code and tests.

## API contract

Request/response contracts were checked against Immich's
[v3.3.1 OpenAPI specification](https://github.com/immich-app/immich/blob/v3.3.1/open-api/immich-openapi-specs.json)
(tag commit `db6e11ecc851228aec9c525abb0ee026d1f5055e`). The required permissions
are `asset.upload`, `album.read`, `album.create` and `albumAsset.create`.
Immich 3.0.0 is the first release whose upload endpoint does not require
`deviceAssetId` and `deviceId`; 2.x and older answer HTTP 400.

## Not verified

The test suite does not start Immich itself, decode the generated JPEG marker
fixtures, connect to cameras, or validate DSM installation steps. Test HTTP
requests exercise multipart uploads, duplicate checks, album creation and
membership, errors and redirect rejection against a loopback server only.

End-to-end verification of the public importer on a camera/NAS is still
pending. See the [whole-path verification steps](synology.md#6-verify-the-whole-path).
The current GitHub CI result is shown by the README badge and the
[Actions runs](https://github.com/ollijunes/camera-wifi-autoimport/actions).
