[![GitHub Release](https://img.shields.io/github/release/toreamun/asyncio-paho)](https://github.com/toreamun/asyncio-paho/releases)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/toreamun/asyncio-paho.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/toreamun/asyncio-paho/context:python)
[![CodeQL](https://github.com/toreamun/asyncio-paho/workflows/CodeQL/badge.svg)](https://github.com/toreamun/asyncio-paho/actions?query=workflow%3ACodeQL&)
[![License](https://img.shields.io/github/license/toreamun/asyncio-paho)](LICENSE)
![Project Maintenance](https://img.shields.io/badge/maintainer-Tore%20Amundsen%20%40toreamun-blue.svg)
[![buy me a coffee](https://img.shields.io/badge/If%20you%20like%20it-Buy%20me%20a%20coffee-orange.svg)](https://www.buymeacoffee.com/toreamun)

# Asynchronous I/O (asyncio) Paho MQTT client

A [Paho MQTT](https://github.com/eclipse/paho.mqtt.python) client supporting [asyncio](https://docs.python.org/3/library/asyncio.html) loop without additional setup. Forget about configuring the [Paho network-loop](https://github.com/eclipse/paho.mqtt.python#network-loop). The client can almost be used as a drop-in replacement for Paho Client. The asyncio loop is automatically configured when you connect. You should use Paho [`connect_async()`](https://github.com/eclipse/paho.mqtt.python#connect_async) or extension [`asyncio_connect()`](#asyncio_connect) to when connecting to avoid blocking.

## Usage

### Drop-in replacement

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

The classic Paho [`connect()`](https://github.com/eclipse/paho.mqtt.python#connect) is blocking. Paho [`connect_async()`](https://github.com/eclipse/paho.mqtt.python#connect_async) is not blocking, but returns before the connect is complete. Use `asyncio_connect()` to wait for connect to complete without blocking. This function also throws exception on connect failure. Please not that `asyncio_connect()` cannot be used together with `on_connect` /`on_connect_fail` (use `asyncio_add_on_connect_listener` and `asyncio_add_on_connect_fail_listener` instead of `on_connect` and `on_connect_fail`).

```python
async with AsyncioPahoClient() as client:
    await client.asyncio_connect("mqtt.eclipseprojects.io")
```

### Callbacks

Paho has a lot of callbacks. Async alternatives have been added for some of them, but they are mutally exclusive (you have to pick sync or async for eatch callback type).

| Classic Paho    | Extension alternative                  |
| --------------- | -------------------------------------- |
| on_connect      | asyncio_add_on_connect_listener()      |
| on_connect_fail | asyncio_add_on_connect_fail_listener() |
| on_message      | asyncio_add_on_message_listener()      |

```python

async def on_connect_async(client, userdata, message) -> None:
    client.subscribe("mytopic")

async with AsyncioPahoClient() as client:
    client.asyncio_add_on_connect_listener(on_connect_async)
    await client.asyncio_connect("mqtt.eclipseprojects.io")
```
