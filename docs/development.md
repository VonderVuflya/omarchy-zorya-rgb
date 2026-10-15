# Development notes

Use the exact pinned OpenSpec version from package-lock.json. OpenSpec is development tooling and is excluded from the installed Python/QML runtime. The npm registry currently reports an upstream braces stack-exhaustion advisory through its globbing dependencies with no patched braces release available. Do not pass untrusted glob expressions to the development tool; track the upstream fix before widening its use to an exposed service.

Validate the installed or a clean exported plugin folder. Running Omarchy validation directly on a checkout containing node_modules fails because npm uses executable symlinks; those ignored development dependencies are not shipped in the plugin.

The GitHub Actions template is included in `ci/github-actions.yml`. To activate it, copy it to `.github/workflows/ci.yml` and push using credentials with workflow permission (`gh auth refresh -h github.com -s workflow`). The initial authenticated token could publish source but lacked workflow permission, so the template is provided without an active remote workflow.
