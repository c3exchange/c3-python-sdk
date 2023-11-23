import base64
import binascii
from abc import ABC, abstractmethod

from algosdk import account, mnemonic, util
from eth_account import Account, messages

from c3.signing.encode import OrderData, encode_user_operation
from c3.signing.types import SettlementTicket


class MessageSigner(ABC):
    @abstractmethod
    def address(self) -> str:
        pass

    @abstractmethod
    def sign_message(self, message: bytes) -> str:
        pass

    @abstractmethod
    def base64address(self) -> bytes:
        pass


# to-do receive algo sdk account as init value


class AlgorandMessageSigner(MessageSigner):
    def __init__(self, private_key: str) -> None:
        self.private_key = mnemonic.to_private_key(
            mnemonic.from_master_derivation_key(private_key)
        )
        super().__init__()

    def address(self) -> str:
        return account.address_from_private_key(self.private_key)

    def base64address(self) -> bytes:
        """Decodes address decoded into bytes.
            Smart Contract uses this format to represent addresses.

        Returns:
            bytes: address decoded into bytes
        """
        bytesAddress = util.encoding.decode_address(
            account.address_from_private_key(self.private_key)
        )

        base64address = base64.b64encode(bytesAddress)

        return base64address

    def sign_message(self, message: bytes) -> str:
        return util.sign_bytes(message, self.private_key)


# to-do receive eth_account account as init value
class EVMMessageSigner(MessageSigner):
    """ "
    Ethereum Message Signer

    It is a eth_account account wrapper to sign messages and decode address

    """

    def __init__(self, private_key: str) -> None:
        self.private_key = private_key
        super().__init__()

    def address(self) -> str:
        return Account.from_key(self.private_key).address

    def base64address(self) -> bytes:
        """Decodes address decoded into bytes.
            Smart Contract uses this format to represent addresses.

        Returns:
            bytes: address decoded into bytes
        """

        def _pad_left_uint8_array(value: bytes, total_length: int) -> bytes:
            if len(value) > total_length:
                raise ValueError(
                    f"Invalid value length, expected {total_length} but received {len(value)}"
                )
            return bytes(total_length - len(value)) + value

        def decode_ethereum_address(ethereum_address: str) -> bytes:
            if ethereum_address.startswith("0x"):
                ethereum_address = ethereum_address[2:]
            return _pad_left_uint8_array(binascii.unhexlify(ethereum_address), 32)

        base64address = base64.b64encode(decode_ethereum_address(self.address()))
        return base64address

    def sign_message(self, message: bytes) -> str:
        msg = messages.encode_defunct(message)
        hexBytesSignature = Account.sign_message(
            msg, private_key=self.private_key
        ).signature

        base64_encoded_signature = base64.b64encode(hexBytesSignature).decode("utf-8")

        return base64_encoded_signature


def sign_order_data(
    order_data: OrderData,
    signer: MessageSigner,
) -> SettlementTicket:
    return SettlementTicket(
        order_data.account,
        order_data.sell_slot_id,
        order_data.buy_slot_id,
        order_data.sell_amount,
        order_data.buy_amount,
        order_data.max_sell_amount_from_pool,
        order_data.max_buy_amount_to_pool,
        order_data.expires_on,
        order_data.nonce,
        signer.base64address(),
        signer.sign_message(encode_user_operation(order_data)),
    )