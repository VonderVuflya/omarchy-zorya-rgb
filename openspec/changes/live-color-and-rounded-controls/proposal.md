## Why
Dragging the color wheel inside the panel loses its mouse grab to ScrollView. Restarting a debounce timer for each pointer event also delays all hardware updates until motion stops. Default Fusion buttons look square and inconsistent with other Omarchy extensions.

## What Changes
- Retain the wheel mouse grab and flush the last selected color on release.
- Send coalesced color changes at bounded intervals during continuous movement.
- Round themed action controls, tabs and dropdown surfaces with clear interaction states.

## Impact
QML only; backend, fan curves and selected scenes remain compatible.
