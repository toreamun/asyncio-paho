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

