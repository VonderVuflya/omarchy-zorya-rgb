## ADDED Requirements

### Requirement: Stable explicit Python runtime setup
Explicit runtime setup SHALL avoid mutable version-manager aliases and preserve the previous runtime on replacement failure.

#### Scenario: Version-manager latest alias changes
- **WHEN** a runtime is created and a version-manager alias later changes Python minor version
- **THEN** the private interpreter does not follow that alias.

#### Scenario: Dependency installation fails
- **WHEN** replacement installation fails after an old environment was backed up
- **THEN** the old environment is restored and its daemon restart is attempted without writing through external interpreter symlinks.

#### Scenario: Later installer operation fails
- **WHEN** runtime replacement succeeds before another installer step fails
- **THEN** the existing daemon has already been restarted with the verified runtime.

### Requirement: Isolated recoverable CLI launch
Checkout and installed launchers SHALL isolate Python settings and permit stdlib diagnosis and explicit Setup when the private interpreter cannot start.

#### Scenario: Private interpreter is broken
- **WHEN** the private startup probe fails and distribution Python is available
- **THEN** the CLI starts with distribution Python and preserves all arguments.

#### Scenario: Parent application injects Python settings
- **WHEN** a desktop process exports foreign Python paths or home settings
- **THEN** CLI imports use the selected interpreter's libraries and the trusted Zorya source tree.
