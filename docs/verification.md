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

## Live color controls, version 0.1.2

84 tests passed. A Qt ScrollView regression reproduced drag cancellation after only two color signals; pointer capture now preserves continuous dragging. A Quickshell Process integration regression reproduced one final write after continuous motion; throttling now sends bounded intermediate writes and preserves the final color. The native Omarchy panel was restarted and visually checked with rounded controls. No cooling settings were changed.

## Smooth pulse, version 0.1.4

96 Python tests passed with the SDK installed; 36 bridge Rust tests passed. The bridge supplement applied after the full compatibility patch on the exact upstream pin, with repeat-build detection verified. Live buffered uploads of150 frames at33 ms were accepted by both wireless controllers. The user confirmed that the cooler pulse became smooth. The GPU's native Pulse remained visibly stepped; the tested AORUS RTX5080/NVIDIA-adapter profile now uses Direct software pulse at up to30 FPS, and the user confirmed smooth output afterward. Twenty acknowledged GPU updates at30 FPS averaged0.32 ms (maximum0.52 ms) per SDK update. No fan curve was changed.

## Partial discovery recovery, version 0.1.5

A real2026-10-16 resume left the SDK with USB devices but neither RAM nor GPU. Both I2C nodes were accessible to the user at diagnosis; one later owned OpenRGB restart restored the seven-controller inventory and cleared both missing IDs without altering selection. The automatic coordinator now retries a partially populated selected inventory once, sharing its budget with the existing empty-scan retry.98 Python tests, all OpenSpec changes, QML and the installed manifest validated. Another physical suspend with this update remains to be observed.

## Bounded SDK transport, version 0.1.6

On 2026-10-16, 124 Python tests passed with pinned openrgb-python 0.3.6, including 23 transport tests. A bounded subprocess reproduced the upstream EOF hang; the adapter rejects the same truncated response and permits a subsequent valid connection. Coverage includes startup/later reads, fragmented packets, slow streams, nested notifications, oversized allocation fields and total discovery/update deadlines. Council regressions cover discovery exceptions after the resume deadline and rejection of both external and older managed full-mode Lian Li services before mutations. Independent final review found no remaining blockers in the reviewed scope.

All six OpenSpec changes passed strict validation; QML, Python compilation and whitespace checks passed. Read-only connections to the reference PC's actual protocol-4 OpenRGB and protocol-1 Lian Li endpoints returned five and two controllers respectively and completed subsequent updates. This is not proof of peer authentication: loopback SDK ports remain unauthenticated. No new physical suspend or clean hardware build was performed for this change.

## Guided first run, version 0.2.0

The updated read-only assessment on the reference PC found seven controllers and reported runtime, OpenRGB, Lian Li and verification ready without changing hardware or saved selection. All 149 Python tests passed with the pinned SDK, including launcher bootstrap, mocked per-stage installation and actual offscreen Quickshell process integration. The latter covers read-only opening, failure/retry, close/reopen, sticky errors, queued writes, blocked plans and revised-action review. Independent final review reported no remaining blockers after resolving Lian Li-only verification and forced scene-reapplication findings.

All seven OpenSpec changes, production QML, Python compilation, whitespace checks and a clean plugin export manifest validated. The repository directory itself contains development-only node_modules symlinks and is not a clean plugin artifact; validation used exported tracked/nonignored source files instead. A new clean-machine hardware build, physical suspend and visual verification of the installed wizard have not been performed. Local verification does not imply remote GitHub Actions ran.

## Updates and support, version 0.3.0

209 tests passed with the pinned SDK, including release transaction/cache/downgrade tests, last-error capture, diagnostic redaction, reviewed-body submission and real offscreen QML process sequencing. Independent review findings were resolved and rechecked: mixed-component downgrades, private path/serial leaks, actual kernel driver retention, ambiguous submission receipts and explicit GitHub hostname pinning. A cross-URL Loader fixture reproduced and verifies the fix for a null panel cast reported in issue #2. UI tests cover successful result-before-rescan ordering and mutual exclusion of updates/report submission through asynchronous process startup.

Eight OpenSpec changes, production QML, clean-export manifest validation, Python compilation and whitespace checks passed. A live read-only GitHub check returned the current release. The reference-PC report included active drivers, saved full Markdown with0600 permissions and correctly capped its browser draft at7500bytes with a visible truncation notice. No test issue was published; GitHub submission and transactional upgrade/rollback were tested with mocked external boundaries and temporary sources, not by applying an update to physical hardware. Physical suspend and a clean hardware installation were not repeated. Remote GitHub Actions was not run.

## Startup-report follow-up, version 0.3.1

The first real0.3.0 release-tag deployment succeeded on the reference PC, synchronizing UI/app/runtime versions and preserving all seven selected controllers, saved color and service health. It exposed a pre-existing successful-connect fallback message newly retained by error history. A failing regression reproduced that first iteration; the fallback now applies only when discovery remains disconnected.210 tests and strict OpenSpec/QML checks passed. No issue was submitted during verification.

## Stable Python runtime, version 0.3.2

An Omarchy/mise update moved the reference PC's `latest` Python alias from3.14 to3.15 while its private SDK remained under python3.14. Rebuilding the private environment with distribution Python3.14.8 restored OpenRGB imports and six controllers without changing the saved scene. The separate UNI FAN TL wireless group reports unbound in the bridge; this fix does not claim to repair pairing.

216 tests passed with pinned openrgb-python0.3.6. Six runtime regressions cover resolved aliases/copied interpreter creation, rollback without overwriting external Python, daemon restart before returning, isolated checkout imports and installed-launcher fallback. The two independent review findings were reproduced as failing tests, fixed and rechecked without remaining blockers. Nine OpenSpec changes, QML, clean-export manifest, Python compilation and whitespace checks passed. QML retains its existing ColorWheel id-shadow warning. No new physical suspend or clean hardware build was performed; remote CI was not run.
