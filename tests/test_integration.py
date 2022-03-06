"""AsyncioPahoClient integration tests."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import paho.mqtt.client as paho
import pytest
from asyncio_paho import AsyncioPahoClient

TOPIC = "asyncioclient"
MQTT_HOST = "test.mosquitto.org"


@pytest.mark.asyncio
async def test_connect_publish_subscribe(event_loop: asyncio.AbstractEventLoop, caplog):
    """Test connect."""
    caplog.set_level(logging.DEBUG)

    subscribed_future = event_loop.create_future()
    done_future = event_loop.create_future()
    subscribe_result: tuple[int, int] = (-1, -1)

    def on_connect(
        client: paho.Client, userdata: Any, flags_dict: dict[str, Any], result: int
    ) -> None:
        # pylint: disable=unused-argument
        nonlocal subscribe_result
        subscribe_result = client.subscribe(TOPIC)

        assert subscribe_result[0] == paho.MQTT_ERR_SUCCESS

        print(
            f"Connected and subscribed to topic {TOPIC} with result {subscribe_result}"
        )

    def on_connect_fail(client: paho.Client, userdata: Any) -> None:
        # pylint: disable=unused-argument
        print("Connect failed")

    def on_subscribe(
        client: paho.Client, userdata: Any, mid: int, granted_qos: tuple[int, ...]
    ) -> None:
        # pylint: disable=unused-argument
        print("Subscription done.")

        nonlocal subscribe_result
        assert mid == subscribe_result[1]

        subscribed_future.set_result(None)

    def on_message(client, userdata, msg: paho.MQTTMessage):
        # pylint: disable=unused-argument
        print(f"Received from {msg.topic}: {str(msg.payload)}")
        done_future.set_result(msg.payload)

    def on_log(client, userdata, level, buf):
        # pylint: disable=unused-argument
        print(f"LOG: {buf}")

    async with AsyncioPahoClient(loop=event_loop) as client:
        client.on_connect = on_connect
        client.on_connect_fail = on_connect_fail
        client.on_subscribe = on_subscribe
        client.on_message = on_message
        client.on_log = on_log

        client.connect_async(MQTT_HOST)

        # wait for subscription be done before publishing
        await subscribed_future
        client.publish(TOPIC, "this is a test")

        received = await done_future

        assert received == b"this is a test"


@pytest.mark.asyncio
async def test_async_connect_publish_subscribe(
    event_loop: asyncio.AbstractEventLoop, caplog
):
    """Test connect."""
    caplog.set_level(logging.DEBUG)

    subscribed_future = event_loop.create_future()
    done_future = event_loop.create_future()
    subscribe_result: tuple[int, int] = (-1, -1)

    async def on_connect_async(
        client: paho.Client, userdata: Any, flags_dict: dict[str, Any], result: int
    ) -> None:
        # pylint: disable=unused-argument
        nonlocal subscribe_result
        subscribe_result = client.subscribe(TOPIC)

        assert subscribe_result[0] == paho.MQTT_ERR_SUCCESS

        print(
            f"Connected and subscribed to topic {TOPIC} with result {subscribe_result}"
        )

    async def on_connect_fail(client: paho.Client, userdata: Any) -> None:
        # pylint: disable=unused-argument
        print("Connect failed")

    async def on_subscribe(
        client: paho.Client, userdata: Any, mid: int, granted_qos: tuple[int, ...]
    ) -> None:
        # pylint: disable=unused-argument
        print("Subscription done.")

        nonlocal subscribe_result
        assert mid == subscribe_result[1]

        subscribed_future.set_result(None)

    async def on_message_async(client, userdata, msg: paho.MQTTMessage):
        # pylint: disable=unused-argument
        print(f"Received from {msg.topic}: {str(msg.payload)}")
        done_future.set_result(msg.payload)

    def on_log(client, userdata, level, buf):
        # pylint: disable=unused-argument
        print(f"LOG: {buf}")

    async with AsyncioPahoClient(loop=event_loop) as client:
        client.asyncio_add_on_connect_listener(on_connect_async)
        client.asyncio_add_on_connect_fail_listener(on_connect_fail)
        client.asyncio_add_on_subscribe_listener(on_subscribe)
        client.asyncio_add_on_message_listener(on_message_async)
        client.on_log = on_log

        await client.asyncio_connect(MQTT_HOST)

        # wait for subscription be done before publishing
        await subscribed_future
        client.publish(TOPIC, "this is a test")

        received = await done_future

        assert received == b"this is a test"
