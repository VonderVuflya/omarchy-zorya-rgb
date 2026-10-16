## ADDED Requirements

### Requirement: Partial resume hardware discovery
Automatic resume recovery SHALL retry the owned OpenRGB hardware scan once for an incomplete selected inventory, including when the SDK already exposes other controllers. Empty and partial scan recovery SHALL share one redetection budget.

#### Scenario: USB devices present but I2C targets missing
- **WHEN** OpenRGB exposes USB devices after resume but selected RAM or GPU controllers remain missing
- **THEN** recovery performs one delayed owned OpenRGB rescan and preserves the saved selection.

#### Scenario: Device remains physically unavailable
- **WHEN** the selected inventory remains incomplete after the retry
- **THEN** recovery reports the missing target and controls available devices without repeated service restarts.
