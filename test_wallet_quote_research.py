import unittest
from unittest.mock import patch
import wallet_quote_research as w


class ReadOnlyQuotesTests(unittest.TestCase):
    def test_rpc_rejects_sending(self):
        for method in ('eth_sendTransaction','eth_sendRawTransaction','eth_sign'):
            with self.assertRaises(ValueError):
                w.rpc(method,[])

    def test_abi_path(self):
        result=w.encode_amounts(1,[w.BCOIN,w.WBNB])
        self.assertTrue(result.startswith('0xd06ca61f'))
        self.assertEqual(len(result),10+5*64)

    def test_invalid_amount_and_path(self):
        for amount,path in ((0,[w.BCOIN,w.WBNB]),(1,['bad','bad'])):
            with self.assertRaises(ValueError):
                w.encode_amounts(amount,path)

    def test_rejects_wrong_quote(self):
        with patch.object(w,'get_json',return_value={'inputMint':'wrong','outAmount':'1'}):
            with self.assertRaises(ValueError):
                w.quote_sol(w.GRASS,w.USDC,1000)
