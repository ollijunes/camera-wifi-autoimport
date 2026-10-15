# Release verification

## v0.1.0

The public importer is a rewrite of an existing private Sony A7 IV / Synology
workflow. Verification of that earlier workflow does not substitute for testing
this release on physical hardware.

- 53 automated tests passed locally on macOS with Python 3.11 and 3.12.
- Statement coverage: 92.57% for `camera_import.py`; the CI minimum is 85%.
- Ruff lint and format checks passed.
- Gitleaks found no findings in the release source tree.
- Test HTTP requests exercise multipart uploads, duplicate checks, album
  creation/membership, errors and redirect rejection. Only a loopback test
  server and generated fixtures are used.
- Source files remain intact in success, failure and retry tests. Tests cover
  stale capture timestamps, changed files, lost upload responses and album
  failures after upload.

API request/response contracts were checked against Immich's
[v3.3.1 OpenAPI specification](https://github.com/immich-app/immich/blob/v3.3.1/open-api/immich-openapi-specs.json)
(tag commit `db6e11ecc851228aec9c525abb0ee026d1f5055e`). The required permissions
are `asset.upload`, `album.read`, `album.create` and `albumAsset.create`.

The test suite does not start Immich itself, decode the generated JPEG marker
fixtures, connect to cameras, or validate DSM installation steps. End-to-end
verification of the public release on a camera/NAS is still pending. See the
[whole-path verification steps](synology.md#6-verify-the-whole-path).

The current GitHub CI result is shown by the README badge and the
[Actions runs](https://github.com/ollijunes/camera-wifi-autoimport/actions).
