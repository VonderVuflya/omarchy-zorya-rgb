## ADDED Requirements

### Requirement: OpenRGB protocol negotiation fallback
When no protocol version is pinned, the SDK connection SHALL retry a negotiation that times out or is closed by the server once with protocol 3 and reuse a successful fallback for that endpoint.

#### Scenario: Server does not answer the default protocol
- **WHEN** negotiation with the library default protocol times out or the server closes the socket, and protocol 3 succeeds
- **THEN** the client connects with protocol 3 and later connections to that endpoint start with protocol 3.

#### Scenario: Connection is refused or a protocol is pinned
- **WHEN** the server refuses the connection, returns malformed data, or the caller pinned a protocol
- **THEN** no fallback attempt is made and the original error is reported.

### Requirement: Tolerant saved state
Loading saved state SHALL keep every valid setting and scene when other fields are unknown or invalid, and SHALL keep an unreadable file before replacing it.

#### Scenario: State from a newer release
- **WHEN** saved state contains an unknown key or effect value
- **THEN** valid settings and scenes are loaded and the unknown values fall back to defaults.

#### Scenario: Unreadable state file
- **WHEN** the state file is not a JSON object and the user changes a setting
- **THEN** the old file is renamed to `state.json.corrupt-<time>` before the new state is written.

### Requirement: Shared SDK endpoint recovery
A device failure that closes a shared SDK socket SHALL NOT put other devices on that endpoint into retry delay.

#### Scenario: One device drops the endpoint socket
- **WHEN** a device write fails and closes its endpoint socket
- **THEN** other devices on that endpoint report a reconnect, the endpoint is refreshed on the next loop, and they are applied after reconnection.

### Requirement: Narrow Arch dependency installation
Hardware setup on Arch SHALL request only missing build packages and SHALL NOT install core system packages.

#### Scenario: Core package missing
- **WHEN** `systemd` or `python` is not installed
- **THEN** setup stops and asks for a full system upgrade without running pacman.

### Requirement: First-run panel and failure polling
The panel SHALL open on Setup while setup is required and SHALL slow status polling while the backend keeps failing.

#### Scenario: Setup required on open
- **WHEN** the panel opens and the backend reports that setup is needed
- **THEN** the Setup tab is shown unless the user has already chosen a tab.

#### Scenario: Backend unavailable
- **WHEN** consecutive status reads fail
- **THEN** the poll interval doubles up to 30 seconds and returns to 4 seconds after a success or user action.
