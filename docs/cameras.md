# Camera compatibility

The common interface is a directory containing complete JPEG files. The importer
does not use a manufacturer's camera API, EXIF model filter, cloud account or
phone application.

## What your camera needs

For direct camera-to-NAS operation, it must be able to join your home access
point and send JPEGs to a configurable FTP or FTPS server. Wi-Fi that only
supports a phone app, remote control or a vendor cloud is not equivalent.
Firmware, accessories and power-saving settings can change what is possible.

If a vendor desktop app or another bridge can reliably save JPEGs to the NAS
inbox, the importer can consume those files. Configuring such a bridge is
outside this release. Prefer a transfer tool that writes a temporary filename
and atomically renames it to `.jpg` only when complete.

| Camera / route | Evidence | Project test status |
| --- | --- | --- |
| Sony A7 IV / ILCE-7M4, native FTP | [Sony FTP Help Guide](https://helpguide.sony.net/di/ftp_2110/v1/en/index.html) documents wireless LAN transfer | Original private camera/NAS workflow used this route; public rewrite still needs a hardware test |
| Nikon Z 8, native FTP | [Nikon reference guide](https://onlinemanual.nikonimglib.com/z8/en/14_connecting_to_computers_or_ftp_servers_87.html) includes FTP over wireless LAN | Manufacturer-documented capability; not tested by this project |
| Canon EOS R5 Mark II, FTP | [Canon communication preparation](https://cam.start.canon/en/C017/manual/html/UG-06_Network_0040.html) documents FTP server transfer | Manufacturer-documented capability; complete camera/NAS interoperability not tested here |
| Other Sony, Nikon, Canon, Fujifilm, Panasonic or other brands | Check the exact model's manual for a configurable FTP/FTPS server or a folder-writing bridge | No blanket brand-wide support claim |

## Multiple cameras

Give each camera its own inbox subfolder and private configuration/state
directory. Choose a different album name for each, or explicitly set the same
existing `album_id` when you want a shared destination. Each run processes only
its configured inbox and descendants.

Ask the receiver to avoid overwriting existing filenames. Camera counters can
wrap and two cameras can generate the same name. Date-based destination folders
or receiver-side unique names protect files before the importer sees them.
The importer cannot recover a file that the FTP server has already overwritten.

## Report a tested combination

Include camera model, firmware, JPEG settings, transfer protocol, NAS/OS,
Python version, Immich version, and whether new/duplicate/retry tests passed.
Remove passwords, keys, hostnames, IP addresses, SSIDs, serial numbers and
personal image metadata. Use a generated test image if an attachment is needed.
