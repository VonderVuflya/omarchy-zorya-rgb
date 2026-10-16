# ZoryaRGB contributor instructions

Read `openspec/changes/initial-zorya-rgb/design.md` and `docs/implementation-plan.md` before changes. Record externally visible changes in OpenSpec. Keep Python core standard-library based; `openrgb-python` is the hardware SDK dependency. Never embed personal absolute paths, access tokens, raw device serials in fixtures, or private state.

QtQuick UI runs inside Omarchy's existing shell process. Validate manifests and QML against the installed shell; never edit `/usr/share/omarchy`. Hardware setup is explicit, predictable, and reversible. Do not install packages or bind hardware on import, plugin load, or status polling. Never write SPD EEPROM. Cooling changes need an explicit user choice.

Test real failure modes using fixtures/mocked adapters before physical hardware. Keep sleep recovery separate from animation/render logic. One device failure must not block control of others. Preserve third-party patch attribution and licenses.

## Required development and release process

- Record every technical decision and behavior change in OpenSpec: proposal, design, testable requirements and implementation tasks. Update the applicable change when implementation or review changes the decision. Keep decisions with the code they explain.
- All features, fixes and other code changes go through a feature/fix branch and a GitHub pull request. Never commit or push directly to `main`. Include process/documentation changes in a PR as well.
- PR descriptions must be brief and concrete: the problem and resulting behavior, relevant checks and any remaining validation limits. Avoid conversational history and unsupported claims. Use the repository PR template.
- Before merging, complete appropriate automated checks and independent review; resolve important findings and update OpenSpec. Creating a PR does not by itself authorize merging or publishing: follow the user's current scope of authorization.
- After a PR is confirmed merged, delete its remote feature/fix branch and the corresponding local branch after switching away from it. Preserve any uncommitted work and branches still needed by another open PR or worktree; finish their cleanup when no longer needed. Never delete `main` or release tags.
- Every published version has a consistent version number, annotated `vX.Y.Z` Git tag and GitHub Release with concise user-facing notes. Create releases from the reviewed merged commit on `main`, never from an unmerged feature branch. See `docs/releasing.md`.
- Do not update marketplace submissions, issue comments or send messages on the user's behalf unless explicitly requested. A code release does not implicitly authorize those messages.
