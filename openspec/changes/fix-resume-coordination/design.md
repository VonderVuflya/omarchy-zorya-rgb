## Decisions
The Lian Li bridge already re-execs itself on resume. Zorya must not concurrently send it SIGTERM: a signal received during shutdown can be lost across exec while systemd keeps waiting to stop it. Zorya restarts only its owned OpenRGB unit automatically; explicitly requested service restarts retain their manual semantics.

OpenRGB scans hardware at startup. A listening SDK with zero controllers is not ready, and SDK update cannot repeat hardware discovery. Wait three seconds for USB/I2C and retry an empty owned OpenRGB scan once after five seconds.

Waiting for every selected controller must be bounded. After a finite settling period, apply to available controllers, report absent selections, and rediscover them without endlessly restarting services.

## Validation
Reproduce simultaneous restart selection and empty scan with failing tests; test partial inventory after recovery failure and its later return. Verify live discovery, commands and fan telemetry without suspending the user's active session.
