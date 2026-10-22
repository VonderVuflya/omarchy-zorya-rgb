# Release hardening for 0.3.3

## Why
A project review found failures that affect users before any new feature: OpenRGB 1.0 servers time out during SDK negotiation (issue #3), one unknown field in saved state discards every scene, one failing device on a shared SDK socket stalls the other devices on it, and CI never ran because its workflow was outside `.github/workflows`. The first-run panel opened on the color wheel instead of Setup, and the "Color & effects" tab rendered as "Color _effects".

## What Changes
- Retry a stalled SDK negotiation (timeout or early close) once with protocol 3 when no protocol is pinned, and remember that per endpoint.
- Load saved state per field and per scene; set commands stay strict. Keep an unreadable state file as `state.json.corrupt-<time>` before replacing it.
- Reconnect a shared SDK endpoint after its socket drops without putting the other devices on it into retry delay.
- Hardware setup on Arch installs only missing packages and never `systemd` or `python`; interrupted source checkouts recover; installation metadata writes are atomic and corrupt metadata is reported.
- Successful updates keep one source backup and the newest failed copy.
- Panel: Setup opens first while setup is needed, the device empty state links to Setup and Rescan, polling backs off while the backend fails, accessibility names are shorter, executable paths are URL-decoded.
- Prepare CI with a version consistency check; activation needs a token with workflow permission.

## Impact
No new dependencies. No new privileged operations; the Arch package request becomes narrower. Saved state written by a newer release loses only fields this release does not understand. Release 0.3.3.
