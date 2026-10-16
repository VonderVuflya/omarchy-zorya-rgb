## Why
The pinned SDK loops forever on EOF while reading controller data. Unauthenticated loopback peers and failing hardware endpoints must not monopolize the lighting worker. Review also found an exception bypass of resume deadlines and unsafe adoption of full-mode cooling services.

## What Changes
- Inject bounded SDK transport before the first network operation, without modifying the installed dependency.
- Reject truncated/oversized/malformed responses and bound discovery, nested callbacks and parser allocations.
- Preserve bounded resume recovery when discovery raises.
- Refuse full-mode Lian Li adoption before mutations.

## Impact
Core remains dependency-light; transport imports the optional SDK lazily. Protocol negotiation fails closed for nonresponsive legacy peers. Loopback identity remains unauthenticated.
