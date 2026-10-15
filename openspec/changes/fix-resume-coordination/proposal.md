## Why
Real suspend exposed competing bridge self-reexec and Zorya systemctl restart, an empty early OpenRGB hardware scan, and an indefinite all-device readiness barrier. This left fans at fail-safe speeds during recovery and blocked lighting commands.

## What Changes
- Let the compatible Lian Li bridge own its resume restart.
- Delay OpenRGB scanning until USB/I2C settles and retry one empty scan.
- Bound resume readiness waiting, restore available devices, and report missing targets separately.

## Impact
Recovery lifecycle and regression tests; existing fan curves and saved scenes are preserved.
