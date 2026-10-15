## ADDED Requirements

### Requirement: Bounded independent resume recovery
The plugin SHALL avoid restarting a self-restarting Lian Li bridge during automatic resume, SHALL retry an empty early OpenRGB scan once, and SHALL limit waiting for selected devices.

#### Scenario: Missing controller after suspend
- **WHEN** one selected controller remains unavailable after the settling deadline
- **THEN** commands apply to available controllers and missing targets remain visible as errors.

#### Scenario: Empty OpenRGB discovery
- **WHEN** OpenRGB starts after resume with an empty controller list
- **THEN** the plugin performs one delayed rediscovery through its owned service without restarting the bridge.
