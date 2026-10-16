## Why
Installing the marketplace widget currently leaves users to install the runtime and diagnose hardware services manually. Existing Setup actions expose components and raw reports without a coherent path to usable lighting. Development also needs durable PR/OpenSpec/release rules.

## What Changes
- A read-only automatic first-open assessment and a reviewed, explicit setup wizard.
- Separate runtime, OpenRGB, detected Lian Li and verification stages with progress and retry.
- Reuse healthy services, preserve cooling, show actionable failures, and keep device selection/color testing explicit.
- Bootstrap the marketplace checkout before its private Python environment exists.
- Require OpenSpec decisions, pull requests and versioned GitHub releases/tags for future work.

## Impact
No installation, pairing, lighting changes or privileged actions happen on open or polling. Existing CLI setup remains available. Existing working users retain direct lighting controls. The base distribution Python 3.11+ remains a prerequisite; the wizard prepares the private SDK environment.
