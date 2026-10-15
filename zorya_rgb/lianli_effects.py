"""Upload a bounded pulse loop to compatible wireless firmware, once per scene."""
import re
import logging
from .effects import frame


def start_pulse(device, state, *, ipc=None):
    if not state['on'] or state['effect'] != 'pulse':
        return False
    name = str(getattr(device, 'name', '')).lower()
    if not (name.startswith('hydroshift ii ') or name.startswith('uni fan tl wireless')):
        return False
    location = getattr(device, 'location', None)
    if location is None:
        location = getattr(getattr(getattr(device, 'data', None), 'metadata', None), 'location', '')
    match = re.fullmatch(r'HID:\s*(wireless:(?:[0-9a-f]{2}:){5}[0-9a-f]{2})', str(location), re.I)
    count = len(getattr(device, 'leds', []))
    if not match or not 1 <= count <= 255:
        return False
    if ipc is None:
        from .hardware import _lianli_ipc
        ipc = _lianli_ipc
    try:
        # Old bridge builds upload frames but can replace them with a static
        # frame during RGB drift recovery. Use onboard playback only after
        # verifying the complete-animation replay fix is present.
        support = ipc('GetRgbAnimationSupport')
        if not isinstance(support, dict) or support.get('replay_safe') is not True:
            return False
        period = 1 / state['speed']
        max_frames = min(160, 48000 // (count * 3))
        samples = max(8, min(max_frames, round(period * 30)))
        interval_ms = max(1, round(period * 1000 / samples))
        frames = [frame(state, count, i * period / samples) for i in range(samples)]
        ipc('SetRgbFrames', {'device_id': match.group(1).lower(),
                            'frames': frames, 'interval_ms': interval_ms}, timeout=5)
        logging.getLogger(__name__).info('Buffered pulse uploaded: %s, %d frames, %d ms', device.name, samples, interval_ms)
        return True
    except (OSError, ValueError, RuntimeError):
        return False  # The SDK fallback remains available on older/offline bridges.
