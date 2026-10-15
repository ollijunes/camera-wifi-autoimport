# Contributing

Start with a reproducible bug or a tested camera combination. Keep changes
focused and include a regression test when behavior changes.

```sh
uv sync --locked
uv run python -m pytest --cov=camera_import --cov-fail-under=85
uv run ruff check .
uv run ruff format --check .
gitleaks git --redact --no-banner .
python3 scripts/check_public_tree.py
```

Tests must use temporary directories, synthetic credentials and generated data.
Never add your photos, EXIF exports, private config, state database, keys, SSIDs,
personal hostnames or API response dumps, even to a temporary commit.

The local HTTP tests verify multipart requests, duplicate handling and redirect
rejection against a test server. They do not claim to test image decoding,
physical cameras, DSM installation or a live Immich deployment. If you test
those, report the exact versions and steps without private environment data.

Runtime code stays standard-library-only. Do not weaken source-file retention,
TLS validation, album confirmation, private file permissions or response
validation to make a device work. Discuss new file formats and camera bridges
before adding them.

Use a public-safe Git author address. Keep private assistant/session links out
of commit messages and pull request descriptions. Report vulnerabilities through
[SECURITY.md](SECURITY.md), not a public issue.
