[![GitHub Release](https://img.shields.io/github/release/toreamun/asyncio-paho)](https://github.com/toreamun/asyncio-paho/releases)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/toreamun/asyncio-paho.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/toreamun/asyncio-paho/context:python)
[![CodeQL](https://github.com/toreamun/asyncio-paho/workflows/CodeQL/badge.svg)](https://github.com/toreamun/asyncio-paho/actions?query=workflow%3ACodeQL&)
[![License](https://img.shields.io/github/license/toreamun/asyncio-paho)](LICENSE)
![Project Maintenance](https://img.shields.io/badge/maintainer-Tore%20Amundsen%20%40toreamun-blue.svg)
[![buy me a coffee](https://img.shields.io/badge/If%20you%20like%20it-Buy%20me%20a%20coffee-orange.svg)](https://www.buymeacoffee.com/toreamun)

# Asynchronous I/O (asyncio) Paho MQTT client

A [Paho MQTT](https://github.com/eclipse/paho.mqtt.python) client supporting [asyncio](https://docs.python.org/3/library/asyncio.html) loop without additional setup. Forget about configuring the [Paho network-loop](https://github.com/eclipse/paho.mqtt.python#network-loop). The client can almost be used as a drop-in replacement for Paho Client. The asyncio loop is automatically configured when you connect.

### Features

- Drop-in replacement of Paho Client (inherits from Paho Client)
- Automatic configuration of asyncio loop.
- Reconnect on connection loss.
- Type hinted.
- Async callbacks.
- Non blocking connect (`await client.asyncio_connect()`).
- Python Asynchronous Context Manager handles cleanup.
- No threading, only asyncio.

## Installation

```
pip install asyncio-paho
```

## Usage

You should use Paho [`connect_async()`](https://github.com/eclipse/paho.mqtt.python#connect_async) or extension [`asyncio_connect()`](#asyncio_connect) when connecting to avoid blocking. It is often usefull to configure subscriptions in on_connect callback to make sure all subscriptions is also setup on reconnect after connection loss.

### Drop-in replacement

Remove all you calls to Paho looping like loop_forever() etc.

```python
client = AsyncioPahoClient()
client.connect_async("mqtt.eclipseprojects.io")

# remove your current looping (loop_forever() etc)
# do mqtt stuff

client.Disconnect()

```

### Asynchronous Context Manager

The client is an Asynchronous Context Manager and can be used with the Python with statement to atomatically disconnect and clean up.

```python
async with AsyncioPahoClient() as client:
    client.connect_async("mqtt.eclipseprojects.io")

    # do mqtt stuff - client.Disconnect() is called when exiting context.

```

## Extensions

The client has some additional async features (functions prefixed with `asyncio_`).

### asyncio_connect

The classic Paho [`connect()`](https://github.com/eclipse/paho.mqtt.python#connect) is blocking. Paho [`connect_async()`](https://github.com/eclipse/paho.mqtt.python#connect_async) is not blocking, but returns before the connect is complete. Use `asyncio_connect()` to wait for connect to complete without blocking. This function also throws exception on connect failure. Please note that `asyncio_connect()` cannot be used together with `on_connect` /`on_connect_fail` (use `asyncio_add_on_connect_listener` and `asyncio_add_on_connect_fail_listener` instead of `on_connect` and `on_connect_fail`).

```python
async with AsyncioPahoClient() as client:
    await client.asyncio_connect("mqtt.eclipseprojects.io")
```

### asyncio_subscribe

The classic Paho [`connect()`](https://github.com/eclipse/paho.mqtt.python#subscribe) returns before the subscriptions is acknowledged by the broker, and [`on_subscribe`](https://github.com/eclipse/paho.mqtt.python#on_subscribe) / `asyncio_listeners.add_on_subscribe()` has to be uses to capture the acknowledge if needed. The async extension `asyncio_subscribe()` can be used to subscribe and wait for the acknowledge without blocking. It is often usefull to configure subscriptions when connecting to make sure subscriptions are reconfigured on reconnect (connection lost).

```python
async def on_connect_async(client, userdata, flags_dict, result):
    await client.asyncio_subscribe("mytopic")

async def on_message_async(client, userdata, msg):
    print(f"Received from {msg.topic}: {str(msg.payload)}")

async with AsyncioPahoClient() as client:
    client.asyncio_listeners.add_on_connect(on_connect_async)
    client.asyncio_listeners.add_on_message(on_message_async)
    await client.asyncio_connect("mqtt.eclipseprojects.io")
```

### Callbacks

Paho has a lot of callbacks. Async alternatives have been added for some of them, but they are mutally exclusive (you have to pick sync or async for eatch callback type). Multiple async listeners can be added to the same event, and a function handle to unsubscribe is returned when adding.

| Classic Paho                                                                             | Extension alternative                    | Called when                                                                                     |
| ---------------------------------------------------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [on_connect](https://github.com/eclipse/paho.mqtt.python#callback-connect)               | asyncio_listeners.add_on_connect()       | the broker responds to our connection                                                           |
| on_connect_fail                                                                          | asyncio_listeners.add_on_connect_fail()  | the client failed to connect to the broker                                                      |
| [on_message](https://github.com/eclipse/paho.mqtt.python#on_message)                     | asyncio_listeners.add_on_message()       | a message has been received on a topic that the client subscribes to                            |
| [message_callback_add](https://github.com/eclipse/paho.mqtt.python#message_callback_add) | asyncio_listeners.message_callback_add() | a message has been received on a topic for specific subscription filters                        |
| [on_subscribe](https://github.com/eclipse/paho.mqtt.python#on_subscribe)                 | asyncio_listeners.add_on_subscribe()     | the broker responds to a subscribe request                                                      |
| [on_publish](https://github.com/eclipse/paho.mqtt.python#on_publish)                     | asyncio_listeners.add_on_publish()       | a message that was to be sent using the publish() call has completed transmission to the broker |

```python

async def on_connect_async(client, userdata, message) -> None:
    client.subscribe("mytopic")

async with AsyncioPahoClient() as client:
    client.asyncio_add_on_connect_listener(on_connect_async)
    await client.asyncio_connect("mqtt.eclipseprojects.io")
```

#### asyncio_listeners.add_on_connect()

Add async on_connect event listener.

MQTT v3 callback signature:

```python
async def callback(client: AsyncioPahoClient, userdata: Any, flags: dict[str, Any], rc: int)
```

MQTT v5 callback signature:

```python
async def callback(client: AsyncioPahoClient, userdata: Any, flags: dict[str, reasonCode: ReasonCodes, properties: Properties])
```

#### asyncio_listeners.add_on_message()

Add async on_connect event listener. Callback signature:

```python
async def callback(client: AsyncioPahoClient, userdata: Any, msg: MQTTMessage)
```

## Dependencies

- Python 3.8 or later.
- [Paho MQTT](https://github.com/eclipse/paho.mqtt.python)

The client uses asyncio event loop `add_reader()` and `add_writer()` methods. These methods are not supported on [Windows](https://docs.python.org/3/library/asyncio-platforms.html#windows) by [ProactorEventLoop](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.ProactorEventLoop) (default on **Windows** from Python 3.8). You should be able to use another event loop like [SelectorEventLoop](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.SelectorEventLoop).
