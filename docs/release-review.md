# Release preparation review — 2026-10-15

The review below records the private preparation stage on 15 October.
Publication was authorized on 16 October, with the physical camera/NAS test
still explicitly pending. The public README documents that limitation.

The 16 October publication checks passed locally: 53 tests, 92.57% statement
coverage, Ruff lint/format checks, and secret/privacy scans. The Affinity banner
and icon were rendered and inspected, including their PNG metadata and decoded
colour profiles. The private-repository CI attempts did not start because of
an account billing/spending restriction, so those runs are not test results.

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

## Review follow-up

1. Exercise this rewrite with a real camera, receiver and Immich instance using
   the [whole-path verification procedure](synology.md#6-verify-the-whole-path).
   Record duplicate handling, album membership, original image retention and
   Immich processing. The existing private workflow is not evidence that this
   rewrite passes those checks.
2. Artwork and publication review were completed on 16 October. The banner and
   icon in `docs/` contain only generated vector/text artwork. Native design
   documents and private environment data are not included.

No production installation or camera/NAS configuration was changed by this
review. Publication does not change the scope of the hardware verification.
