## ADDED Requirements

### Requirement: Smooth capability-aware pulse
The plugin SHALL prefer native pulse at reduced brightness and SHALL use bounded onboard loops for supported wireless controllers with replay-safe bridge support.

#### Scenario: GPU without a brightness capability
- **WHEN** pulse is selected below full brightness
- **THEN** the native pulse receives brightness-scaled primary colors without host frame streaming.

#### Scenario: Buffered wireless pulse
- **WHEN** a supported replay-safe controller runs pulse
- **THEN** it plays a bounded smooth periodic loop and recovery preserves all animation frames.

#### Scenario: Transport fallback
- **WHEN** no native or buffered mode is available
- **THEN** USB/HID frames may update at up to30 FPS while conservative transports retain their rate limit.

#### Scenario: Known coarse native GPU pulse
- **WHEN** the tested AORUS RTX 5080 on its dedicated NVIDIA I2C adapter exposes Direct mode
- **THEN** pulse uses smooth software frames at up to30 FPS while unknown I2C controllers retain conservative limits.
