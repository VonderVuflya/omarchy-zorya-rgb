## Decisions
Use a per-client subclass adapter for pinned SDK 0.3.6, including constructor negotiation. Exact reads detect EOF and use a monotonic deadline shared across each discovery/update operation. Limit packets to 1 MiB, controllers to 256, notifications to 32, callback nesting to 8 and active mode palettes to 65535 colors. Preflight matrix/segment allocation dimensions before invoking the SDK parser. Preserve valid per-LED GPU modes with unused palette metadata.

Disconnect on protocol failure and release request locks. Do not globally patch the SDK. Continue to use existing reconnect and resume coordination; catching discovery failures must not extend its deadline. Full-mode Lian Li services cannot safely be converted into RGB-only wrappers, so setup refuses before any mutation, including for existing managed units.

## Validation
Subprocess reproduction verifies the original SDK hangs on a fake peer EOF without hanging the test runner. Tests cover initial/later requests, fragments, slow streams, nested notifications, oversized allocations, cleanup and reconnection. Independent implementation, adversarial testing and final review were performed. Live SDK reads cover protocols 1 and 4; physical suspend is not automated.
