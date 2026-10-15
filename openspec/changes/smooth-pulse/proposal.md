## Why
Software pulse sampled at two FPS creates visible brightness steps. The GPU incorrectly falls back to software at reduced brightness despite native Pulse support. Lian Li controllers can play buffered frames but drift recovery must preserve the entire animation.

## What Changes
- Use native pulse with color-scaled brightness when no hardware brightness control exists.
- Upload bounded, smoothly sampled pulse loops to compatible Lian Li wireless controllers.
- Preserve complete buffered animation during bridge RGB recovery and expose support through read-only IPC.
- Allow up to 30 FPS software fallback for explicit USB/HID devices, retaining conservative limits for I2C/RF/unknown transports.

## Impact
Backend, effect helper, bundled bridge supplement and tests; no cooling-curve changes.
