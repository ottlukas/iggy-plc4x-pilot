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
    Superset -->|Dashboard| HMI[HMI Control Panel]
```

All runtime components are Docker containers launched by Compose. The PLC4X bridge container includes a Java helper subprocess because a stable PLC4X Rust API is not available for this pilot. The two relay binaries are Rust applications using rumqttc and Iggy's Rust SDK; they are not native Iggy connector plugins. Superset is built as a custom container with IoTDB's experimental Python SQLAlchemy dialect installed. The HMI control panel provides a web-based interface for monitoring and controlling the pipeline.

## Run With Docker Compose

Prerequisites: Docker Engine with the Compose plugin and internet access for initial image builds and package installation. If Docker is available to the host only through Flatpak, invoke it with `flatpak-spawn --host docker compose` (for example, `flatpak-spawn --host docker compose up --build -d`).

```sh
docker compose up --build -d
```

Compose starts 9 services: Apache BifroMQ (MQTT broker), Apache Iggy (streaming storage), Apache IoTDB (time-series database), Modbus simulator, PLC4X bridge, MQTT-to-Iggy relay, Iggy-to-IoTDB relay, Apache Superset (visualization), and HMI control panel. The simulator increments holding register 0 on each read; the sample config polls it once per second. To use a real PLC, change `plc.endpoint` and the static tag addresses in [config.toml](config.toml). The PLC must be reachable from the Docker network.

The Compose configuration enables IoTDB's REST service and uses the Iggy edge image with development credentials for the relays. `seccomp:unconfined` is required by the Iggy image in this pilot; use a narrower custom seccomp profile for deployments that need stronger isolation.

### Accessing Services

| Service | Port | URL | Credentials |
|---------|------|-----|-------------|
| Apache BifroMQ | 1883 | MQTT broker | Anonymous (dev mode) |
| Apache Iggy | 8090 | `http://localhost:8090` | `iggy` / `iggy` |
| Apache IoTDB REST | 18080 | `http://localhost:18080` | `root` / `root` |
| Apache IoTDB SQL | 6667 | Thrift interface | `root` / `root` |
| Apache Superset | 8088 | `http://localhost:8088` | `admin` / `admin` |
| HMI Control Panel | 8080 | `http://localhost:8080` | N/A |

### Superset Configuration

Superset is pre-configured with an IoTDB database connection and a sample dashboard. After starting the stack:

