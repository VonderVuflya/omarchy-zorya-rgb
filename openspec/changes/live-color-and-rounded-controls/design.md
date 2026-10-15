## Decisions
The wheel MouseArea prevents a parent Flickable from stealing its active drag. Focus is acquired once on press. Release/cancellation flushes the pending color.

The existing 120 ms timer becomes a throttle: start when idle, never restart on each incoming edit. Existing serialized actions and coalescing preserve the latest pending color without queuing every pointer event. Optimistic local state keeps the cursor and swatch immediate; stale remote reads remain guarded by the edit revision.

Theme-aware rounded controls replace default Fusion chrome, preserving keyboard focus, hover, pressed, selected and disabled affordances.

## Verification
Reproduce drag loss inside a real Qt ScrollView and continuous-edit starvation through the actual Quickshell Process service. Assert intermediate writes, bounded write count and the final color. Check QML and the native shell panel after installation.
