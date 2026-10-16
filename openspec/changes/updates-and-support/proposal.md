## Why
Users cannot discover and apply Zorya releases from the panel, and raw JSON diagnostics do not provide a usable bug-reporting workflow. Transient failures may disappear before the panel opens, losing the context needed to investigate.

## What Changes
- Check stable GitHub Releases and show an update arrow for a newer version.
- Explicit release-tag deployment updates UI and runtime together with backups and rollback.
- Retain the last hardware error and exception traceback while the daemon runs.
- Replace raw Details with a sanitized Markdown report preview, full-report copy and user-submitted prefilled GitHub issue.
- Include the previously agreed merged-branch cleanup rule in contributor instructions.

## Impact
No automatic installation, issue publication, hardware setup or AI execution. Release checking uses network requests; diagnostic collection stays local until the user opens the GitHub form.
