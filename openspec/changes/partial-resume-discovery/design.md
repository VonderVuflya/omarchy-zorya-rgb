## Decision
A listening SDK and nonzero controller count are not sufficient to establish resume readiness. When the selected inventory is still incomplete after five seconds, restart only the owned OpenRGB unit once so its hardware detector runs after I2C/USB settling. Refresh the SDK afterward through the existing readiness callback. Empty and partial inventory paths share one retry budget; permanently absent devices cannot trigger a restart loop. Existing bounded partial-device fallback remains in place.

## Evidence
On2026-10-16 the09:43 resume scan returned keyboard/mouse/motherboard, while RAM and GPU were absent. Current I2C ACLs were readable/writable for the user. One later OpenRGB restart rediscovered both missing controllers and restored all seven stable IDs without changing selection.
