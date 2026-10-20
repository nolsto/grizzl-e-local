# Grizzl-E Local Client

Python client for interacting with a United Chargers Grizzl-E EVSE device on your network.

## Usage

At the heart of the library is a client for reading from and writing to a "document".
The document represents all known fields from the device firmware's web interface.

### The Client — reading, writing, and polling

The `Client` communicates with the device over HTTP.
With it, you can get and set data the firmware recognizes (see `src/grizzl_e_local/document/versions.py` for all known fields and their data types).
The client can also poll for data on a given interval.

If your device is configured with an HTTP username or password, pass them to the constructor:

```python
async with Client("http://192.168.4.1", username="admin", password="secret") as client: ...
```

All subsequent requests include basic authentication.

```python
from grizzl_e_local import Client

async with Client("http://192.168.4.1") as client:
    # Read and cache the full document
    doc = await client.get_document()
    print(doc.sessionTime)

    # Read a single field, always fresh from the device
    voltage = await client.get("voltMeas1")

    # Write a single field value
    await client.set("evseEnabled", 1)

    # Write multiple field values in one request
    await client.set_many(
        currentSet=30,
        sh1CurrentEnable=1,
    )

    # Poll the device every second, yielding a fresh document each cycle
    async for doc in client.watch(interval=1.0):
        print(f"Session: {doc.sessionTime} seconds")
```

### Transactions — batching writes

To batch writes to the device, use the `Client.transaction` context manager.
Write operations accumulate and are submitted to the device together when the context exits.

```python
async with Client("http://192.168.4.1") as client:
    async with client.transaction():
        await client.set("currentSet", 30)
        await client.set("evseEnabled", 1)
        # Batched writes — no network call yet
```

Use the return value of the context manager to easily manage the batched writes in a dictionary.

```python
async with Client("http://192.168.4.1") as client:
    async with client.transaction() as batch:
        batch["currentSet"] = 30
        batch["sh1CurrentEnable"] = 1
```

The boolean `refresh` flag ensures the client fetches an updated document after the write completes. Use it to confirm changes took effect or to read back values that depend on the new configuration.

```python
async with Client("http://192.168.4.1") as client:
    print(await client.get_document().sh1CurrentEnable)  # original from device: 0

    async with client.transaction(refresh=True) as batch:
        batch["sh1CurrentEnable"] = 1

    # After the context exits, a fresh document is present.
    print(client.document.sh1CurrentEnable)  # latest from device: 1
```

### The Device — an ergonomic abstraction of the hardware

Since it is taxing to hold a mental map of the device firmware's data fields and their purpose and data type, the client also provides the `Client.device` interface.

`Client.device` exposes a tree of components based on the UI of the web interface, mirroring the device's logical structure.

#### The Problem

All device fields read or written by `client.get` or `client.set`/`client.set_many` are limited to the data types used by the device firmware: `str | int | float` (note the use of 0/1 to represent off/on). Device fields are numerous, vaguely (and inconsistently) named, and exist in a large, flat namespace.

#### The Solution

`Client.device` components use sensible Python types such as `bool`, `Decimal`, `datetime`, `timedelta`, etc. to transparently represent values without requiring the user to decode them to their primitive types.

`Client.device` components also define convenience methods to write data to the device. Some examples:

```python
from grizzl_e_local import Client

async with Client("http://192.168.4.1") as client:
    async with client.transaction():
        client.device.toggle()  # enables or disables the EVSE (optional `on: bool` parameter)
        client.device.sync_time()  # syncs the device firmware's time to this system's clock
        client.device.limits.suspend()  # suspends all time, energy, and cost limits
        client.device.meters[1].reset()  # resets the second meter
```

The device can be used in a synchronous style with attributes. Mutating values outside a transaction is not allowed.

```python
from grizzl_e_local import Client

async with Client("http://192.168.4.1") as client:
    # Data must be fetched before client.device values are accessed.
    await client.get_document()

    limit = client.device.schedules[0].current_limit
    print(f"Schedule 1 enabled: {limit.is_enabled}")
    print(f"Schedule 1 limit: {limit.value}")

    # Writing via attribute assignment or mutation method must be done inside a transaction
    async with client.transaction(refresh=True):
        client.device.schedules[0].current_limit.value = 30
        client.device.schedules[0].toggle(on=True)
```

Device values are kept up-to-date with the underlying document fields reported by the device firmware.

In addition to reading and writing device values via attribute-style access and assignment inside a transaction, async `.get()` and `.set()` methods can also be used. Unlike sync writes, `.set()` submits each write immediately rather than batching it into a surrounding transaction, and `.get()` fetches fresh data automatically.

```python
from grizzl_e_local import Client

async with Client("http://192.168.4.1") as client:
    await client.device.schedules[0].current_limit.set("value", 30)
    is_enabled = await client.device.schedules[0].current_limit.get("is_enabled")
    print(f"Schedule 1 enabled: {is_enabled}")
    await client.device.schedules[0].toggle_async(on=not is_enabled)
```

All device components are explicitly typed. Your IDE can provide you hints while accessing them.
