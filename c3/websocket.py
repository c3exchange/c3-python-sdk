import asyncio
import json
import logging
import time
from enum import Enum
from typing import Optional
from urllib.parse import urlencode, urljoin

import websockets

logger = logging.getLogger("websocket-client")

class WebSocketClientEvent(Enum):
    Connect = "connected"
    Level1 = "level1"
    level2Depth20 = "level2Depth20"
    bookDelta = "bookDelta"
    OpenOrders = "openOrders"
    Cancels = "cancels"
    Trades = "trades"

class MessageType(Enum):
    MESSAGE = "message"
    ACK = "ack"
    RESPONSE = "response"
    REQUEST = "request"
    LOGIN = "login"
    ERROR = "error"
    PONG = "pong"
    PING = "ping"

class RequestMethod(Enum):
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    LIST_SUBSCRIPTIONS = "LIST_SUBSCRIPTIONS"

class TopicType(Enum):
    level1 = "level1"
    level2Depth20 = "level2Depth20"
    bookDelta = "bookDelta"
    userOrderEvents = "userOrderEvents"
    unknown = ("unknown",)

def now_ms():
    return round(time.time() * 1000)

async def send_ws_message(websocket: websockets.WebSocketClientProtocol, message: dict):
    str_message = json.dumps(message)
    logger.debug(f"Sending message {str_message}")
    await websocket.send(str_message)

async def send_ping(websocket: websockets.WebSocketClientProtocol):
    while True:
        await websocket.ping()
        await asyncio.sleep(10)  # Send a ping every 10 seconds

class WebSocketClient:
    def __init__(self, url, account_id, jwt_token):
        self.listeners = {}
        self.url = url
        self.jwt_token = jwt_token
        self.socket = None
        self.account_id = account_id
        self.socket_task: Optional[asyncio.Task] = None
        self.running = False
        self.connected = False
        self.requests: dict = {}

    def bind(self):
        def create_handler(wse: WebSocketClientEvent):
            def handler(*args, **kwargs):
                self.emit(wse.value, *args, **kwargs)

            return handler

        # for event in WebSocketClientEvent:
        #     self.socket.on(event.value, create_handler(event))

    def handle_login(self, login_message):
        print("handle_login", login_message)

    def handle_response(self, response_message: dict):
        try:
            logger.debug(f"handle_response: {response_message}")
            rsp_id = response_message["id"]
            fut: asyncio.Future = self.requests[rsp_id]
            if fut is not None:
                fut.set_result(response_message["data"])
        except Exception as e:
            logger.error(e)

    def handle_ack(self, ack_message):
        print(f"handle_ack {ack_message}")

    def handle_event_message(self, event_message):
        event_type = event_message.get("subject")
        if event_type is not None:
            self.emit(event_type, event_message.get("data"))

    def handle_message(self, message):
        if not isinstance(message, str):
            return
        try:
            obj: dict = json.loads(message)
            logger.debug(f"Received Message: f{obj}")
        except json.JSONDecodeError:
            print("Error: Received message is not valid JSON")
            return

        message_type = obj["type"]
        if message_type == MessageType.LOGIN.value:
            self.handle_login(obj)
        elif message_type == MessageType.MESSAGE.value:
            self.handle_event_message(obj)
        elif message_type == MessageType.PONG.value:
            self.heartbeat()
        elif message_type == MessageType.RESPONSE.value:
            self.handle_response(obj)
        elif message_type == MessageType.ACK.value:
            self.handle_ack(obj)

    def on_error(self, ws, error):
        print(f"Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")
        self.connected = False

    def on_open(self, ws):
        print("Connection opened...")
        self.connected = True

    def start(self):
        if self.socket_task is None:
            print("Starting socket_task")
            self.socket_task = asyncio.create_task(self.run(), name="socket_task")
        else:
            raise RuntimeError(
                "Web socket is already running should stop before starting"
            )

    def stop(self):
        if self.socket_task is not None and not self.socket_task.cancelling():
            self.socket_task.cancel()

    async def listen_messages(self, websocket: websockets.WebSocketClientProtocol):
        async for message in websocket:
            try:
                self.handle_message(message)
            except Exception as e:
                logger.error(e)

    async def run_websocket_client(self):
        params = {"accountId": self.account_id, "token": self.jwt_token}
        query_string = urlencode(params)
        uri = urljoin(self.url.replace("http", "ws"), "/ws/v1?" + query_string)
        reconnect_delay = 5
        while True:
            try:
                async with websockets.connect(
                    uri, ping_timeout=10, ping_interval=1
                ) as websocket:
                    self.socket = websocket
                    ping_task = asyncio.create_task(send_ping(websocket))
                    receive_task = asyncio.create_task(self.listen_messages(websocket))
                    # Wait for either task to complete
                    done, pending = await asyncio.wait(
                        [ping_task, receive_task], return_when=asyncio.FIRST_COMPLETED
                    )

                    # If we're here, one of the tasks is done. Cancel the other one.
                    for task in pending:
                        task.cancel()

                    # Optionally, handle the done tasks (e.g., to check for exceptions)
                    for task in done:
                        if task.exception():
                            print(f"Task raised an exception: {task.exception()}")

            except websockets.exceptions.ConnectionClosed as e:
                logger.error(e)
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Error running websocket: {e}")
            print(f"Attempting to reconnect in {reconnect_delay} seconds...")
            await asyncio.sleep(reconnect_delay)

    async def run(self):
        await self.run_websocket_client()

    def connected(self):
        return self.connected

    def check_socket_connection(self):
        if self.socket is None:
            raise Exception("socket is not initialized")

        if not self.connected:
            raise Exception("socket is not connected")

    async def subscribe_to_market(self, market_id: str, topic: TopicType):
        topic = f"{topic.value}:{market_id}"
        subscription_message = {
            "id": f"subscribe-${now_ms()}",
            "method": f"{MessageType.REQUEST.value}",
            "type": f"{RequestMethod.SUBSCRIBE.value}",
            "response": False,
            "topic": topic,
        }
        await send_ws_message(self.socket, subscription_message)

    async def unsubscribe_from_market(self, market_id: str, topic: TopicType):
        topic = f"{topic.value}:{market_id}"
        unsubscription_message = {
            "id": f"unsubscribe-${now_ms()}",
            "method": f"{MessageType.REQUEST.value}",
            "type": f"{RequestMethod.UNSUBSCRIBE.value}",
            "response": False,
            "topic": topic,
        }
        await send_ws_message(self.socket, unsubscription_message)

    async def list_subscriptions(self):
        list_subscriptions_message = {
            "id": f"listSubscriptions-{now_ms()}",
            "method": f"{MessageType.REQUEST.value}",
            "type": f"{RequestMethod.LIST_SUBSCRIPTIONS.value}",
            "response": False,
        }
        fut = asyncio.Future()
        self.requests[list_subscriptions_message["id"]] = fut
        await send_ws_message(self.socket, list_subscriptions_message)
        try:
            result = await asyncio.wait_for(fut, timeout=10)
            return result
        except asyncio.TimeoutError:
            print("List subscriptions request timed out")
            return None

    def on(self, event: WebSocketClientEvent, handler=None):
        def set_handler(h):
            if not self.listeners.get(event.value, None):
                self.listeners[event.value] = {h}
            else:
                self.listeners[event.value].add(h)

        if handler is None:
            return set_handler
        set_handler(handler)

    def emit(self, event_name: str, *args, **kwargs):
        listeners = self.listeners.get(event_name, [])
        for listener in listeners:
            asyncio.create_task(listener(*args, **kwargs))
