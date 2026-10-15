## ADDED Requirements

### Requirement: Continuous color dragging
The color wheel SHALL retain pointer capture inside scrolling content and SHALL send coalesced color changes during continuous movement, with the final selected color sent on release.

#### Scenario: Continuous pointer movement
- **WHEN** the user drags across the wheel without pausing
- **THEN** the marker follows the pointer and multiple bounded updates reach the backend before the drag ends.

### Requirement: Rounded themed controls
The panel SHALL use rounded theme-aware controls with visible keyboard focus, hover, selected and disabled states.

#### Scenario: Theme controls
- **WHEN** the user opens the panel
- **THEN** actions, tabs and selection controls use consistent rounded surfaces and readable foregrounds.

### Requirement: Widget-anchored panel
The panel SHALL open adjacent to its bar widget and stay within screen margins instead of centering across the bar.

#### Scenario: Widget on the right of the top bar
- **WHEN** the user opens Zorya from the right-hand bar widget
- **THEN** the panel appears beneath that widget and is clamped to the screen edge.
