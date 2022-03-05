[![GitHub Release](https://img.shields.io/github/release/toreamun/asyncio-paho)](https://github.com/toreamun/asyncio-paho/releases)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/toreamun/asyncio-paho.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/toreamun/asyncio-paho/context:python)
[![CodeQL](https://github.com/toreamun/asyncio-paho/workflows/CodeQL/badge.svg)](https://github.com/toreamun/asyncio-paho/actions?query=workflow%3ACodeQL&)
[![License](https://img.shields.io/github/license/toreamun/asyncio-paho)](LICENSE)
![Project Maintenance](https://img.shields.io/badge/maintainer-Tore%20Amundsen%20%40toreamun-blue.svg)
[![buy me a coffee](https://img.shields.io/badge/If%20you%20like%20it-Buy%20me%20a%20coffee-orange.svg)](https://www.buymeacoffee.com/toreamun)


# Asynchronous I/O (asyncio) Paho MQTT client
A [Paho MQTT](https://github.com/eclipse/paho.mqtt.python) client supporting [asyncio](https://docs.python.org/3/library/asyncio.html) loop without additional setup. Forget about configuring the [Paha network-loop](https://github.com/eclipse/paho.mqtt.python#network-loop). The client can almost be used as a drop-in replacement for Paho Client. The asyncio loop is automatically configured when you connect. You should use [connect_async](https://github.com/eclipse/paho.mqtt.python#connect_async) to connect to avoid blocking.



```python
client = AsyncioPahoClient()
client.connect_async("mqtt.eclipseprojects.io")

# do mqtt stuff

client.Disconnect()

```

## Asynchronous Context Manager
The client is an Asynchronous Context Manager and can be used with the Python with statement to atomatically disconnect and clean up.

```python
async with AsyncioPahoClient() as client:
    client.connect_async("mqtt.eclipseprojects.io")
    
    # do mqtt stuff - client.Disconnect() is called when exiting context.

```

