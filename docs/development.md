# Development notes

Use the exact pinned OpenSpec version from package-lock.json. OpenSpec is development tooling and is excluded from the installed Python/QML runtime. The npm registry currently reports an upstream braces stack-exhaustion advisory through its globbing dependencies with no patched braces release available. Do not pass untrusted glob expressions to the development tool; track the upstream fix before widening its use to an exposed service.

Validate the installed or a clean exported plugin folder. Running Omarchy validation directly on a checkout containing node_modules fails because npm uses executable symlinks; those ignored development dependencies are not shipped in the plugin.

The GitHub Actions workflow is kept in `ci/github-actions.yml` until it is moved to `.github/workflows/checks.yml` with a token that has workflow permission. Once active it runs on pull requests, `main` and release tags: the Python suite with the pinned SDK on Python 3.11 and 3.14, compilation, `scripts/check-versions.py`, whitespace checks and strict OpenSpec validation. Changing workflow files requires a token with workflow permission (`gh auth refresh -h github.com -s workflow`). QML validation needs an installed Omarchy shell and remains a local check (`python scripts/check-qml.py`).
