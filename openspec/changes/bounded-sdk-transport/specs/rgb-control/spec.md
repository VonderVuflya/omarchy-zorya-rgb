## ADDED Requirements

### Requirement: Bounded SDK transport
SDK operations SHALL detect EOF and bound elapsed discovery/update time and untrusted protocol allocations from the first connection onward.

#### Scenario: Peer closes a partial controller packet
- **WHEN** a peer advertises a controller payload and closes before delivering it
- **THEN** the client disconnects and reports failure without spinning indefinitely.

#### Scenario: Peer streams fragmented or malicious responses
- **WHEN** reads fragment, trickle, nest notifications or advertise excessive allocations
- **THEN** valid bounded fragments are accepted and operations exceeding deadlines or limits fail closed.

### Requirement: Recovery deadline survives discovery exceptions
Resume recovery SHALL preserve its bounded readiness wait when discovery raises.

#### Scenario: Discovery continues to fail
- **WHEN** discovery raises beyond the recovery deadline
- **THEN** recovery releases available targets without repeated hardware restarts.

### Requirement: Preserve full-mode cooling services
Explicit hardware setup SHALL reject full-mode Lian Li adoption before configuration or service mutations, including older managed units.

#### Scenario: Existing service controls cooling or LCDs
- **WHEN** setup discovers a service that is not recognized as RGB-only
- **THEN** it reports the incompatibility and leaves the service and configuration intact.
