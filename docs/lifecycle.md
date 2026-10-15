# Lifecycle and permissions

The UI never launches another Quickshell. It sends structured argument arrays to a local CLI; settings travel as JSON rather than shell fragments. The per-user daemon validates updates and writes state atomically.

State is stored under `$XDG_STATE_HOME/zorya-rgb` (normally `~/.local/state/zorya-rgb`). Runtime IPC lives under `$XDG_RUNTIME_DIR/zorya-rgb` with user-only access. Installed tools live under `$XDG_DATA_HOME/omarchy-zorya-rgb`, plugin files under the user Omarchy plugin directory, and services under the user systemd directory.

Sleep detection compares Linux BOOTTIME with MONOTONIC. Wall-clock adjustments and ordinary scheduling delays do not qualify as suspend. Recovery coordinates the managed hardware services, waits for device enumeration, and reapplies the saved scene. It does not periodically restart healthy services.

Installation, migration and uninstallation are explicit operations. Existing unit configuration and enabled/active states are tracked when compatible tools are adopted. Uninstallation stops Zorya-owned units, preserves saved state and restores adopted service state when recorded. It does not uninstall system packages or erase unrelated configurations.

A polkit password may be requested for distribution build packages or narrow hardware access rules. Hardware builders run source compilation as the user. Original system OpenRGB executables and `/usr/share/omarchy` remain unchanged.
