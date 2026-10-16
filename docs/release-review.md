# Release preparation review — 2026-10-15

Publication is on hold. The repository is private pending a later publication
decision. GitHub reported `PRIVATE`, and an unauthenticated request returned
HTTP 404. Changing visibility cannot retract copies made while it was public.

## Reviewed implementation

Reviewed commit `075b2c17989d85826b36d56597ec2d3d0c2fa242`: importer,
tests, configuration example, installation/security documentation, CI,
exclusions and the privacy checker. This review adds documentation only.

No blocking code defect was identified in this review. The following properties
were checked in the implementation and existing tests:

- Uploads use a private snapshot after two unchanged file observations. Source
  files are never deleted or moved, including on upload or album failures.
- Completion is recorded only after album membership succeeds. A retry checks
  the checksum again, including after a lost upload response.
- The API key is read from a restricted file. HTTP redirects and environment
  proxies are disabled, TLS verification remains enabled, and expected errors
  do not echo credentials, filenames or server response bodies.
- Camera-writable storage is separated from the key and state. File symlinks
  are refused and directory traversal does not follow symlinks.
- Camera compatibility claims distinguish folder ingestion from model-specific
  transfer support. JPEG markers are not presented as full image validation.

## Test and privacy evidence

The reviewed commit's [CI run](https://github.com/ollijunes/camera-wifi-autoimport/actions/runs/38723906727)
passed all ten jobs: eight Python/platform combinations, lint and secret checks.
The suite contains 53 tests; the previously measured statement coverage is
92.57%. No implementation changed during this review, so these results were
verified rather than rerunning the same suite for documentation changes.

Local privacy checks were rerun during review:

- Gitleaks: three reachable commits scanned, no findings.
- The privacy checker: three commits, 20 file versions, no findings;
  all 16 synthetic canaries passed.
- The existing release has no attached assets.

Earlier review also covered published CI logs, release/PR/commit metadata and
comments without findings. Scanners and manual review provide evidence, not a
guarantee that every possible secret format can be detected. Scan the final
publication revision and any added artwork or attachments again before making
the repository public.

After privatization, GitHub's repository API no longer reported a
`security_and_analysis` configuration. Hosted secret scanning and push
protection are therefore not counted as verified protections for this private
phase. The repository's Gitleaks and privacy-checker CI jobs remain configured;
their execution also depends on Actions availability for the private repository.

## Outstanding work before publication

1. Exercise this rewrite with a real camera, receiver and Immich instance using
   the [whole-path verification procedure](synology.md#6-verify-the-whole-path).
   Record duplicate handling, album membership, original image retention and
   Immich processing. The existing private workflow is not evidence that this
   rewrite passes those checks.
2. Finish the planned Affinity artwork and inspect the exported files and their
   metadata before adding them. The retry still timed out during MCP
   initialization; no banner has been rendered or added to this repository.
3. Review the final diff, run the relevant tests and both privacy scans, inspect
   publication metadata, and confirm the maintainer's decision to publish.

No production installation or camera/NAS configuration was changed by this
review. The repository must remain private until that later decision.
