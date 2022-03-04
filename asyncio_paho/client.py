"""Asyncio Paho MQTT Client module."""
from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Awaitable, Callable
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
        self._loop_misc_task: asyncio.Task | None = None
        self._on_message_async: Callable[
            [paho.Client, Any, paho.MQTTMessage], Awaitable[None]
        ] | None = None

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
            await self._loop_misc_task

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
        return super().connect_async(
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
            self._is_disconnecting = False
            while True:
                if self._is_connect_async:
                    self._reconnect()
                    self._is_connect_async = False
                    await self._async_reconnect_wait()

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
