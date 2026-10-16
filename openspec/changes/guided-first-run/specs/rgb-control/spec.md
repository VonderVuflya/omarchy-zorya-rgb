## ADDED Requirements

### Requirement: Read-only first-use assessment
Opening the panel SHALL assess setup readiness without installing dependencies, changing units, pairing devices or writing lighting state.

#### Scenario: Marketplace checkout has no private runtime
- **WHEN** the panel opens on a system with base Python but no private SDK environment
- **THEN** setup assessment remains usable and explains the preparation required.

#### Scenario: Compatible services already work
- **WHEN** bounded SDK discovery and the runtime are healthy
- **THEN** assessment reports their readiness and setup does not replace or restart them.

### Requirement: Explicit guided setup with recoverable stages
The panel SHALL show planned actions before user-initiated setup and report each runtime/hardware/verification stage separately.

#### Scenario: Setup stage fails
- **WHEN** one stage fails
- **THEN** later stages do not run and the error and recovery action remain visible despite status polling or panel reopening.

#### Scenario: User retries setup
- **WHEN** the user requests retry after correcting a failure
- **THEN** assessment runs again and healthy stages are skipped.

#### Scenario: Full-mode cooling service would be replaced
- **WHEN** a required hardware setup conflicts with a full-mode Lian Li service
- **THEN** setup reports the conflict and preserves its cooling and LCD operation.

### Requirement: Explicit lighting verification
Successful discovery SHALL report devices and offer device selection and an explicit current-scene test without automatically changing the selection or lighting.

#### Scenario: No devices selected
- **WHEN** hardware is discovered but no targets are selected
- **THEN** the user is directed to choose devices and no automatic all-device scene is applied.

#### Scenario: Only supported Lian Li devices are present
- **WHEN** the supported bridge provides devices and the OpenRGB endpoint is empty or absent
- **THEN** verification can succeed without requiring an unused OpenRGB service.

#### Scenario: Current saved scene has been overwritten externally
- **WHEN** the user explicitly requests the lighting test
- **THEN** the current scene is forcefully reapplied to selected devices even when the saved color is unchanged.

### Requirement: Review revised setup actions
Setup SHALL preserve the user's review boundary when reassessment changes the actions required.

#### Scenario: Hardware changes after the plan was reviewed
- **WHEN** reassessment adds a new setup action or changes its explanation
- **THEN** the updated plan is shown and another explicit Start action is required before running it.
