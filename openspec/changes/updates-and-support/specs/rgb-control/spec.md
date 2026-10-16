## ADDED Requirements

### Requirement: Release-aware updates
The widget SHALL check stable upstream releases and offer a version-specific update only for a newer release.

#### Scenario: Network check fails
- **WHEN** GitHub is unreachable or returns invalid data
- **THEN** the check reports failure with bounded retry traffic and lighting controls remain usable.

#### Scenario: Installed version is newer than latest release
- **WHEN** a development installation is ahead of the stable release
- **THEN** no downgrade button is shown.

### Requirement: Transactional explicit release installation
An explicitly confirmed update SHALL deploy the exact proposed release to UI and runtime, preserve state and roll back on failure.

#### Scenario: Local edits or changed release dependencies
- **WHEN** updating would overwrite git edits or require different dependencies
- **THEN** installation refuses with an actionable explanation before swapping files.

#### Scenario: New daemon fails health verification
- **WHEN** the new source does not produce a daemon reporting the expected runtime version
- **THEN** both source snapshots are restored and the previous daemon is restarted.

### Requirement: Useful private diagnostic drafts
Errors SHALL remain available after recovery, and users SHALL be able to preview and copy a sanitized report and explicitly open a prefilled GitHub issue.

#### Scenario: Transient error clears before panel opens
- **WHEN** the hardware worker recovers after a failure
- **THEN** status still exposes the last error context for reporting without keeping the current lighting state in error.

#### Scenario: Report contains sensitive diagnostic strings
- **WHEN** a report is prepared
- **THEN** credentials, device identities and user paths are removed, the full Markdown is private and nothing is automatically published.

#### Scenario: Full report exceeds URL capacity
- **WHEN** the encoded GitHub draft would exceed its bound
- **THEN** the form contains a visible truncation notice and the user can copy the full report.

#### Scenario: User explicitly submits the full reviewed report
- **WHEN** gh is available and the user clicks Create GitHub issue after preview
- **THEN** only the full report matching that preview fingerprint is submitted to the fixed Zorya repository and repeated submission returns the existing issue link.

#### Scenario: Report changes or submission outcome is uncertain
- **WHEN** the saved report no longer matches the preview or an earlier request might have created an issue
- **THEN** automatic retry is refused and the user receives a clear recovery action.
