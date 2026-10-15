# Hardware support

Zorya controls controllers exposed by OpenRGB. It does not claim universal compatibility with every RGB device or every model carrying a similar product name.

| Integration | Behavior |
| --- | --- |
| OpenRGB SDK | Local loopback connections, per-device capabilities and independent errors |
| Lian Li wireless TX/RX V1 and V2 | Detects known USB controllers and offers the pinned RGB bridge |
| HydroShift II wireless pump ring | RGB control through the wireless bridge; standalone LCD media is outside scope |
| UNI FAN TL Wireless | RGB, static/preset restoration and capability-aware effects |
| Kingston Fury DDR5 | Optional official SPD-based identification backport for compatible families with broken RGB signatures |
| Other OpenRGB devices | Work according to the capabilities actually exposed by the SDK |

The reference PC used during development has an X870E AORUS PRO X3D ICE, Kingston Fury DDR5, RTX 5080 MASTER ICE, G502 HERO, HydroShift II LCD-C and three UNI FAN TL Wireless radiator fans. Exact checks and remaining verification limits are recorded in `docs/verification.md`.

Kingston setup reads SPD identity; it never writes SPD EEPROM. Lian Li firmware and device bindings are not modified by status polling. The default RGB service skips cooling and LCD control. The former controller and its cooling policy may be retained during an explicit migration.

A successful setup on the reference PC does not prove a fresh installation on every supported distribution or physical effect fidelity on every controller. Report failures with `zorya-rgb doctor`, selected device names and software versions; redact serials and personal paths before sharing reports.
