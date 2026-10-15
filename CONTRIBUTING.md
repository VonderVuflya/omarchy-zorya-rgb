# Contributing

Use OpenSpec for behavior changes. Start with a proposal, concrete requirements/scenarios, design tradeoffs and tasks. Update the compatibility and verification notes with evidence.

Run Python tests, OpenSpec validation, Omarchy manifest validation and QML checks appropriate to your changes. SDK fixtures should resemble the real `openrgb-python` object shape and capability flags. Include failure tests for disconnected hardware, malformed state, partial discovery, suspend recovery and installer rollback.

Avoid personal paths, access tokens and raw hardware serials in source, fixtures or public reports. Keep third-party source pins, patches and license notices together. Do not silently broaden hardware writes or package installation behavior.

Marketplace publication uses the [official submission form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml). Source publication and marketplace listing are separate operations; a listing is subject to maintainer review.
