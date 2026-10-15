## ADDED Requirements

### Requirement: Arbitrary color and white
The plugin SHALL support HSV selection, HEX/RGB input, saturation, brightness, and explicit white.

#### Scenario: White selection
- **WHEN** the user selects white
- **THEN** color is #FFFFFF, saturation is zero, and selected devices receive brightness-scaled white.

### Requirement: Saved effects
The plugin SHALL support static, pulse, rainbow, gradient and named saved presets with validated parameters.

#### Scenario: Restore animated preset
- **WHEN** an animated preset is applied and the daemon restarts
- **THEN** its colors, brightness, selected devices, effect and speed are restored.

### Requirement: Hardware setup
The plugin SHALL detect supported Lian Li USB devices, expose actionable setup status, and install pinned dependencies only through explicit setup actions.

#### Scenario: Unsupported or missing tools
- **WHEN** a supported Lian Li controller is present but its bridge is unavailable
- **THEN** the UI shows which setup component is required and offers an installation action without silently changing cooling.

### Requirement: Resume recovery
The plugin SHALL detect actual suspend independent of wall-clock corrections, wait for device availability, and reapply saved state to all selected devices.

#### Scenario: Lost device colors
- **WHEN** suspend resets device color state
- **THEN** recovery restores the active preset automatically after rediscovery without requiring UI interaction.

### Requirement: Safe lifecycle
The plugin SHALL use only user-owned plugin/backend paths, restrict local IPC access, and preserve existing configuration during migration and removal.

#### Scenario: Remove plugin
- **WHEN** the user uninstalls Zorya
- **THEN** its services stop and its shell entry is removed while saved state and unrelated services remain preserved.

### Requirement: Explicit wireless pairing
The plugin SHALL report unbound wireless devices and SHALL pair only a currently discovered device after an explicit Pair action.

#### Scenario: Unbound radiator fans
- **WHEN** supported wireless fans are discovered without a binding
- **THEN** diagnosis shows the device and offers a Pair action without sending binding commands during polling.
