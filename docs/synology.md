# Sony A7 IV (or another FTP camera) → Synology → Immich

This guide assumes DSM 7, a working home network and an Immich account. Menu
labels vary by camera firmware and DSM version. Values below are examples;
none are the maintainer's home-network settings.

## 1. Install Immich and choose storage

Install Container Manager from DSM's Package Center if needed. Follow Immich's
[Synology community installation guide](https://docs.immich.app/install/synology/)
and use the Compose files supplied for your chosen Immich release. Keep the
Immich server and machine-learning versions aligned.

Set Immich's `UPLOAD_LOCATION` to storage on the NAS and keep its database in
the location prescribed by the installation guide. Open Immich in your browser,
create the photo owner's account, and upload a test image manually before
adding the camera importer. Maintain backups of both images and the database.

Create a separate DSM shared folder named `camera-inbox`. It must not be inside
Immich's managed storage. You can create a `camera-1` subfolder for one camera.
Do not add this inbox as an Immich external library.

## 2. Configure the NAS as the receiver

1. Reserve the NAS's LAN address in your router's DHCP settings. Use that address
   in the camera's FTP profile.
2. Create a dedicated DSM camera user. Grant read/write access only to the
   camera inbox, no administrator membership, and only the needed FTP application
   permission. Use a unique password.
3. In **Control Panel → File Services → FTP**, enable the transfer protocol.
   Prefer explicit FTPS (FTP over TLS) when supported by both devices, with a
   certificate the camera can validate. SFTP is a different protocol.
4. Under FTP advanced settings, restrict the camera user's FTP root to the
   inbox if your DSM configuration supports it. A camera folder under that root
   is then `/camera-1`, not the NAS filesystem path `/volume1/camera-inbox/camera-1`.
5. Allow the FTP control port and configured passive data ports only from your
   trusted camera/home network. Keep DSM's firewall enabled. Do not forward FTP
   ports from the internet or enable anonymous login.

Plain FTP sends credentials and images without encryption. The original Sony
workflow used FTP on the home LAN; this guide does not claim FTPS was tested on
that setup. If you choose FTP, keep it on a trusted local network and restrict
the account and firewall accordingly.

See [Synology's FTP instructions](https://kb.synology.com/en-us/DSM/tutorial/How_to_access_files_on_Synology_NAS_via_FTP).

## 3. Configure the camera

### Sony A7 IV

Join your home Wi-Fi access point. Open **Network → FTP Transfer → FTP Transfer
Func.** and configure a server profile:

| Setting | Value |
| --- | --- |
| Host | Your NAS's reserved LAN address |
| Port | The port configured in DSM |
| User / password | Dedicated camera FTP account |
| Destination | The folder as seen from the user's FTP root, for example `/camera-1` |
| Passive mode | On, matching the NAS firewall's passive port range |
| Secure connection | Match DSM's FTPS/FTP configuration; validate the server certificate when using TLS |
| RAW+JPEG transfer target | JPEG only |
| FTP function / Auto FTP Transfer | On |

Start with one new JPEG. Check that it arrives in the inbox. For older photos,
use the camera's FTP selection controls to transfer the desired card contents.
Automatic transfer does not necessarily send every old image just because the
camera has joined Wi-Fi. Keep the camera powered during transfer.

The reference workflow used 5 GHz Wi-Fi after testing 2.4 GHz. Choose a band
both the camera and access point support with a reliable signal; there is no
universal throughput guarantee. Set the camera's date, time and timezone before
shooting: the importer preserves JPEG bytes and does not repair bad EXIF dates.

Manufacturer reference: [Sony ILCE-7M4 FTP Help Guide](https://helpguide.sony.net/di/ftp_2110/v1/en/index.html).

### Other cameras

Use the model's own FTP/FTPS instructions and send JPEGs to the same kind of
inbox. The importer neither logs into the camera nor requires Sony metadata.
See [compatibility requirements](cameras.md) for Nikon, Canon and other brands.

## 4. Configure the importer

Run the importer as a dedicated, non-administrator NAS user with read access to
the inbox and ownership of its private state/key directory. The camera account
must not have access to the API key or state directory.

Check `python3 --version`: this project requires **Python 3.11+**. DSM's bundled
Python may be older. Install a supported Python package for your NAS and use
its absolute executable path, or run the script on another Linux machine with
the inbox mounted read-only and state on that machine's local disk. Do not
replace DSM's system Python. Container Manager for Immich does not itself supply
a host `python3` executable for this script.

Clone or download the repository to `/volume1/docker/camera-wifi-autoimport`.
The following commands run as the importer user; ensure its parent directory
allows it to create these private files:

```sh
umask 077
mkdir -p /volume1/docker/camera-wifi-autoimport-private/state
chmod 700 /volume1/docker/camera-wifi-autoimport-private
chmod 700 /volume1/docker/camera-wifi-autoimport-private/state
cp /volume1/docker/camera-wifi-autoimport/config.example.toml \
  /volume1/docker/camera-wifi-autoimport-private/config.toml
```

In Immich's user settings, create a key with these permissions:

| Permission | Used for |
| --- | --- |
| `asset.upload` | Check checksums and upload new photos |
| `album.read` | Find the destination album |
| `album.create` | Create the album if it does not exist |
| `albumAsset.create` | Add new and duplicate assets to the album |

Store the key without putting it in a shell argument or history. Run this in
an interactive terminal and paste the key at the hidden prompt:

```sh
python3 -c 'import getpass, os; p="/volume1/docker/camera-wifi-autoimport-private/immich.key"; f=os.open(p, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600); os.write(f, getpass.getpass("Immich API key: ").encode()); os.close(f)'
```

This creates a new file and refuses to overwrite an existing one. Keep the key
in your password manager too, or be prepared to revoke and replace it in Immich.

Edit the private `config.toml`:

- `inbox`: `/volume1/camera-inbox/camera-1` in this example.
- `immich_url`: `http://127.0.0.1:2283` if the script runs on the NAS and Immich's
  port is published there; otherwise use your verified HTTPS origin.
- `album`: for example `Sony A7 IV`, `Nikon camera`, or `Camera uploads`.
- `api_key_file` and `state_dir`: the private paths created above.

An existing shared album is refused when selected only by name. Set `album_id`
explicitly only if you intend to put the photos in that shared album. Multiple
albums with the same name also require an explicit UUID.

For a remote HTTP server, `allow_insecure_http = true` is an explicit opt-in to
unencrypted API traffic. Prefer verified HTTPS. Redirects are refused; configure
the final server URL. HTTPS verification cannot be disabled in this script.

Run the dry-run command twice at least 60 seconds apart, then run without
`--dry-run`, as shown in the [README](../README.md#quick-start). The script needs
temporary disk space for up to two copies of one JPEG in its private state
directory. It uploads sequentially to avoid flooding the NAS with image jobs.

## 5. Schedule it

In **DSM Control Panel → Task Scheduler**, create a scheduled user-defined
script under the importer user. Schedule it every two minutes and use absolute
paths. Replace `/path/to/python3` with the actual Python 3.11+ executable:

```sh
umask 077
/path/to/python3 /volume1/docker/camera-wifi-autoimport/camera_import.py \
  --config /volume1/docker/camera-wifi-autoimport-private/config.toml
```

Use DSM's task execution results and failure notifications to monitor it.
Avoid editing DSM's system crontab directly: DSM updates can replace it.
On a regular Linux host, the equivalent crontab entry is:

```cron
*/2 * * * * /path/to/python3 /path/to/camera_import.py --config /path/to/private/config.toml
```

Exit `0` means the pass completed without a reported failure; `waiting` files
may still be unprocessed. Exit `1` means a configuration, file, API or lock
error; exit `2` means invalid CLI arguments. Check counts, not just the exit code.

## 6. Verify the whole path

Take a test photo, allow two scheduled passes, and open the chosen Immich album.
Check the original resolution and capture date. Send the same JPEG again under
another name: it should join the album without another upload. Confirm the
original inbox files remain and the next run reports them as `recorded`.

Immich's face detection, recognition and search run as separate background jobs.
Check their queues and machine-learning service if faces do not appear. The
importer's success count does not validate facial recognition or backups.

After DSM/Immich/Python upgrades, repeat the test and check the scheduled task.
Inbox retention is your responsibility: this version never removes files.
