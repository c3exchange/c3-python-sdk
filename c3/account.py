import base64
import time
from decimal import Decimal
from typing import Any, Dict

from Crypto.Hash import SHA512

from c3.api import ApiClient
from c3.signing.encode import encode_user_operation, encode_user_operation_base
from c3.signing.signers import MessageSigner, base64address
from c3.signing.types import (
    CancelSignatureRequest,
    OrderSignatureRequest,
    RequestOperation,
)
from c3.utils.constants import Constants, MainnetConstants, get_constants
from c3.utils.utils import amountToContract


class Account(ApiClient):
    def __init__(
        self,
        signer: MessageSigner,
        instrumentsInfo: Dict[str, Any],
        marketsInfo: Dict[str, Any],
        accountId: str = None,
        apiToken: str = None,
        base_url: str = MainnetConstants.API_URL,
        constants: Constants = None,
        primaryAccountAddress: str = None,
    ):
        super().__init__(base_url)

        self.accountId = accountId
        self.signer = signer
        # Set base64address based on the presence of primaryAccountAddress (delegation mode)
        self.base64address = (
            base64address(primaryAccountAddress)
            if primaryAccountAddress
            else signer.base64address()
        )
        self.address = signer.address()

        self.base_url = base_url
        self.Constants = constants if constants is not None else get_constants(base_url)

        self.instrumentsInfo = instrumentsInfo
        self.marketsInfo = marketsInfo

        self.lastNonceStored = int(round(time.time() * 1000))

        self.apiToken = apiToken
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.apiToken}",
            }
        )

    def generateOrderId(self, order_signature_request: OrderSignatureRequest):
        encodedOrder = encode_user_operation_base(order_signature_request)

        hash_obj = SHA512.new(truncate="256")
        hash_obj.update(encodedOrder)
        hashed_data = hash_obj.digest()

        orderId = base64.b64encode(hashed_data).decode("utf-8")
        return orderId

    def getBalance(self):
        return self.get(f"v1/accounts/{self.accountId}/balance")

    def submitOrder(self, orderParams: Dict[str, Any]):
        """
        Submits a new order to the trading system based on the specified parameters.

        It extracts market information using the 'marketId' from 'orderParams', calculates base and quote
        instrument information, and prepares the order data including the type, side,
        amount, and price of the order. The method handles both market and limit orders
        and computes values for buying and selling amounts, slot IDs, and max borrow/repay
        values as applicable. It also includes order signing and payload preparation
        before making a POST request to submit the order.

        Args:
            orderParams (Dict[str, Any]): A dictionary containing the parameters for the order.
                Expected keys include:
                    - marketId (str): Identifier of the market.
                    - type (str): Type of the order ('market' or 'limit').
                    - side (str): Side of the order ('buy' or 'sell').
                    - amount (str): Amount of the order.
                    - price (str, optional): Price of the order if it's a limit order.
                    - maxBorrow (str, optional): Maximum amount to borrow for the order.
                    - maxRepay (str, optional): Maximum amount to repay for the order.
                    - expiresOn (int, optional): Expiration timestamp of the order.
                    - clientOrderId (str, optional): Client-side identifier of the order.

        Returns:
            str: The response from the order submission, typically including the order id.

        Note:
            The method increments 'lastNonceStored' for each order and calculates
            expiration time if not specified. It also encodes and signs the order
            before submission. Ensure that all necessary keys are provided in
            'orderParams' to avoid errors.
        """

        marketId = orderParams["marketId"]

        baseId = self.marketsInfo[marketId]["baseInstrument"]["id"]
        quoteId = self.marketsInfo[marketId]["quoteInstrument"]["id"]

        baseInstrumentInfo = self.instrumentsInfo[baseId]
        quoteInstrumentInfo = self.instrumentsInfo[quoteId]

        orderData = {
            "type": orderParams["type"],
            "side": orderParams["side"],
            "amount": orderParams["amount"],
            "price": (
                orderParams["price"]
                if orderParams["type"] == "limit" and "price" in orderParams
                else None
            ),
        }

        if orderData["side"] == "buy":
            orderData["max_borrow"] = amountToContract(
                orderParams.get("maxBorrow", "0"), baseInstrumentInfo["asaDecimals"]
            )
            orderData["max_repay"] = amountToContract(
                orderParams.get("maxRepay", "0"), quoteInstrumentInfo["asaDecimals"]
            )
        else:
            orderData["max_borrow"] = amountToContract(
                orderParams.get("maxBorrow", "0"), quoteInstrumentInfo["asaDecimals"]
            )
            orderData["max_repay"] = amountToContract(
                orderParams.get("maxRepay", "0"), baseInstrumentInfo["asaDecimals"]
            )

        def _getBuySellValues(orderData: dict):
            values = {}
            if orderData["type"] == "market":
                values["buyAmount"], values["sellAmount"] = "0", "0"

                if orderData["side"] == "buy":
                    values["buySlotId"], values["sellSlotId"] = (
                        baseInstrumentInfo["slotId"],
                        quoteInstrumentInfo["slotId"],
                    )
                else:
                    values["buySlotId"], values["sellSlotId"] = (
                        quoteInstrumentInfo["slotId"],
                        baseInstrumentInfo["slotId"],
                    )

            # limit orders
            else:
                quoteAmount = Decimal(orderData["amount"]) * Decimal(orderData["price"])

                if orderData["side"] == "buy":
                    values["buyAmount"] = amountToContract(
                        orderData["amount"], baseInstrumentInfo["asaDecimals"]
                    )
                    values["buySlotId"] = baseInstrumentInfo["slotId"]

                    values["sellAmount"] = amountToContract(
                        quoteAmount, quoteInstrumentInfo["asaDecimals"]
                    )
                    values["sellSlotId"] = quoteInstrumentInfo["slotId"]

                else:
                    values["buyAmount"] = amountToContract(
                        quoteAmount, quoteInstrumentInfo["asaDecimals"]
                    )
                    values["buySlotId"] = quoteInstrumentInfo["slotId"]

                    values["sellAmount"] = amountToContract(
                        orderData["amount"], baseInstrumentInfo["asaDecimals"]
                    )
                    values["sellSlotId"] = baseInstrumentInfo["slotId"]

            return values

        values = _getBuySellValues(orderData)

        # to-do
        # validateOrder(orderParams)

        # one day if not specified
        expires_on = orderParams.get("expiresOn", int(time.time()) + 86400)
        client_order_id = orderParams.get("clientOrderId", "")

        order_nonce = self.lastNonceStored
        self.lastNonceStored += 1

        order_signature_request = OrderSignatureRequest(
            op=RequestOperation.Order,
            account=self.base64address,
            sell_slot_id=values["sellSlotId"],
            buy_slot_id=values["buySlotId"],
            sell_amount=values["sellAmount"],
            buy_amount=values["buyAmount"],
            max_sell_amount_from_pool=orderData["max_repay"],
            max_buy_amount_to_pool=orderData["max_borrow"],
            expires_on=expires_on,
            nonce=order_nonce,
            # NOTE: For orders, these should be zero
            last_valid=0,
            lease=bytearray(32),
        )

        encoded_order = encode_user_operation(order_signature_request)
        signature = self.signer.sign_message(encoded_order)

        orderPayload = {
            "marketId": marketId,
            "type": orderData["type"],
            "side": orderData["side"],
            "size": orderData["amount"],
            "price": orderData["price"],
            "clientOrderId": client_order_id,
            "sentTime": int(time.time()),
            "settlementTicket": {
                "account": self.base64address.decode("utf-8"),
                "sellSlotId": values["sellSlotId"],
                "buySlotId": values["buySlotId"],
                "sellAmount": str(values["sellAmount"]),
                "buyAmount": str(values["buyAmount"]),
                "maxSellAmountFromPool": "0",
                "maxBuyAmountToPool": "0",
                "expiresOn": expires_on,
                "nonce": order_nonce,
                "creator": self.address,
                "signature": signature,
            },
        }

        orderResponse = self.post(
            f"v1/accounts/{self.accountId}/markets/{marketId}/orders", orderPayload
        )

        return orderResponse

    def cancelMarketOrders(
        self, marketId: str, all_orders_until = None
    ):
        if all_orders_until is None:
            all_orders_until = int(time.time() * 1000)
        
        cancelSignatureRequest = CancelSignatureRequest(
            op=RequestOperation.Cancel,
            all_orders_until=all_orders_until,
        )

        encoded_cancel = encode_user_operation(cancelSignatureRequest)
        signature = self.signer.sign_message(encoded_cancel)

        cancelPayload = {
            "signature": signature,
            "allOrdersUntil": all_orders_until,
            "creator": self.address,
        }

        cancelResponse = self.delete(
            f"v1/accounts/{self.accountId}/markets/{marketId}/orders", cancelPayload
        )

        return cancelResponse

    def cancelOrders(self, orderIds: list):
        cancelSignatureRequest = CancelSignatureRequest(
            op=RequestOperation.Cancel,
            orders=orderIds,
        )

        encoded_cancel = encode_user_operation(cancelSignatureRequest)
        signature = self.signer.sign_message(encoded_cancel)

        cancelPayload = {
            "signature": signature,
            "orders": orderIds,
            "creator": self.address,
        }

        cancelResponse = self.delete(
            f"v1/accounts/{self.accountId}/orders", cancelPayload
        )

        return cancelResponse
