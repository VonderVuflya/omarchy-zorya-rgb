## Why
After real suspend, OpenRGB returned USB controllers but missed both RAM and GPU I2C controllers. Recovery retried only entirely empty SDK inventories; ordinary SDK refreshes cannot repeat hardware discovery.

## What Changes
Retry the owned OpenRGB startup scan once when selected devices are missing from a nonempty inventory. Share the existing single-redetection budget between empty and partial scans, keep the Lian Li bridge running, and retain independent errors for genuinely missing targets.

## Impact
Resume coordinator and regression tests; saved selection and lighting state remain unchanged.
