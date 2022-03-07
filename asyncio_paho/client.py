"""Asyncio Paho MQTT Client module."""
from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Awaitable, Callable
from enum import Enum, auto
from typing import Any

import paho.mqtt.client as paho


class AsyncioPahoClient(paho.Client):
    # pylint: disable=too-many-instance-attributes
    """Paho MQTT Client using asyncio for connection loop."""

    def __init__(
        self,
        client_id: str = "",
        clean_session: bool | None = None,
        userdata: Any | None = None,
        protocol: int = paho.MQTTv311,
        transport: str = "tcp",
        reconnect_on_failure: bool = True,
        loop: asyncio.AbstractEventLoop = None,
    ) -> None:
        # pylint: disable=too-many-arguments
        """Initialize AsyncioPahoClient. See Paho Client for documentation."""
        super().__init__(
            client_id,
            clean_session,
            userdata,
            protocol,
            transport,
            reconnect_on_failure,
        )
        self._event_loop = loop if loop else asyncio.get_event_loop()
        self._userdata = userdata
        self._reconnect_on_failure = reconnect_on_failure
        self._is_disconnecting = False
        self._is_connect_async = False
        self._connect_ex: Exception | None = None
        self._loop_misc_task: asyncio.Task | None = None

        self._asyncio_listeners = _Listeners(self, self._event_loop)
        self.on_socket_open = self._on_socket_open_asyncio
        self.on_socket_close = self._on_socket_close_asyncio
        self.on_socket_register_write = self._on_socket_register_write_asyncio
        self.on_socket_unregister_write = self._on_socket_unregister_write_asyncio

    async def __aenter__(self) -> AsyncioPahoClient:
        """Enter contex."""
        return self

    async def __aexit__(self, *args) -> None:
        """Exit context."""
        self.disconnect()
        if self._loop_misc_task:
            try:
                await self._loop_misc_task
            except asyncio.CancelledError:
                return

    @property
    def asyncio_listeners(self):
        """Async listeners."""
        return self._asyncio_listeners

    def connect_async(
        self,
        host: str,
        port: int = 1883,
        keepalive: int = 60,
        bind_address: str = "",
        bind_port: int = 0,
        clean_start: bool | int = paho.MQTT_CLEAN_START_FIRST_ONLY,
        properties: paho.Properties | None = None,
    ) -> None:
        # pylint: disable=too-many-arguments
        """
        Connect to a remote broker asynchronously.

        This is a non-blocking connect call that can be used to provide very quick start.
        """
        self._is_connect_async = True
        self._ensure_loop_misc_started()  # loop must be started for connect to proceed
        super().connect_async(
            host, port, keepalive, bind_address, bind_port, clean_start, properties
        )

    def disconnect(
        self,
        reasoncode: paho.ReasonCodes = None,
        properties: paho.Properties | None = None,
    ) -> int:
        """Disconnect a connected client from the broker."""
        result = super().disconnect(reasoncode, properties)
        self._is_disconnecting = True
        if self._loop_misc_task:
            self._loop_misc_task.cancel()
        return result

    async def asyncio_connect(
        self,
        host: str,
        port: int = 1883,
        keepalive: int = 60,
        bind_address: str = "",
        bind_port: int = 0,
        clean_start: bool | int = paho.MQTT_CLEAN_START_FIRST_ONLY,
        properties: paho.Properties | None = None,
    ) -> None:
        # pylint: disable=too-many-arguments
        """Connect to a remote broker asynchronously and return when done."""
        connect_future = self._event_loop.create_future()

        if self.on_connect not in (
            None,
            self._asyncio_listeners._on_connect_forwarder,  # pylint: disable=protected-access
        ) or self.on_connect_fail not in (
            None,
            self._asyncio_listeners._on_connect_fail_forwarder,  # pylint: disable=protected-access
        ):
            raise Exception(
                (
                    "async_connect cannot be used when on_connect or on_connect_fail is set. "
                    "Use asyncio_listeners instead of setting on_connect."
                )
            )

        async def connect_callback(*args):
            # pylint: disable=unused-argument
            nonlocal connect_future
            if self._connect_ex:
                connect_future.set_exception(self._connect_ex)
            else:
                connect_future.set_result(self._connect_ex)

        unsubscribe_connect = self.asyncio_listeners.add_on_connect(
            connect_callback, is_high_pri=True
        )
        unsubscribe_connect_fail = self.asyncio_listeners.add_on_connect_fail(
            connect_callback, is_high_pri=True
        )
        try:
            self.connect_async(
                host, port, keepalive, bind_address, bind_port, clean_start, properties
            )
            await connect_future
        finally:
            unsubscribe_connect()
            unsubscribe_connect_fail()

    async def asyncio_publish(
        self,
        topic: str,
        payload: Any | None = None,
        qos: int = 0,
        retain: bool = False,
        properties: paho.Properties | None = None,
    ) -> int:
        # pylint: disable=too-many-arguments
        """Publish a message on a topic."""
        subscribed_future = self._event_loop.create_future()

        result: paho.MQTTMessageInfo

        async def on_publish(client: paho.Client, userdata: Any, mid: int) -> None:
            # pylint: disable=unused-argument
            nonlocal result
            if result.mid == mid:
                nonlocal subscribed_future
                subscribed_future.set_result(mid)

        unsubscribe = self.asyncio_listeners.add_on_publish(
            on_publish, is_high_pri=True
        )
        try:
            result = super().publish(topic, payload, qos, retain, properties)
            result.is_published()
            return await subscribed_future
        finally:
            unsubscribe()

    async def asyncio_subscribe(
        self,
        topic: str | tuple | list,
        qos: int = 0,
        options: paho.SubscribeOptions | None = None,
        properties: paho.Properties | None = None,
    ):
        """Subscribe the client to one or more topics."""
        subscribed_future = self._event_loop.create_future()
        result: tuple[int, int]

        async def on_subscribe(*args):
            # pylint: disable=unused-argument
            nonlocal result
            if result[1] == args[2]:  # mid should match if relevant
                nonlocal subscribed_future
                subscribed_future.set_result(None)

        unsubscribe = self.asyncio_listeners.add_on_subscribe(
            on_subscribe, is_high_pri=True
        )
        try:
            result = super().subscribe(topic, qos, options, properties)

            if result[0] == paho.MQTT_ERR_NO_CONN:
                return result

            await subscribed_future
            return result
        finally:
            unsubscribe()

    def user_data_set(self, userdata: Any) -> None:
        """Set the user data variable passed to callbacks. May be any data type."""
        self._userdata = userdata
        super().user_data_set(userdata)

    def loop_forever(self, *args, **kvarg):
        """Invalid operation."""
        raise NotImplementedError(
            "loop_forever() cannot be used with AsyncioPahoClient."
        )

    def loop_start(self):
        """Invalid operation."""
        raise NotImplementedError(
            "The threaded interface of loop_start() cannot be used with AsyncioPahoClient."
        )

    def loop_stop(self, force: bool = ...):
        """Invalid operation."""
        raise NotImplementedError(
            "The threaded interface of loop_stop() cannot be used with AsyncioPahoClient."
        )

    def _on_socket_open_asyncio(
        self, client: paho.Client, _, sock: socket.socket
    ) -> None:
        self._event_loop.add_reader(sock, client.loop_read)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)
        self._ensure_loop_misc_started()

    def _on_socket_close_asyncio(
        self,
        client,
        userdata,
        sock: socket.socket,
    ) -> None:
        # pylint: disable=unused-argument
        self._event_loop.remove_reader(sock)

    def _on_socket_register_write_asyncio(
        self, client: paho.Client, userdata, sock: socket.socket
    ) -> None:
        # pylint: disable=unused-argument
        self._event_loop.add_writer(sock, client.loop_write)

    def _on_socket_unregister_write_asyncio(
        self, client, userdata, sock: socket.socket
    ) -> None:
        # pylint: disable=unused-argument
        self._event_loop.remove_writer(sock)

    def _ensure_loop_misc_started(self) -> None:
        if self._loop_misc_task is None or self._loop_misc_task.done():
            self._loop_misc_task = self._event_loop.create_task(self._loop_misc())

    async def _loop_misc(self) -> None:
        try:
            self._connect_ex = None
            self._is_disconnecting = False
            if self._is_connect_async:
                try:
                    self.reconnect()
                except Exception as ex:
                    self._connect_ex = ex
                    on_connect_fail = super().on_connect_fail
                    if on_connect_fail:
                        on_connect_fail(self, self._userdata)
                    raise

                self._is_connect_async = False

            while True:

                return_code = paho.MQTT_ERR_SUCCESS
                while return_code == paho.MQTT_ERR_SUCCESS:
                    return_code = self.loop_misc()
                    await asyncio.sleep(1)

                if self._is_disconnecting or not self._reconnect_on_failure:
                    self._log(paho.MQTT_LOG_DEBUG, "Disconnecting. Exit misc loop.")
                    return

                await self._async_reconnect_wait()

                if self._is_disconnecting:
                    self._log(paho.MQTT_LOG_DEBUG, "Disconnecting. Exit misc loop.")
                    return

                self._reconnect()
        except asyncio.CancelledError:
            self._log(paho.MQTT_LOG_DEBUG, "Loop misc cancelled.")
            return

    def _reconnect(self) -> None:
        try:
            self.reconnect()
        except (OSError, paho.WebsocketConnectionError):
            on_connect_fail = super().on_connect_fail
            if on_connect_fail:
                on_connect_fail(self, self._userdata)
            self._log(paho.MQTT_LOG_DEBUG, "Connection failed, retrying")

    async def _async_reconnect_wait(self):
        # See reconnect_delay_set for details
        now = time.monotonic()
        with self._reconnect_delay_mutex:
            if self._reconnect_delay is None:
                self._reconnect_delay = self._reconnect_min_delay
            else:
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self._reconnect_max_delay,
                )

            target_time = now + self._reconnect_delay

        remaining = target_time - now
        await asyncio.sleep(remaining)

    def _log(self, level: Any, fmt: object, *args: object):
        easy_log = getattr(super(), "_easy_log", None)
        if easy_log is not None:
            easy_log(level, fmt, *args)


