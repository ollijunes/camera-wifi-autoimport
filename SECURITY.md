# Security

## Report a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/ollijunes/camera-wifi-autoimport/security/advisories/new).
Do not open a public issue containing a credential, private network detail or
personal photograph. Describe the issue with synthetic data and include the
affected version. Security fixes target the latest release.

## Data and credential handling

- The Immich key is read from a private file owned by the runner. Its mode must
  be `600` or `400`; symbolic links and non-regular files are refused.
- Keep key, private config and state outside both the Git checkout and FTP inbox.
  Restrict parent-folder access and DSM ACLs as well as POSIX mode bits.
- API requests use only the configured HTTP(S) origin. TLS verification is on,
  redirects are refused, and environment HTTP proxy settings are ignored.
  Remote plain HTTP requires an explicit configuration opt-in.
- Logs use counts and fixed errors. The script does not print API keys, image
  names, configured server URLs, raw server responses or exception tracebacks
  for expected operational errors. Do not run Python with debug HTTP tracing.
- State holds private filenames and a hash binding the destination and key.
  Temporary files hold JPEG bytes. Both belong in a local, mode-700 directory
  that the FTP user cannot access. Disk encryption/backups are the operator's responsibility.
- Filenames are treated as untrusted input. Multipart filenames are sanitized,
  file symlinks are refused, and directory walks do not follow symlinks.
- The importer never deletes or moves originals or Immich assets. It uploads
  and adds album membership only. Exact duplicates already in trash are held
  for review. A shared album requires an explicit `album_id` opt-in.

## Transfer limits

The camera-to-NAS leg is configured outside the script. Prefer validated FTPS.
Plain FTP exposes credentials and photo bytes to anyone who can observe that
traffic. Do not expose the FTP receiver to the internet.

Stable size/timestamps and JPEG boundary markers catch common partial transfers;
they are not a full JPEG decoder or a proof that a sender has finished forever.
A paused overwrite of an existing valid JPEG can fool a stability heuristic.
Use unique destination filenames and atomic final rename when the receiver
supports it, and retain the camera card until you verify the imports.

The checksum follows Immich's SHA-1 API. It detects normal identical-file
duplicates, not deliberate cryptographic collisions or visual similarity.

The runner trusts its local configuration, its private directory, and the
configured Immich server. It is not a sandbox against a compromised NAS,
malicious administrator, or code executed as the same user. Keep Immich and
the receiver patched, restrict the camera account, and back up the library.

## Repository hygiene

Examples contain invented paths and public documentation links only. Tests
generate synthetic credentials and marker fixtures. No private repository
history, camera photos, state databases, API responses or production settings
belong here. Gitleaks scans the Git history in CI; automated scanning complements
manual review and does not prove the absence of every possible secret.

Before publishing a branch, inspect staged files, commit author metadata,
commit messages and test output. Enable GitHub secret scanning and push
protection on forks where available.
