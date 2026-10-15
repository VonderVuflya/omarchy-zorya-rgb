# Verification of version 0.1.0

Checked on the reference Arch/Omarchy PC on 2026-10-15.

- 77 Python tests passed with the real openrgb-python 0.3.6 dependency, including mocked reconnect, resume, selection, effects, migration and installation failures.
- Strict OpenSpec validation passed. Installed plugin manifest and QML validation passed.
- Native Omarchy shell: panel opens and closes; color wheel and theme controls render inside the existing shell. A full shell restart is required after QML changes when its compiled component cache is stale.
- Local installation adopted existing working OpenRGB and Lian Li binaries/configuration into dedicated user services; cooling policy was preserved.
- Both SDK endpoints expose seven controllers: two-DIMM Kingston RAM controller, GPU, keyboard, mouse, motherboard, pump ring and radiator fan group.
- Static, pulse, rainbow and gradient were applied through the real SDK without reported device errors; the previous scene was restored afterward. This verifies API acceptance, not visual fidelity of every LED.

Physical suspend/resume and long-duration lighting stability still need user observation with this new plugin. Recovery and reconnect failure paths are covered by automated tests. A clean hardware build on a machine without existing binaries has not been executed end to end; pinned source patches were checked separately. No universal device compatibility is claimed.

Remote GitHub Actions were not run: the publishing token lacked workflow scope. The supplied CI template runs the Python suite on Python 3.11/3.14 and strict OpenSpec validation once activated.

## Resume fix, version 0.1.1

A real suspend on the reference PC exposed a bridge self-reexec/systemd restart race (90-second stop timeout), an empty early OpenRGB scan, and an indefinite readiness barrier. A later OpenRGB restart restored all seven controllers; the user confirmed that lighting commands and normal fan speeds returned. Telemetry then reported approximately 1320–1330 RPM for all three radiator fans and coolant at 36 °C. The fix removes the competing bridge restart, retries empty OpenRGB discovery once, and bounds waiting for absent selected controllers. Another physical suspend with the new code still needs observation; no automatic suspend was performed during the active session.

Version 0.1.1: 82 tests passed with the real SDK installed; both OpenSpec changes passed strict validation, QML and the installed manifest validated. The updated user daemon reports seven controllers and no missing devices or errors.
