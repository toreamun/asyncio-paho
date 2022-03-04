"""AsyncioPahoClient integration tests."""
import asyncio
import logging

import paho.mqtt.client as paho
import pytest
from asyncio_paho.client import AsyncioPahoClient

TOPIC = "asyncioclient"
MQTT_HOST = "test.mosquitto.org"


@pytest.mark.asyncio
async def test_connect_publish_subscribe(event_loop: asyncio.AbstractEventLoop, caplog):
    """Test connect."""
    caplog.set_level(logging.DEBUG)

    subscribed_future = event_loop.create_future()
    done_future = event_loop.create_future()
    subscribe_result: tuple[int, int] = (-1, -1)

    def on_connect(*argv) -> None:
        # pylint: disable=unused-argument
        nonlocal subscribe_result
        subscribe_result = client.subscribe(TOPIC)

        assert subscribe_result[0] == paho.MQTT_ERR_SUCCESS

        print(
            f"Connected and subscribed to topic {TOPIC} with result {subscribe_result}"
        )

    def on_connect_fail(*argv) -> None:
        # pylint: disable=unused-argument
        print("Connect failed")

    def on_subscribe(client, userdata, mid, granted_qos) -> None:
        # pylint: disable=unused-argument
        print("Subscription done.")

        nonlocal subscribe_result
        assert mid == subscribe_result[1]

        subscribed_future.set_result(None)

    async def on_message_async(client, userdata, msg: paho.MQTTMessage):
        # pylint: disable=unused-argument
        print(f"Received from {msg.topic}: {str(msg.payload)}")
        done_future.set_result(msg.payload)

    async with AsyncioPahoClient(loop=event_loop) as client:
        client.on_connect = on_connect
        client.on_connect_fail = on_connect_fail
        client.on_subscribe = on_subscribe
        client.on_message_async = on_message_async

        client.connect_async(MQTT_HOST, port=1883)

        # wait for subscription be done before publishing
        await subscribed_future
        client.publish(TOPIC, "this is a test")

        received = await done_future

        assert received == b"this is a test"
