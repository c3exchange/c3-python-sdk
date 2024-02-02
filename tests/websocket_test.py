import asyncio
import logging
import os
import time
import unittest

from c3.c3exchange import C3Exchange
from c3.signing.signers import AlgorandMessageSigner
from c3.websocket import TopicType, WebSocketClient, WebSocketClientEvent


class TestWebSockets(unittest.IsolatedAsyncioTestCase):
    async def test_should_connect_sdk(self):
        logging.basicConfig(
            format="%(message)s",
            level=logging.DEBUG,
        )
        base_url = "http://localhost:3000/"
        account_mnemonic = os.environ["TEST_ACCOUNT_MNEMONIC"]
        delegatedAccount = os.environ["DELEGATED_ACCOUNT"]
        signer = AlgorandMessageSigner.from_mnemonic(mnemonic_string=account_mnemonic)
        c3_client = C3Exchange(base_url)
        account = c3_client.login(
            signer, None, "C3_UAA345IZ3DNZZXWFECA25M2RJ7S3AWUQZQ3OMBKUIVSQEWDWAYHL5UP7"
        )
        print(account)
        client = WebSocketClient(
            base_url, account_id=delegatedAccount, jwt_token=account.apiToken
        )

        connected = False
        stop = False

        @client.on(WebSocketClientEvent.Level1)
        async def level1(data):
            print(f"L1 Data : {data}")

        @client.on(WebSocketClientEvent.Connect)
        async def connect():
            nonlocal connected
            connected = True
            print("Connected")

        @client.on(WebSocketClientEvent.Cancels)
        async def handle_ws_cancels(cancels):
            print("WebSocket Cancels", cancels)

        @client.on(WebSocketClientEvent.Trades)
        async def handle_trade_event(trades):
            print("Some Order got filled", trades)

        # Open Order event is raised every time a new order is placed on connected account
        @client.on(WebSocketClientEvent.OpenOrders)
        async def handle_open_order_event(orders):
            print("Some Order got filled", orders)

        #        @client.on(WebSocketClientEvent.L1MarketData)
        #        async def print_mkt_data(data):
        #            print("Mkt Data", data)
        try:
            client.start()
            await asyncio.sleep(0.5)
            await client.list_subscriptions()
            await asyncio.sleep(0.5)
            await client.subscribe_to_market("ETH-USDC", TopicType.level1)
            await asyncio.sleep(6000)

        except Exception as error:
            print(f"Something failed {error}")
        #        await client.subscribe_to_market("ETH-USDC")
        #        await client.subscribe_to_market("AVAX-USDC")

        retry = 5
        while not stop:
            await asyncio.sleep(1)
            --retry


if __name__ == "__main__":
    unittest.main()
