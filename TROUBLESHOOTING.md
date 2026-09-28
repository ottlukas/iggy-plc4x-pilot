# Troubleshooting

## Modbus or PLC4X cannot connect

- Confirm the PLC/simulator address and TCP port are reachable from the Compose network. The sample uses `modbus-tcp://modbus-simulator:502`; a physical PLC must be reachable from Docker and configured in `config.toml`.
- Check the configured tag address and PLC register type. The simulator exposes holding/input registers; PLC4X Modbus addresses are one-based, so `holding-register:1:UINT` reads simulator register zero.
- Inspect `docker compose logs plc4x-bridge modbus-simulator`. The bridge starts a Java PLC4X reader subprocess; also verify that the container image built the `plc4x-reader.jar` artifact.

## MQTT readings are not reaching Iggy

- Check `docker compose logs bifromq plc4x-bridge mqtt-to-iggy` for broker connection and subscription errors.
- Confirm the topic prefix in `config.toml` matches the bridge publish topic and relay subscription filter. The default filter is `iggy/plc/#`.
- Verify the Iggy endpoint and development credentials match the Compose service configuration. The sample credentials and anonymous MQTT setup are for isolated development only.

## Iggy consumer reports a missing partition

- The sample producer creates a topic with one partition. Its partition ID is zero; keep the standalone consumer pinned to partition `0` in `src/bin/iggy-to-iotdb.rs`.
- Inspect `docker compose logs iggy mqtt-to-iggy iggy-to-iotdb`. Confirm the producer reports that it created/found stream `plc_raw` and topic `readings`, then check that the consumer is not repeatedly reporting a missing partition.
- Ensure the Iggy server image and Rust SDK are compatible. Avoid changing the floating `apache/iggy:edge` tag without rerunning the Docker-backed integration test.

## IoTDB query returns no rows

- Check `docker compose logs iotdb iggy-to-iotdb` for REST authentication, database creation, and write errors.
- Query the REST endpoint with `curl -u root:root -H 'Content-Type: application/json' -d '{"sql":"SELECT temperature FROM root.sg.line_1"}' http://localhost:18080/rest/v2/query`.
- Confirm `config.toml` points to `http://iotdb:18080/rest/v2/nonQuery` from inside Compose, and that the configured device prefix and tag produce the expected path `root.sg.line_1.temperature`.

## Superset cannot query IoTDB

- Confirm Superset is healthy at `http://localhost:8088/health` and that the configured SQLAlchemy URI is `iotdb://root:root@iotdb:6667` (do not append `/default`).
- In SQL Lab, select the IoTDB database and run `SELECT temperature FROM root.sg.line_1` after IoTDB contains samples. IoTDB tree-model paths are not relational tables, so schema/table discovery can fail even when direct SQL works.
- Superset chart Explore is currently incompatible: this image pins `apache-iotdb` 2.0.11 while Superset 4.1.1 uses SQLAlchemy 1.4.52. Direct SQL Lab queries work, but chart compilation fails; use SQL Lab for validation until a compatible driver release is available.
- Review Superset and IoTDB logs with `docker compose logs superset iotdb`. The IoTDB dialect used here is experimental and intended for this pilot.
