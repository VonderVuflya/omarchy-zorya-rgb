# ZoryaRGB Implementation Plan

**Goal:** Самостоятельный Omarchy RGB-плагин с переносимой настройкой оборудования и восстановлением состояния.
**Architecture:** QML UI → JSON CLI → пользовательский Unix daemon → OpenRGB и Lian Li adapters.
**Tech Stack:** Python3.11+, openrgb-python, QtQuick/Quickshell, systemd user, OpenSpec.
**Spec:** openspec/changes/initial-zorya-rgb/design.md

## Ownership and Interfaces

Backend agent owns `zorya_rgb/{state,effects,openrgb_backend,daemon,cli}.py`, `bin/zorya-rgb`, backend tests and pyproject.toml. Setup agent owns `zorya_rgb/{hardware,setup}.py`, `scripts/`, `patches/`, `systemd/` and setup tests. UI agent owns `manifest.json`, QML/JS, UI tests. Root owns OpenSpec/docs/CI/integration/repository publication. Shared state/CLI contract is the design decision4; interface changes require message to root.

## Tasks

- [x] Backend: failing tests for invalid RGB/speed/state and deterministic effects; implement state and presets; mocked SDK tests including GPU palette normalization; daemon0600 IPC, reconnect and actual-sleep recovery; CLI JSON contract.
- [x] Setup: read existing working hardware fixes; fixture detection; portable pinned build scripts/patches and dependency checks; user services, explicit privileged USB ACL step, adoption of existing compatible tools, migration and rollback.
- [x] UI: native bar-widget manifest; rich panel with HSV wheel/white/HEX/RGB/brightness; effect controls and saved presets; device and setup sections; debounced IPC with separate process objects to prevent stale writes.
- [x] Root: integrate contracts; run Python tests, OpenSpec validation, manifest validation and qmllint; install isolated user plugin and test native shell lifecycle; authenticate GitHub and publish public repo with attribution and truthful compatibility matrix.

## Acceptance

No personal absolute paths in shipped source. No second Quickshell. No automatic privileged install on plugin load. No unknown hardware writes or SPD writes. Animation errors and offline backends are visible; UI remains responsive. Restore occurs after backend readiness, not before discovery. Repository contains reproducible installers, not only links to private artifacts.
