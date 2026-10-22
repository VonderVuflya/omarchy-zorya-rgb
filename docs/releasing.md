# Development and releases

All code, fixes and features are developed on branches and reviewed through pull requests. Technical decisions, changed behavior and acceptance criteria live in OpenSpec alongside the implementation. Update the specification if review changes a decision. PR descriptions explain the final behavior and relevant verification briefly.

A release requires authorization to publish, a reviewed PR and successful checks. Resolve important review findings, merge the PR, and use its resulting commit on `main`. Do not merge solely because a PR was requested.

1. In the PR, update the version consistently in `manifest.json`, `pyproject.toml`, `zorya_rgb/__init__.py`, `package.json` and the root entries in `package-lock.json`; `python scripts/check-versions.py [vX.Y.Z]` checks them and the tag. Record verification limits, including any untested clean hardware build or physical suspend.
2. Run the Python suite with the pinned hardware SDK, strict OpenSpec validation, QML validation, Python compilation and whitespace checks. Validate the plugin manifest against the installed Omarchy shell. CI activation is separate from local verification; never report remote CI if it did not run.
3. After review and authorized merge, confirm the PR is merged, switch to and update `main`, and delete the merged remote and local feature/fix branches. Preserve uncommitted work and branches needed by another open PR or worktree; complete their cleanup when no longer needed. Keep `main` and release tags. Create an annotated `vX.Y.Z` tag pointing to it. Push that tag.
4. Create a GitHub Release from the tag. Notes describe user-facing improvements/fixes, setup or compatibility changes and material validation limits. Link the PR. The tag, release and package versions must agree.
5. Verify the remote tag/release and report their links. Marketplace submission changes and issue comments require their own explicit authorization.

A requested PR can remain open for review. In that case prepare release notes as a draft and do not create a final release/tag until the PR is merged. Do not publish an unmerged branch as a release.