1. Open Superset at [http://localhost:8088](http://localhost:8088) and sign in with `admin` / `admin`.
2. The IoTDB database connection is automatically created with URI: `iotdb://root:root@iotdb:6667`
3. A sample dashboard "PLC IoT Data Dashboard" is created with:
   - Temperature time series chart
   - Current temperature gauge
   - Recent PLC readings table

**Note:** IoTDB's tree-model paths are not relational tables, so Superset table/schema discovery may fail. Direct SQL Lab queries are verified; chart Explore currently fails because `apache-iotdb` 2.0.11's compiler is incompatible with Superset 4.1.1's SQLAlchemy 1.4.52. Do not treat charts/dashboards as supported until a compatible dialect release is available. For now, use SQL Lab for querying.

### HMI Control Panel

The HMI (Human-Machine Interface) at [http://localhost:8080](http://localhost:8080) provides:
- Real-time pipeline status overview with visual flow diagram
- Service health monitoring for all 9 services
- Flow control (START/STOP pipeline buttons)
- Live PLC readings display with timestamp and status
- Diagnostic logs viewer for each service
- Configuration viewer (read-only)
- Auto-refresh every 3 seconds

The HMI connects to the Docker socket to control services. On Linux/macOS, ensure `/var/run/docker.sock` is accessible. On Windows, Docker Desktop automatically mounts the socket.

### Manual Database Setup (if needed)

If the automatic Superset initialization fails, manually add the IoTDB database:

1. Go to **Data > Databases**
2. Click **+ Database**
3. Select **Other** as the database type
4. Enter the SQLAlchemy URI (do not add a `/default` path):

```text
iotdb://root:root@iotdb:6667
```

5. Click **Test Connection** and then **Save**

In SQL Lab, select this database and run `SELECT temperature FROM root.sg.line_1` after the pipeline has written its first reading.

## Configuration And Payload

`config.toml` is mounted read-only into each application container. `PILOT_CONFIG` selects a different TOML file. It configures the PLC endpoint, static tags, polling interval, BifroMQ endpoint and MQTT topic prefix, Iggy endpoint/stream/topic, and IoTDB REST endpoint/device prefix.

Each MQTT message uses IoTDB's tree-model JSON shape:

```json
{"device":"root.sg.line_1","timestamp":1780000000000,"measurements":["temperature"],"values":[123]}
```

MQTT topic: `iggy/plc/line_1/temperature`. The MQTT relay stores the JSON bytes in Iggy stream `plc_raw`, topic `readings`. The IoTDB relay converts each reading into an `INSERT` statement posted to `POST /rest/v2/nonQuery`, then commits the Iggy offset only after IoTDB accepts the write. It creates the configured database if needed. Superset queries IoTDB over its SQLAlchemy/Thrift port `6667`, not through Iggy's storage.

## Scope And Limitations

- Modbus TCP only; tag lists are static. The simulator serves single holding/input registers.
- PLC4X runs through its Java API from inside the Rust bridge container. Its artifact is pinned to 0.13.0.
- MQTT uses QoS 0, no TLS, development auth, and no retained messages. Dropped messages can be lost before Iggy.
- The released Iggy connector runtime does not provide a generally available MQTT source. A Rust MQTT subscriber writes through the Iggy SDK instead; the pilot does not depend on PR #4303.
- IoTDB writes use a Rust Iggy consumer and the IoTDB 2.0 REST API, not an Iggy sink plugin. Failed writes are retried and Iggy offsets are committed after success. A crash between write and commit may repeat the same point.
- Superset uses IoTDB's experimental SQLAlchemy dialect. IoTDB documents it as not production-ready; it is included only to demonstrate dashboard connectivity.
- No production retry policy, credentials management, metrics, tag discovery, TLS, or protocol support beyond Modbus TCP. Sample passwords and anonymous development broker access are unsafe outside an isolated pilot network.

## Testing

### Unit Tests

Rust unit tests and Java unit tests use mocks or pure transformations and do not need Docker or a PLC:

```sh
cargo test --locked
mvn -f java-reader/pom.xml test
```

### Integration Tests

The Rust integration tests start the repository's services with Docker Compose and verify the end-to-end pipeline:

```sh
# Run all integration tests
cargo test --locked --features integration --test integration -- --nocapture

# Run specific tests
cargo test --locked --features integration --test integration modbus_to_iotdb_pipeline_writes_a_reading -- --nocapture
cargo test --locked --features integration --test integration superset_iotdb_connection_works -- --nocapture
cargo test --locked --features integration --test integration hmi_control_api_works -- --nocapture
```

The integration tests verify:
1. **End-to-end pipeline**: Modbus simulator → PLC4X → MQTT → Iggy → IoTDB
2. **Superset-IoTDB connection**: Superset can connect to IoTDB and query data
3. **HMI control API**: HMI can control the pipeline and report status

### Docker Compose Validation

Check Docker Compose configuration and startup:

```sh
docker compose config --quiet
docker compose up --wait --wait-timeout 90 -d bifromq iggy iotdb
docker compose down --remove-orphans
```

## CI/CD

GitHub Actions runs the following on pushes and pull requests:

1. **Lint and configuration**: `cargo fmt`, `cargo clippy`, Maven compile, Docker Compose config validation
2. **Unit tests**: Rust and Java unit tests
3. **Integration tests**: Full pipeline tests (on PRs and main branch pushes)
4. **Image building**: Publishes runtime, Superset, and HMI images to GitHub Container Registry (on main branch pushes)

Images are published as:
- `ghcr.io/ottlukas/iggy-plc4x-pilot:latest` (and with commit SHA)
- `ghcr.io/ottlukas/iggy-plc4x-superset:latest` (and with commit SHA)
- `ghcr.io/ottlukas/iggy-plc4x-hmi:latest` (and with commit SHA)

## Project Structure

```
iggy-plc4x-pilot/
├── Cargo.toml                    # Rust workspace configuration
├── Cargo.lock
├── config.toml                   # Pipeline configuration
├── docker-compose.yml            # Docker Compose services
├── Dockerfile                    # Main Dockerfile (Rust + Java)
├── Dockerfile.superset           # Superset Dockerfile
├── README.md                     # This file
├── .github/workflows/
│   └── ci.yml                    # GitHub Actions workflow
├── hmi/
│   ├── Dockerfile                # HMI Dockerfile
│   ├── main.py                   # FastAPI HMI application
│   └── requirements.txt
├── java-reader/
│   ├── pom.xml
│   └── src/
│       └── main/java/org/apache/iggy/pilot/Plc4xReader.java
├── src/
│   ├── bin/
│   │   ├── plc4x-mqtt-bridge.rs  # PLC4X to MQTT bridge
│   │   ├── mqtt-to-iggy.rs        # MQTT to Iggy relay
│   │   ├── iggy-to-iotdb.rs       # Iggy to IoTDB relay
│   │   └── modbus-simulator.rs   # Modbus TCP simulator
│   ├── config.rs                  # TOML configuration parsing
│   ├── iggy_client.rs             # Iggy client helper
│   ├── iotdb.rs                   # IoTDB REST client
│   ├── mqtt.rs                    # MQTT client helper
│   └── lib.rs
├── superset/
│   ├── databases/
│   │   └── iotdb.yaml             # Superset IoTDB database config
│   └── dashboards/
│       └── plc_iot_dashboard.json # Sample dashboard
├── tests/
│   └── integration.rs             # Integration tests
├── init_superset.py              # Superset initialization script
├── start-superset.sh              # Superset startup script
├── superset_config.py            # Superset configuration
├── TEST_REPORT.md                # Test report
└── TROUBLESHOOTING.md             # Troubleshooting guide
```

## Future Phases

A native Iggy MQTT source would replace `mqtt-to-iggy`: implement Iggy's connector SDK `Source` contract, package it as a C-FFI plugin, configure the connector runtime, and manage MQTT connection/subscription state in the plugin lifecycle. A complete IoTDB sink would replace `iggy-to-iotdb` with batched writes and durable ack semantics. Neither plugin is part of this pilot.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`cargo test --locked` and `mvn -f java-reader/pom.xml test`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
