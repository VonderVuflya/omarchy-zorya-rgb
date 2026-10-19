# Stable private Python runtime

## Why
Omarchy updated mise's mutable Python `latest` alias from 3.14 to 3.15. The existing venv followed the alias while its SDK stayed under python3.14, causing `No module named openrgb`.

## What Changes
- Build private runtimes with resolved distribution Python and copied executables.
- Isolate Python launchers from parent-process Python settings and retain system-Python diagnostics when private Python cannot start.
- Back up and rebuild environments during explicit Setup; restore the existing daemon after success or rollback.

## Impact
Installer and CLI launchers change. Saved scenes and hardware service configuration remain outside runtime rebuilding. No new dependencies or automatic installation on status/plugin load. Release 0.3.2.
