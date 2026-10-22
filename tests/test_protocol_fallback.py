import unittest
from zorya_rgb import sdk_transport


class ProtocolFallbackTests(unittest.TestCase):
    def setUp(self):
        sdk_transport._fallback_endpoints.clear()
        self.addCleanup(sdk_transport._fallback_endpoints.clear)

    def patch_connect(self,outcome):
        calls=[]
        def fake(address,port,name,version):
            calls.append(version); result=outcome(version)
            if isinstance(result,Exception): raise result
            return result
        original=sdk_transport._connect_once; sdk_transport._connect_once=fake
        self.addCleanup(setattr,sdk_transport,'_connect_once',original)
        return calls

    def test_default_protocol_timeout_retries_with_protocol_3_and_caches(self):
        calls=self.patch_connect(lambda v:'client' if v==3 else TimeoutError('timed out'))
        self.assertEqual(sdk_transport.connect_client('127.0.0.1',6742),'client')
        self.assertEqual(sdk_transport.connect_client('127.0.0.1',6742),'client')
        self.assertEqual(calls,[None,3,3])
        sdk_transport._fallback_endpoints[('127.0.0.1',6742)]-=sdk_transport.FALLBACK_TTL
        sdk_transport.connect_client('127.0.0.1',6742); self.assertEqual(calls,[None,3,3,None,3])

    def test_pinned_protocol_is_never_retried(self):
        calls=self.patch_connect(lambda v:TimeoutError('timed out'))
        with self.assertRaises(TimeoutError): sdk_transport.connect_client('127.0.0.1',6743,protocol_version=1)
        self.assertEqual(calls,[1])

    def test_refused_or_malformed_connection_is_not_retried(self):
        for error in (ConnectionRefusedError(),ValueError('Invalid signature')):
            calls=self.patch_connect(lambda v:error)
            with self.assertRaises(type(error)): sdk_transport.connect_client('127.0.0.1',6742)
            self.assertEqual(calls,[None])

    def test_wrapped_negotiation_timeout_is_retried(self):
        def outcome(version):
            if version==3: return 'client'
            try: raise TimeoutError('timed out')
            except TimeoutError as exc:
                try: raise ConnectionError('Invalid or incomplete OpenRGB response') from exc
                except ConnectionError as wrapped: return wrapped
        calls=self.patch_connect(outcome)
        self.assertEqual(sdk_transport.connect_client('127.0.0.1',6742),'client'); self.assertEqual(calls,[None,3])

    def test_server_closing_during_negotiation_is_retried(self):
        calls=self.patch_connect(lambda v:'client' if v==3 else EOFError('OpenRGB server closed an incomplete packet'))
        self.assertEqual(sdk_transport.connect_client('127.0.0.1',6742),'client'); self.assertEqual(calls,[None,3])

    def test_both_protocols_failing_raises_and_clears_cache(self):
        calls=self.patch_connect(lambda v:TimeoutError('v'+str(v)))
        with self.assertRaisesRegex(TimeoutError,'vNone'): sdk_transport.connect_client('127.0.0.1',6742)
        self.assertEqual(calls,[None,3]); self.assertFalse(sdk_transport._fallback_endpoints)
        sdk_transport._fallback_endpoints[('127.0.0.1',6742)]=sdk_transport.time.monotonic()
        with self.assertRaises(TimeoutError): sdk_transport.connect_client('127.0.0.1',6742)
        self.assertFalse(sdk_transport._fallback_endpoints)
