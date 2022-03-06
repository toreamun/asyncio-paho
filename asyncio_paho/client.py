"""Asyncio Paho MQTT Client module."""
from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Awaitable, Callable
from enum import Enum, auto
from typing import Any

import paho.mqtt.client as paho


class _EventType(Enum):
    ON_CONNECT = auto()
    ON_CONNECT_FAILED = auto()


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
        self._on_message_async: Callable[
            [paho.Client, Any, paho.MQTTMessage], Awaitable[None]
        ] | None = None

        self._async_listeners: dict[_EventType, list] = {}

        self.on_socket_open = self._on_socket_open_asyncio
        self.on_socket_close = self._on_socket_close_asyncio
        self.on_socket_register_write = self._on_socket_register_write_asyncio
        self.on_socket_unregister_write = self._on_socket_unregister_write_asyncio

    async def __aenter__(self) -> AsyncioPahoClient:
        """Enter contex."""
        return self

    async def __aexit__(self, *argv) -> None:
        """Exit context."""
        self.disconnect()
        if self._loop_misc_task:
            try:
                await self._loop_misc_task
            except asyncio.CancelledError:
                return

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
            self._on_connect_forwarder,
        ) or self.on_connect_fail not in (None, self._on_connect_fail_forwarder):
            raise Exception(
                (
                    "async_connect cannot be used when on_connect or on_connect_failed is set. "
                    "Use add_on_connect_listener instead of setting on_connect."
                )
            )

        async def connect_callback(*argv):
            # pylint: disable=unused-argument
            nonlocal connect_future
            if self._connect_ex:
                connect_future.set_exception(self._connect_ex)
            else:
                connect_future.set_result(self._connect_ex)

        unsubscribe_connect = self.asyncio_add_on_connect_listener(
            connect_callback, is_high_pri=True
        )
        unsubscribe_connect_fail = self.asyncio_add_on_connect_fail_listener(
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

    def asyncio_add_on_connect_listener(
        self,
        callback: Callable[[paho.Client, Any, dict, int], Awaitable[None]]
        | Callable[[paho.Client, Any, dict, int, paho.Properties], Awaitable[None]],
        is_high_pri: bool = False,
    ) -> Callable[[], None]:
        """Add on_connect async listener."""
        paho.Client.on_connect.fset(self, self._on_connect_forwarder)  # type: ignore
        return self._add_async_listener(_EventType.ON_CONNECT, callback, is_high_pri)

    def _on_connect_forwarder(self, *argv):
        self._async_forwarder(_EventType.ON_CONNECT, argv)

    def asyncio_add_on_connect_fail_listener(
        self,
        callback: Callable[[paho.Client, Any], Awaitable[None]],
        is_high_pri: bool = False,
    ) -> Callable[[], None]:
        """Add on_connect_fail async listener."""
        paho.Client.on_connect_fail.fset(self, self._on_connect_fail_forwarder)  # type: ignore
        return self._add_async_listener(
            _EventType.ON_CONNECT_FAILED, callback, is_high_pri
        )

    def _on_connect_fail_forwarder(self, *argv):
        self._async_forwarder(_EventType.ON_CONNECT_FAILED, argv)

    @property
    def on_message(self) -> Callable[[paho.Client, Any, paho.MQTTMessage], None] | None:
        """Get the message received callback implementation."""
        if super().on_message == self._on_message_async:
            return None
        return super().on_message

    @on_message.setter
    def on_message(
        self, func: Callable[[paho.Client, Any, paho.MQTTMessage], None]
    ) -> None:
        """Set the message received callback implementation."""
        self._on_message_async = None
        paho.Client.on_message.fset(self, func)  # type: ignore

    @property
    def on_message_async(
        self,
    ) -> Callable[[paho.Client, Any, paho.MQTTMessage], Awaitable[None]] | None:
        """Get the message received async callback implementation."""
        return self._on_message_async

    @on_message_async.setter
    def on_message_async(
        self, func: Callable[[paho.Client, Any, paho.MQTTMessage], Awaitable[None]]
    ):
        """Set the message received async callback implementation."""
        self._on_message_async = func
        paho.Client.on_message.fset(self, self._on_message_async_forwarder)  # type: ignore

    def _on_message_async_forwarder(
        self, client: paho.Client, userdata: Any, message: paho.MQTTMessage
    ):
        if self._on_message_async:
            self._event_loop.create_task(
                self._on_message_async(client, userdata, message)
            )

    def message_async_callback_add(
        self,
        sub: str,
        callback: Callable[[paho.Client, Any, paho.MQTTMessage], Awaitable[None]],
    ) -> None:
        """Register an async message callback for a specific topic."""

        def forwarder(client: paho.Client, userdata: Any, message: paho.MQTTMessage):
            self._event_loop.create_task(callback(client, userdata, message))

        super().message_callback_add(sub, forwarder)

    def user_data_set(self, userdata: Any) -> None:
        """Set the user data variable passed to callbacks. May be any data type."""
        self._userdata = userdata
        super().user_data_set(userdata)

    def loop_forever(self, *argv, **kvarg):
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

    def _async_forwarder(self, event_type: _EventType, *argv):
        async_listeners = self._get_async_listeners(event_type)
        for listener in async_listeners:
            self._event_loop.create_task(listener(argv))
