"""Bounded adversarial SDK checks; only ephemeral loopback sockets are used.

Each SDK scenario runs in a disposable process. A regression in the upstream
EOF loop is killed by the parent's wall-clock timeout, not left as a worker.
Run with the optional pinned hardware extra to exercise the actual SDK.
"""
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
import unittest

try:
    import openrgb  # noqa: F401
except ImportError:
    openrgb = None

ROOT = Path(__file__).resolve().parents[1]


def _exact(sock, length):
    data = b''
    while len(data) < length:
        part = sock.recv(length - len(data))
        if not part:
            raise EOFError('client closed')
        data += part
    return data


def _header(kind, length, device=0):
    return struct.pack('<4sIII', b'ORGB', device, kind, length)


def _scenario(name, original=False):
    """Actual SDK discovery against a small, deterministic ORGB peer."""
    from openrgb import OpenRGBClient, utils
    if original:
        connect = OpenRGBClient
    else:
        from zorya_rgb import sdk_transport
        sdk_transport.PACKET_TIMEOUT = 0.80 if name == 'fragmented' else 0.20
        connect = sdk_transport.connect_client

    metadata = utils.MetaData('Fixture vendor', 'Test device', '1', '', 'loopback fixture')
    mode = utils.ModeData(0, 'Static', 0, utils.ModeFlags(0), None, None,
                          None, None, None, None, None, None, None,
                          utils.ModeColors.PER_LED, None)
    zone = utils.ZoneData('Fixture zone', utils.ZoneType.LINEAR,
                          1, 1, 1, 0, 0, segments=[])
    fixture = utils.ControllerData(
        'Fixture controller', metadata, utils.DeviceType.UNKNOWN,
        [utils.LEDData('Fixture LED', 0)], [zone], [mode],
        [utils.RGBColor(10, 20, 30)], 0).pack(4)
    if name in ('matrix_height', 'segment_length'):
        # Wire scalars are packed separately to avoid native alignment padding.
        prefix = (struct.pack('<i', utils.DeviceType.UNKNOWN)
                  + utils.pack_string('Hostile controller') + metadata.pack(4)
                  + struct.pack('<HiH', 0, 0, 1))
        malicious_zone = (utils.pack_string('Hostile zone')
                          + struct.pack('<iIIIH',
                                        utils.ZoneType.MATRIX if name == 'matrix_height'
                                        else utils.ZoneType.LINEAR, 0, 0, 0, 0))
        if name == 'matrix_height':
            malicious_zone += struct.pack('<IIH', 0xffffffff, 0, 0)
        else:
            malicious_zone += (struct.pack('<H', 1)
                               + utils.pack_string('Hostile segment')
                               + struct.pack('<iII', utils.ZoneType.LINEAR, 0, 0xffffffff))
        data = prefix + malicious_zone + struct.pack('<HH', 0, 0)
        fixture = struct.pack('<I', len(data) + 4) + data
    if name in ('palette_huge', 'palette_inverted', 'palette_redundant'):
        mode = utils.ModeData(0, 'Hostile palette', 0, utils.ModeFlags(64 | 32),
                              None, None, None, None, 1, 1, None, None, None,
                              utils.ModeColors.MODE_SPECIFIC, [utils.RGBColor(1, 2, 3)])
        fixture = bytearray(utils.ControllerData(
            'Fixture controller', metadata, utils.DeviceType.UNKNOWN,
            [], [], [mode], [], 0).pack(4))
        offset = fixture.index(utils.pack_string('Hostile palette'))
        offset += len(utils.pack_string('Hostile palette'))
        struct.pack_into('<II', fixture, offset + 24,
                         2 if name == 'palette_inverted' else 1,
                         1 if name == 'palette_inverted' else 0xffffffff)
        if name == 'palette_redundant':
            struct.pack_into('<I', fixture, offset + 44, utils.ModeColors.PER_LED)
        fixture = bytes(fixture)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(1)
    port = listener.getsockname()[1]
    errors = []
    ready_for_update = threading.Event()

    def serve():
        try:
            with listener, listener.accept()[0] as peer:
                peer.settimeout(1)
                peer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                while True:
                    signature, device, kind, size = struct.unpack('<4sIII', _exact(peer, 16))
                    if signature != b'ORGB':
                        raise AssertionError('invalid client signature')
                    _exact(peer, size)
                    if kind == 50:
                        continue
                    if kind == 40:
                        payload = struct.pack('<I', 4)
                    elif kind == 0:
                        payload = struct.pack('<I', 0xffffffff if name == 'excess_count' else
                                              2 if name in ('slow_constructor', 'slow_update') else 1)
                    elif kind == 1:
                        payload = fixture
                    elif kind in (150, 200):
                        payload = struct.pack('<IH', 6, 0)
                    else:
                        raise AssertionError(f'unexpected request {kind}')
                    packet = _header(kind, len(payload), device) + payload
                    if name == 'slow_constructor' or (name == 'slow_update' and ready_for_update.is_set()):
                        time.sleep(0.075)
                    if name == 'nested_notification' and kind == 0:
                        time.sleep(0.075)
                        peer.sendall(_header(100, 0))
                    if name == 'notification_flood' and kind == 0:
                        peer.sendall(_header(100, 0) * 40)
                        return
                    if name in ('profile_eof', 'plugin_eof') and kind == (150 if name == 'profile_eof' else 200):
                        peer.sendall(packet[:18])
                        return
                    if name == 'negotiation_eof' and kind == 40:
                        return
                    if name == 'negotiation_body_eof' and kind == 40:
                        peer.sendall(packet[:18])
                        return
                    if name == 'header_eof' and kind == 1:
                        peer.sendall(packet[:7])
                        return
                    if name in ('body_eof', 'later_eof') and kind == 1:
                        if name == 'body_eof' or ready_for_update.is_set():
                            peer.sendall(packet[:20])
                            if original:
                                print('controller body truncated after advertised size',
                                      file=sys.stderr, flush=True)
                            return
                    if name == 'excess_body' and kind == 1:
                        peer.sendall(_header(kind, 0xffffffff, device))
                        # Keep the peer open: the announced size must be rejected
                        # before attempting to wait for or allocate its body.
                        try:
                            peer.recv(1)
                        except socket.timeout:
                            pass
                        return
                    if name == 'bad_signature' and kind == 1:
                        peer.sendall(b'NOPE' + packet[4:])
                        return
                    if name == 'slow_trickle' and kind == 1:
                        for byte in packet:
                            peer.sendall(bytes([byte]))
                            time.sleep(0.04)
                        return
                    if name == 'fragmented':
                        for start in range(0, len(packet), 3):
                            peer.sendall(packet[start:start + 3])
                            time.sleep(0.001)
                    else:
                        peer.sendall(packet)
        except (EOFError, BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            errors.append(repr(exc))

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    client = None
    started = time.monotonic()
    try:
        client = connect('127.0.0.1', port, name='ZoryaRGB test')
        if name in ('later_eof', 'slow_update'):
            ready_for_update.set()
            started = time.monotonic()
            try:
                client.update()
            except Exception:
                if client.comms.connected or client.comms.lock.locked():
                    raise AssertionError('failed update left socket or SDK lock active')
                raise
        result = {'ok': True, 'names': [d.name for d in client.devices],
                  'protocol': client.comms._protocol_version,
                  'colors': [[c.red, c.green, c.blue] for c in client.devices[0].colors],
                  'modes': [m.name for m in client.devices[0].modes]}
    except Exception as exc:
        result = {'ok': False, 'error': type(exc).__name__, 'message': str(exc)}
    finally:
        elapsed = time.monotonic() - started
        if client is not None:
            client.comms.stop_connection()
        worker.join(1.1)
    result.update(elapsed=elapsed, server_errors=errors, worker_alive=worker.is_alive())
    return result


@unittest.skipIf(openrgb is None, 'openrgb-python hardware extra not installed')
class BoundedSdkTransportTests(unittest.TestCase):
    def run_scenario(self, name, *, original=False, timeout=2.5):
        command = [sys.executable, str(Path(__file__).resolve()), '--scenario', name]
        if original:
            command.append('--original')
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                 timeout=timeout)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertFalse(result['worker_alive'], result)
        self.assertEqual(result['server_errors'], [], result)
        return result

    def test_original_sdk_body_eof_is_externally_bounded_reproducer(self):
        # This proves socket.settimeout cannot bound an EOF busy loop. run()
        # kills and waits for the child when its independent deadline expires.
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            self.run_scenario('body_eof', original=True, timeout=0.8)
        self.assertIn(b'controller body truncated', caught.exception.stderr)

    def assert_rejected(self, scenario, reason=None):
        result = self.run_scenario(scenario)
        self.assertFalse(result['ok'], result)
        self.assertLess(result['elapsed'], 0.8, result)
        self.assertEqual(result['error'], 'OpenRGBDisconnected', result)
        if reason is not None:
            self.assertIn(reason, result['message'], result)

    def test_eof_during_protocol_negotiation(self):
        self.assert_rejected('negotiation_eof')

    def test_eof_in_protocol_version_body(self):
        self.assert_rejected('negotiation_body_eof')

    def test_eof_in_fragmented_controller_header(self):
        self.assert_rejected('header_eof')

    def test_eof_in_promised_controller_body(self):
        self.assert_rejected('body_eof')

    def test_later_update_eof_closes_socket_and_releases_lock(self):
        self.assert_rejected('later_eof')

    def test_excessive_announced_body_rejected_before_read(self):
        self.assert_rejected('excess_body', 'size limit')

    def test_excessive_controller_count_rejected_before_allocation(self):
        self.assert_rejected('excess_count', 'count exceeds limit')

    def test_invalid_signature_rejected(self):
        self.assert_rejected('bad_signature')

    def test_slow_trickle_cannot_extend_packet_deadline(self):
        self.assert_rejected('slow_trickle')

    def test_matrix_height_cannot_allocate_unbounded_rows(self):
        self.assert_rejected('matrix_height', 'matrix dimensions')

    def test_segment_length_cannot_allocate_unbounded_leds(self):
        self.assert_rejected('segment_length', 'segment length')

    def test_notification_flood_is_bounded(self):
        self.assert_rejected('notification_flood', 'notification limit')

    def test_eof_in_profile_body(self):
        self.assert_rejected('profile_eof')

    def test_eof_in_plugin_body(self):
        self.assert_rejected('plugin_eof')

    def test_constructor_shares_deadline_across_multiple_controllers(self):
        self.assert_rejected('slow_constructor')

    def test_later_update_shares_deadline_across_multiple_controllers(self):
        self.assert_rejected('slow_update')

    def test_nested_notification_callbacks_share_deadline(self):
        result = self.run_scenario('nested_notification')
        self.assertFalse(result['ok'], result)
        self.assertEqual(result['error'], 'OpenRGBDisconnected', result)
        self.assertLess(result['elapsed'], 0.40, result)

    def test_mode_palette_advertised_length_is_bounded(self):
        self.assert_rejected('palette_huge', 'palette')

    def test_mode_palette_minimum_cannot_exceed_maximum(self):
        self.assert_rejected('palette_inverted', 'palette')

    def test_redundant_gpu_palette_limits_preserve_per_led_mode(self):
        result = self.run_scenario('palette_redundant')
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['modes'], ['Hostile palette'])

    def test_fragmented_discovery_preserves_real_sdk_controller_data(self):
        result = self.run_scenario('fragmented')
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['names'], ['Fixture controller'])
        self.assertEqual(result['protocol'], 4)
        self.assertEqual(result['colors'], [[10, 20, 30]])
        self.assertEqual(result['modes'], ['Static'])

    def test_healthy_endpoint_remains_usable_after_failed_endpoint(self):
        result = self.run_scenario('reconnect')
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['names'], ['Fixture controller'])


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--scenario':
        sys.path.insert(0, str(ROOT))
        if sys.argv[2] == 'reconnect':
            failed = _scenario('body_eof')
            assert not failed['ok'], failed
            result = _scenario('healthy')
        else:
            result = _scenario(sys.argv[2], '--original' in sys.argv)
        print(json.dumps(result), flush=True)
    else:
        unittest.main()
