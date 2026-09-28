# iggy-plc4x-connector: Pilot Prototype

[![CI](https://github.com/ottlukas/iggy-plc4x-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/ottlukas/iggy-plc4x-pilot/actions/workflows/ci.yml)

An experimental PLC-to-Iggy-to-IoTDB pipeline with Apache Superset for visualization. Static Modbus TCP tags are read through Apache PLC4X, published to Apache BifroMQ over MQTT, appended to Iggy, and written into IoTDB. This validates the pipeline; it is not production software.

## Architecture

```mermaid
flowchart LR
    PLC[Modbus PLC or simulator] -->|PLC4X Java API| Bridge[plc4x-mqtt-bridge Rust]
    Bridge -->|MQTT QoS 0| Broker[Apache BifroMQ]
    Broker --> MqttRelay[mqtt-to-iggy Rust]
    MqttRelay -->|Iggy SDK| Iggy[Apache Iggy]
    Iggy --> IotdbRelay[iggy-to-iotdb Rust]
    IotdbRelay -->|REST SQL| IoTDB[Apache IoTDB]
    IoTDB -->|IoTDB SQLAlchemy dialect| Superset[Apache Superset]
```

All runtime components are Docker containers launched by Compose. The PLC4X bridge container includes a Java helper subprocess because a stable PLC4X Rust API is not available for this pilot. The two relay binaries are Rust applications using rumqttc and Iggy's Rust SDK; they are not native Iggy connector plugins. Superset is built as a custom container with IoTDB's experimental Python SQLAlchemy dialect installed.

## Run With Docker Compose

Prerequisites: Docker Engine with the Compose plugin and internet access for initial image builds and package installation. If Docker is available to the host only through Flatpak, invoke it with `flatpak-spawn --host docker compose` (for example, `flatpak-spawn --host docker compose up --build -d`).

```sh
docker compose up --build -d
```

Compose starts Apache BifroMQ, Apache Iggy, Apache IoTDB, the PLC4X bridge, the MQTT/Iggy relays, the Modbus simulator, and Apache Superset. The simulator increments holding register 0 on each read; the sample config polls it once per second. To use a real PLC, change `plc.endpoint` and the static tag addresses in [config.toml](config.toml). The PLC must be reachable from the Docker network.

The Compose configuration enables IoTDB's REST service and configures Iggy 0.9 for container access, io_uring, and the development credentials used by the relays. `seccomp:unconfined` is required by the Iggy edge image in this pilot; use a narrower custom seccomp profile for deployments that need stronger isolation.

Open Superset at [http://localhost:8088](http://localhost:8088) and sign in with `admin` / `admin`. In **Data > Databases**, choose **Other** and add a database using the SQLAlchemy URI (do not add a `/default` path; the IoTDB dialect treats it as an unsupported `database` argument):

```text
iotdb://root:root@iotdb:6667
```

The URI uses the IoTDB service name and port on Compose's private network. In SQL Lab, select this database and run `SELECT temperature FROM root.sg.line_1` after the pipeline has written its first reading. IoTDB's tree-model paths are not relational tables, so Superset table/schema discovery may fail; use SQL Lab and save a successful query as a virtual dataset when discovery is unavailable. The pilot repository does not include a `plc-control` HMI service, so an iframe targeting that hostname requires a separately deployed HMI.

Runtime verification on 2026-09-28 confirmed the Superset-to-IoTDB SQLAlchemy connection, but `SHOW TIMESERIES` returned no rows. The current `iggy-to-iotdb` consumer repeatedly reports `Partition with ID: 0 for topic with ID: 0 for stream with ID: 0 was not found`, so PLC readings have not reached IoTDB and a live chart/dashboard has not been verified. Resolve Iggy client/server partition compatibility before treating the visualization as operational.

The IoTDB REST API is also exposed on host port `18080`; Superset itself connects over the Docker network. PLC4X Modbus register addresses are one-based, so the sample's `holding-register:1:UINT` reads simulator wire register zero. Stop the stack with `docker compose down`. Persistent Superset metadata is stored in the `superset_home` named volume.

## Configuration And Payload

`config.toml` is mounted read-only into each application container. `PILOT_CONFIG` selects a different TOML file. It configures the PLC endpoint, static tags, polling interval, BifroMQ endpoint and MQTT topic prefix, Iggy endpoint/stream/topic, and IoTDB REST endpoint/device prefix.

Each MQTT message uses IoTDB's tree-model JSON shape:

```json
{"device":"root.sg.line_1","timestamp":1780000000000,"measurements":["temperature"],"values":[123]}
```

MQTT topic: `iggy/plc/line_1/temperature`. The MQTT relay stores the JSON bytes in Iggy stream `plc_raw`, topic `readings`. The IoTDB relay converts each reading into an `INSERT` statement posted to `POST /rest/v2/nonQuery`, then commits the Iggy offset only after IoTDB accepts the write. It creates the configured database if needed. Superset queries IoTDB over its SQLAlchemy/Thrift port `6667`, not through Iggy's storage.

## Scope And Limitations

- Modbus TCP only; tag lists are static. The simulator serves single holding/input registers.
- PLC4X runs through its Java API from inside the Rust bridge container. Its artifact is pinned to 0.13.1.
- MQTT uses QoS 0, no TLS, development auth, and no retained messages. Dropped messages can be lost before Iggy.
- The released Iggy connector runtime does not provide a generally available MQTT source. A Rust MQTT subscriber writes through the Iggy SDK instead; the pilot does not depend on PR #4303.
- IoTDB writes use a Rust Iggy consumer and the IoTDB 2.0 REST API, not an Iggy sink plugin. Failed writes are retried and Iggy offsets are committed after success. A crash between write and commit may repeat the same point.
- Superset uses IoTDB's experimental SQLAlchemy dialect. IoTDB documents it as not production-ready; it is included only to demonstrate dashboard connectivity.
- No production retry policy, credentials management, metrics, tag discovery, TLS, or protocol support beyond Modbus TCP. Sample passwords and anonymous development broker access are unsafe outside an isolated pilot network.

## Testing

Rust unit tests and Java unit tests use mocks or pure transformations and do not need Docker or a PLC:

```sh
cargo test --locked
mvn -f java-reader/pom.xml test
```

The Rust integration test starts the repository's BifroMQ, Iggy, IoTDB, Modbus simulator, and three pipeline services with Docker Compose. It waits for a temperature reading in IoTDB and tears down its isolated Compose project afterward. It is excluded from ordinary `cargo test` runs; run it explicitly with:

```sh
cargo test --locked --features integration --test integration -- --nocapture
```

Docker Compose configuration and startup are checked separately with:

```sh
docker compose config --quiet
docker compose up --wait --wait-timeout 90 -d bifromq iggy iotdb
docker compose down --remove-orphans
```

GitHub Actions runs formatting, Clippy, Maven compilation, Compose validation, and unit tests on pushes and pull requests. The Docker-backed end-to-end test runs on pull requests and pushes to `main`; the runtime image is built on pushes to `main`.

## Future Phases

A native Iggy MQTT source would replace `mqtt-to-iggy`: implement Iggy's connector SDK `Source` contract, package it as a C-FFI plugin, configure the connector runtime, and manage MQTT connection/subscription state in the plugin lifecycle. A complete IoTDB sink would replace `iggy-to-iotdb` with batched writes and durable ack semantics. Neither plugin is part of this pilot.
