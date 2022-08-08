"""AsyncioPahoClient integration tests."""
from __future__ import annotations

import asyncio
import logging
import uuid
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
    test_topic = f"{TOPIC}/{uuid.uuid4()}"

    def on_connect(
        client: paho.Client, userdata: Any, flags_dict: dict[str, Any], result: int
    ) -> None:
        # pylint: disable=unused-argument
        nonlocal subscribe_result
        subscribe_result = client.subscribe(test_topic)

        assert subscribe_result[0] == paho.MQTT_ERR_SUCCESS

        print(
            f"Connected and subscribed to topic {test_topic} with result {subscribe_result}"
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
        client.publish(test_topic, "this is a test")

        received = await done_future

        assert received == b"this is a test"


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", [paho.MQTTv31, paho.MQTTv311, paho.MQTTv5])
@pytest.mark.parametrize("qos", [0, 1, 2])
async def test_async_connect_publish_subscribe(
    event_loop: asyncio.AbstractEventLoop, caplog, protocol, qos
):
    """Test connect."""
    caplog.set_level(logging.DEBUG)
    subscribed_future = event_loop.create_future()
    received_future = event_loop.create_future()
    test_topic = f"{TOPIC}/{protocol}/{uuid.uuid4()}"

    async def on_connect_v3_async(
        client: AsyncioPahoClient,
        userdata: Any,
        flags_dict: dict[str, Any],
        result: int,
    ) -> None:
        # pylint: disable=unused-argument
        subscribe_result = await client.asyncio_subscribe(test_topic, qos=2)
        assert subscribe_result[0] == paho.MQTT_ERR_SUCCESS
        print(
            f"Connected and subscribed to topic {test_topic} with result {subscribe_result}"
        )
        nonlocal subscribed_future
        subscribed_future.set_result(subscribe_result)

    async def on_connect_v5_async(
        client: AsyncioPahoClient,
        userdata: Any,
        flags: dict[str, Any],
        reason_code: paho.ReasonCodes,
        properties: paho.Properties,
    ) -> None:
        # pylint: disable=unused-argument
        subscribe_result = await client.asyncio_subscribe(test_topic, qos=2)
        assert subscribe_result[0] == paho.MQTT_ERR_SUCCESS
        print(
            f"Connected and subscribed to topic {test_topic} with result {subscribe_result}"
        )
        nonlocal subscribed_future
        subscribed_future.set_result(subscribe_result)

    async def on_message_async(client, userdata, msg: paho.MQTTMessage):
        # pylint: disable=unused-argument
        print(f"Received from {msg.topic}: {str(msg.payload)}")
        nonlocal received_future
        received_future.set_result(msg)

    async with AsyncioPahoClient(loop=event_loop, protocol=protocol) as client:
        if protocol == paho.MQTTv5:
            #            client.asyncio_listeners.add_on_connect(on_connect_v3_async)
            client.asyncio_listeners.add_on_connect(on_connect_v5_async)
        else:
            client.asyncio_listeners.add_on_connect(on_connect_v3_async)

        client.asyncio_listeners.add_on_message(on_message_async)
        client.on_log = lambda client, userdata, level, buf: print(f"LOG: {buf}")

        await client.asyncio_connect(MQTT_HOST)
        await subscribed_future

        await client.asyncio_publish(test_topic, "this is a test", qos=qos)
        received: paho.MQTTMessage = await received_future
        assert received.payload == b"this is a test"
        assert received.qos == qos
