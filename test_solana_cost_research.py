import base64
import unittest
from solana_cost_research import unsigned_message,rpc


class UnsignedSimulationTests(unittest.TestCase):
    def test_extracts_message_without_signing(self):
        message=b'\x80example'
        self.assertEqual(unsigned_message(base64.b64encode(b'\x01'+bytes(64)+message)),base64.b64encode(message).decode())

    def test_rejects_signed_and_truncated_payloads(self):
        for raw in (b'\x01'+b'\x01'+bytes(63)+b'msg',b'\x01',b'\x80\x80\x80'):
            with self.assertRaises(ValueError):
                unsigned_message(base64.b64encode(raw))

    def test_broadcast_and_sign_methods_blocked(self):
        for method in ('sendTransaction','sendRawTransaction','signTransaction'):
            with self.assertRaises(ValueError):
                rpc(method,[])
