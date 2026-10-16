# Troubleshooting

| Symptom | Check |
| --- | --- |
| Nothing reaches the inbox | Camera Wi-Fi connection, FTP password, FTP-root-relative folder, passive ports, NAS firewall and camera power state |
| Everything is `waiting` on the first run | Expected: at least two unchanged observations separated by `settle_seconds` are required |
| A file keeps waiting | Transfer may still be writing, another process may change metadata, or the system clock moved backwards |
| Incomplete JPEG markers | Keep the source and retransmit from the card; a non-JPEG renamed to `.jpg` is not supported. The file is counted as `rejected` until its content changes |
| `rejected` count stays above zero | Expected after a size, marker or unsupported-format verdict; the file is not rechecked until it changes. Remove or replace it when you have reviewed it |
| Inbox folder(s) unreadable | Other files were processed; fix permissions on the named subfolder and the next run covers it |
| HTTP 400 on upload with Immich 2.x or older | Upgrade Immich to 3.0 or later; older servers require `deviceAssetId`/`deviceId` |
| Key permission error | Run as the key's owner; set mode `600` or `400`, and keep it outside the inbox |
| State permission error | The state directory must be owned by the runner and mode `700`; keep it on a local filesystem |
| HTTP 401/403 | Verify the API key and its four permissions; use the account that owns the intended library |
| HTTP 400/404 | Verify `/api` URL normalization and your Immich version; API compatibility may have changed |
| HTTP 413 | Check your reverse proxy's upload size limit as well as `max_file_mb` |
| HTTP 429/5xx or connection failure | Leave the source in place; the next scheduled run retries. Check Immich and network health |
| Redirect refused | Set the final HTTPS origin directly; a redirect must not forward the API key |
| Duplicate is trashed / unknown trash status | Review and restore the asset manually if intended, or resolve the server/API mismatch |
| Shared or ambiguous album | Choose a unique private album name, or set the intended album UUID explicitly |
| Upload worked but album failed | Fix album permissions; the next run checks the uploaded asset and retries the album operation |
| Another importer is running | Let it finish; all runs for one inbox must use the same state directory |
| State belongs to another configuration/key | Select a new empty state directory after changing URL, inbox, album or key |
| Files remain in the inbox | Intentional; this release never removes source files |
| Faces or search results are missing | Check Immich's background jobs and machine-learning service; these run after upload |
| Wrong capture time | Check camera clock/timezone and EXIF. Import does not rewrite metadata |

## Recheck after deleting an album or changing a key

Stop the scheduled task, retain the existing state directory, and set a new
empty `state_dir` in the private config. Give it mode `700` and the correct
owner. Run twice to observe and then recheck files. Immich's checksum check
prevents normal identical-file reuploads; the intended album is resolved again.
Resume the schedule after verifying the result.

Do not delete old state while a process is running or share SQLite state over
SMB/NFS. A NAS inbox may be mounted read-only on another host, but keep the
runner's state and lock local to that host.

## Before reporting a problem

Report versions, the fixed error text, counts and a minimal synthetic example.
Do not attach your configuration, database, real API response, image library,
network capture or screenshots containing private infrastructure. If a local
permission issue needs investigation, inspect it locally and redact any output
before posting it. Security reports belong in the private channel in
[SECURITY.md](../SECURITY.md).
