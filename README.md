# ZoryaRGB for Omarchy

Named after Zorya, the dawn figure in Slavic folklore.

![ZoryaRGB panel](preview.png)

RGB control in the Omarchy bar. Pick a color on the wheel and your fans, RAM, GPU and other OpenRGB devices change as you drag. Save scenes, run pulse, rainbow or gradient effects, and get your lighting back after suspend. Lian Li wireless fans and pump rings work through a bundled RGB-only bridge.

## Install

```sh
omarchy plugin add https://github.com/VonderVuflya/omarchy-zorya-rgb.git --enable
```

1. Click the ZoryaRGB icon in the bar. The panel opens on **Setup** and checks what is already in place without changing anything.
2. Select **Start setup**. It prepares a private Python runtime and the hardware services you need. You may be asked for your password to install build packages or USB/I2C access rules, and a fresh hardware build can take several minutes. Closing the panel does not stop it.
3. Open **Devices**, select what Zorya should control and pick a color to check that the lights respond. Nothing is controlled until you select it.

If a step fails, its error stays on screen and **Retry setup** continues from the stages that are still needed.

## Supported hardware

| Hardware | Status |
| --- | --- |
| Anything OpenRGB detects (motherboards, GPUs, RAM, keyboards, mice) | Works with the modes the device reports |
| OpenRGB 1.0 from the Arch repos | Supported; an existing `openrgb --server` unit is reused |
| Lian Li wireless TX/RX V1 and V2, UNI FAN TL Wireless | RGB, effects and restore after suspend |
| Lian Li HydroShift II pump ring | RGB only; the LCD is not controlled |
| Kingston Fury DDR5 | Optional detection fix for modules OpenRGB misses |

Zorya does not set fan curves, pump speeds or LCD media, and never writes RAM SPD EEPROM. If a device does not support an effect, the panel shows an error for that device instead of pretending it worked. Details and the reference PC are in [hardware support](docs/hardware.md).

## Using it

Drag the wheel or type a HEX or RGB value. **Pure white** selects `#FFFFFF`, and brightness is a separate slider. Effects are static, pulse, rainbow and a two-color gradient, each with a speed control. Save a scene by name to keep color, brightness, effect, speed and device selection together; saving again with the same name updates it.

Native device modes are used when a device has them. Otherwise Zorya animates in software at up to 30 FPS on USB/HID devices and 2 FPS on slower SMBus or wireless links. Lian Li wireless controllers run pulse from a smooth onboard frame loop.

Everything is also available from the terminal:

```sh
zorya-rgb status
zorya-rgb devices
zorya-rgb set --json '{"color":"#FFFFFF","brightness":75,"effect":"static"}'
zorya-rgb set --json '{"effect":"gradient","color":"#00E5FF","secondary_color":"#FF3399"}'
zorya-rgb preset save "Evening"
```

## Updates and bug reports

Zorya checks GitHub Releases when the bar loads and every six hours. When a newer release exists, an **↑** button appears; open it to see the version and choose **Install update**. The UI and runtime update together from that release tag, and a failed health check rolls the update back. Your scenes and hardware setup are kept. Local git edits block an update, and releases that change dependencies ask you to run Setup instead.

When something fails, select **Prepare issue report**. You get a readable report with versions, hardware models, drivers, service states and the error. Device serials, credentials and your home path are filtered out, but read it before posting. With an authenticated GitHub CLI, **Create GitHub issue** files it in one click; otherwise copy the report or open the issue form.

## Troubleshooting

**Clicking the bar icon does nothing.** Update to 0.3.0 or later; older releases had a QML cast that broke the panel on some shell builds.

**"Backend disconnected" with OpenRGB 1.0.** Fixed in 0.3.3: Zorya retries the SDK handshake with protocol 3 when the server does not answer the default one. Run **Retry setup** after updating.

**`No module named openrgb` after an Omarchy update.** Open **Setup** and run the runtime step. It rebuilds the private Python environment and keeps your scenes and hardware services.

**No devices found.** Run `zorya-rgb doctor` to see which services, USB devices and I2C permissions are missing. Lian Li devices that are not bound to the receiver appear in Setup with a **Pair** button. Pairing only happens when you click it.

**What did Setup change?** User services under `~/.config/systemd/user`, the private runtime under `~/.local/share/omarchy-zorya-rgb`, and, if you approved them, build packages and udev rules for USB/I2C access. Existing RGB-only services are reused. Setup refuses to replace a Lian Li service that also controls cooling or the LCD. See [lifecycle and permissions](docs/lifecycle.md).

## Migrating from the old RGB plugin

```sh
zorya-rgb migrate
```

This imports the old plugin's selected devices and color. Compatible user services are adopted, and their previous state is recorded so uninstall can restore it.

## Advanced setup

Setup's **Advanced tools** has diagnostics, pairing and the optional Kingston fix. The same steps are available from the terminal:

```sh
zorya-rgb onboarding plan
zorya-rgb doctor
zorya-rgb setup --component all --dry-run
zorya-rgb setup --component openrgb
zorya-rgb setup --component lianli
zorya-rgb setup --component kingston
```

Hardware builds use pinned upstream commits and the bundled compatibility patches. Arch-based Omarchy is the main target; on other systems, setup reports which dependencies are missing before it does anything. To install from a checkout instead of `omarchy plugin add`, run `./bin/zorya-rgb install`.

## Remove

```sh
zorya-rgb uninstall
omarchy plugin remove vondervuflya.zorya-rgb
```

Saved scenes stay on disk. Unrelated services and system packages are left alone, and adopted services get their previous state back.

## Contributing

Bug reports and ideas are welcome in [issues](https://github.com/VonderVuflya/omarchy-zorya-rgb/issues). For code changes, see the [contribution guidelines](CONTRIBUTING.md) and [development notes](docs/development.md); behavior changes are recorded in [OpenSpec](openspec/changes).

## License and upstream credits

Zorya's original code is **GPL-3.0-or-later**. `openrgb-python` is GPLv3. OpenRGB compatibility patches keep their GPL-2.0-or-later notices, and the Lian Li patches keep the MIT license. See [third-party notices](THIRD_PARTY_NOTICES.md).
