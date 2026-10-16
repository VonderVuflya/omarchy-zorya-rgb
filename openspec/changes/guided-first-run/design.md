## Scope and decisions
Extend the existing QML Setup and Python installers rather than introduce a second installation service. Use separate read-only assessment and explicitly invoked operations. The repository launcher uses private Python when available and system Python to bootstrap otherwise; no optional SDK import is needed for core startup.

### CLI and UI contract
`onboarding plan` returns a summary, readiness, diagnostics and ordered steps: runtime, openrgb, lianli, verify. Each step has an id, label, description, status (`ready`, `needed`, `blocked`, `skipped`) and required flag. `onboarding run --step ID` performs only the named operation and returns a JSON result, error and optional hint/devices. The UI owns sequencing and reports actual step completion rather than a simulated percentage. Diagnosis is independent of the daemon status process so an absent runtime cannot block first-use assessment.

### Readiness and reuse
Availability of a binary alone is not readiness. Inspect the private runtime and user daemon and probe bounded SDK discovery. Healthy existing services, including compatible external endpoints, can be reused without replacing them. When installation would encounter a full-mode cooling/LCD service, explain the block and preserve it. On a supported Lian Li-only system, a healthy bridge inventory makes an empty or absent OpenRGB endpoint optional; users can install OpenRGB explicitly from advanced tools later. Pairing and Kingston compatibility work remain explicit advanced operations. Closing the panel does not terminate a running setup operation.

### Confirmation, errors and retries
Show planned changes and the possibility of package downloads, build time and system authorization before the Start action. Never install on load/poll. Sequential steps stop at the first error; retain that error separately from periodic status. Reassess on Retry and skip healthy/completed stages. If reassessment adds a new action or changes its description, display the updated plan and require another Start click before running it. Serialize pending lighting writes and regular actions with assessment/setup; keep explicit edits queued until setup stops. Verification reports SDK-discovered devices, not visual proof of LEDs. Route users to explicit device selection and allow a separate explicit action using the existing forced `restore` operation to reapply their current scene, even if its saved color is unchanged. No automatic color or selection changes.

### Runtime lifecycle
The wizard's runtime-only installer prepares the private environment and daemon without implicit hardware adoption or widget re-registration. This avoids replacing the live bootstrap UI mid-operation. Existing explicit full installer remains compatible. No new automatic cooling management or hardware restart policy is introduced.

### Contribution and release workflow
All technical decisions and changed behavior belong in OpenSpec. All code changes use a branch and reviewed PR with concise behavior/checks/spec links. Release versions agree across package/manifest metadata. Annotated tags and GitHub Releases point to reviewed merged main commits; an open PR gets prepared notes, not a premature final release. Marketplace comments/submission updates remain separately authorized.

## Verification
Test read-only assessment without filesystem/service mutations, missing runtime, healthy reuse, blocked cooling services, individual stage errors, retry and unsupported IDs. Exercise actual QML Process sequencing with a fake CLI offscreen, including stale polling and failure retention. Validate the production QML/manifest against the installed shell. No clean hardware build or physical suspend is implied by mocked installer tests.
