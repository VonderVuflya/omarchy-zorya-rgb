# Third-party notices

- **OpenRGB** — CalcProgrammer1 and contributors, GPL-2.0-or-later. The Kingston SPD detection compatibility patch is derived from official upstream source. Original copyright headers and the GPL license are retained in the patches directory. The setup builder downloads source at a pinned commit and produces a private user binary.
- **openrgb-python** — upstream contributors, GPLv3. Installed into the private Python environment as a separate package.
- **lian-li-linux** — sgtaziz and contributors, MIT. Bundled RGB/resume compatibility patches retain the upstream license. The setup builder downloads a pinned source revision.
- **FFmpeg** — upstream contributors, primarily LGPL-2.1-or-later for the minimal build used here. No GPL/nonfree codec configuration is enabled by Zorya's RGB-only dependency builder.
- **EVDI** — DisplayLink and contributors; the setup uses the pinned upstream userspace library and retains upstream license files. The builder does not install the kernel module.
- **OpenSpec** — Fission-AI and contributors, MIT; development tooling only.

No upstream project is implied to endorse Zorya. Exact source revisions and supplied patch licenses are recorded beside the installer scripts and patch files.