class _EventType(Enum):
    ON_CONNECT = auto()
    ON_CONNECT_FAILED = auto()
    ON_MESSAGE = auto()
    ON_SUBSCRIBE = auto()
    ON_PUBLISH = auto()


class _Listeners:
    def __init__(
        self, client: AsyncioPahoClient, loop: asyncio.AbstractEventLoop
    ) -> None:
        self._client = client
        self._event_loop = loop
        self._async_listeners: dict[_EventType, list] = {}

    def _get_async_listeners(self, event_type: _EventType) -> list:
        return self._async_listeners.setdefault(event_type, [])

    def _add_async_listener(
        self, event_type: _EventType, callback, is_high_pri=False
    ) -> Callable[[], None]:
        listeners = self._get_async_listeners(event_type)
        if is_high_pri:
            listeners.insert(0, callback)
        else:
            listeners.append(callback)

        def unsubscribe():
            if callback in listeners:
                listeners.remove(callback)

        return unsubscribe

    def _async_forwarder(self, event_type: _EventType, *args):
        async_listeners = self._get_async_listeners(event_type)
        for listener in async_listeners:
            self._event_loop.create_task(listener(*args))

    def add_on_connect(
        self,
        callback: Callable[[paho.Client, Any, dict[str, Any], int], Awaitable[None]]
        | Callable[
            [paho.Client, Any, dict[str, Any], paho.ReasonCodes, paho.Properties],
            Awaitable[None],
        ],
        is_high_pri: bool = False,
    ) -> Callable[[], None]:
        """Add on_connect async listener."""
        paho.Client.on_connect.fset(self._client, self._on_connect_forwarder)  # type: ignore
        return self._add_async_listener(_EventType.ON_CONNECT, callback, is_high_pri)

    def _on_connect_forwarder(self, *args):
        self._async_forwarder(_EventType.ON_CONNECT, *args)

    def add_on_connect_fail(
        self,
        callback: Callable[[paho.Client, Any], Awaitable[None]],
        is_high_pri: bool = False,
    ) -> Callable[[], None]:
        """Add on_connect_fail async listener."""
        on_connect_fail = paho.Client.on_connect_fail
        on_connect_fail.fset(self._client, self._on_connect_fail_forwarder)  # type: ignore
        return self._add_async_listener(
            _EventType.ON_CONNECT_FAILED, callback, is_high_pri
        )

    def _on_connect_fail_forwarder(self, *args):
        self._async_forwarder(_EventType.ON_CONNECT_FAILED, *args)

    def add_on_message(
        self,
        callback: Callable[[paho.Client, Any, paho.MQTTMessage], Awaitable[None]],
    ) -> Callable[[], None]:
        """Add on_connect_fail async listener."""

        def forwarder(*args):
            self._async_forwarder(_EventType.ON_MESSAGE, *args)

        paho.Client.on_message.fset(self._client, forwarder)  # type: ignore
        return self._add_async_listener(_EventType.ON_MESSAGE, callback)

    def message_callback_add(
        self,
        sub: str,
        callback: Callable[[paho.Client, Any, paho.MQTTMessage], Awaitable[None]],
    ) -> None:
        """Register an async message callback for a specific topic."""

        def forwarder(*args):
            self._event_loop.create_task(callback(*args))

        self._client.message_callback_add(sub, forwarder)

    def add_on_subscribe(
        self,
        callback: Callable[[paho.Client, Any, int, tuple[int, ...]], Awaitable[None]]
        | Callable[
            [paho.Client, Any, int, list[int], paho.Properties], Awaitable[None]
        ],
        is_high_pri: bool = False,
    ) -> Callable[[], None]:
        """Add on_subscribe async listener."""

        def forwarder(*args):
            self._async_forwarder(_EventType.ON_SUBSCRIBE, *args)

        paho.Client.on_subscribe.fset(self._client, forwarder)  # type: ignore
        return self._add_async_listener(_EventType.ON_SUBSCRIBE, callback, is_high_pri)

    def add_on_publish(
        self,
        callback: Callable[[paho.Client, Any, int], Awaitable[None]],
        is_high_pri: bool = False,
    ) -> Callable[[], None]:
        """Add on_publish async listener."""

        def forwarder(*args):
            self._async_forwarder(_EventType.ON_PUBLISH, *args)

        paho.Client.on_publish.fset(self._client, forwarder)  # type: ignore
        return self._add_async_listener(_EventType.ON_PUBLISH, callback, is_high_pri)
