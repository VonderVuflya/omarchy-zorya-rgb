# ZoryaRGB contributor instructions

Read `openspec/changes/initial-zorya-rgb/design.md` and `docs/implementation-plan.md` before changes. Record externally visible changes in OpenSpec. Keep Python core standard-library based; `openrgb-python` is the hardware SDK dependency. Never embed personal absolute paths, access tokens, raw device serials in fixtures, or private state.

QtQuick UI runs inside Omarchy's existing shell process. Validate manifests and QML against the installed shell; never edit `/usr/share/omarchy`. Hardware setup is explicit, predictable, and reversible. Do not install packages or bind hardware on import, plugin load, or status polling. Never write SPD EEPROM. Cooling changes need an explicit user choice.

Test real failure modes using fixtures/mocked adapters before physical hardware. Keep sleep recovery separate from animation/render logic. One device failure must not block control of others. Preserve third-party patch attribution and licenses.
