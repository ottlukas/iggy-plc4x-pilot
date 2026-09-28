# Integration Test Report

Date: 2026-09-28

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Rust unit tests | Pass | `cargo test --locked`: 12 tests passed, 0 failed. |
| Rust lint/format | Pass | `cargo fmt --all -- --check` and `cargo clippy --all-targets -- -D warnings`. |
| Java unit tests | Pass | Maven 3 tests passed, 0 failures/errors, on Java 21 using the same Maven base image as the Docker build. |
| Docker image build | Pass | Clean multi-stage runtime build compiled all Rust binaries and packaged the PLC4X Java helper; the custom Superset image also built with `apache-iotdb==2.0.11`. |
| Compose configuration | Pass | `docker compose config --quiet`. |
| Modbus/PLC4X through Iggy to IoTDB | Pass | Live IoTDB query returned `root.sg.line_1.temperature` samples after setting the one-partition consumer to partition ID `0`; writer initialized and had no fresh errors. |
| Superset connection and SQL Lab | Pass | Superset health endpoint responded successfully. `SELECT temperature FROM root.sg.line_1` rendered 825 rows in SQL Lab; IoTDB REST `LIMIT 5` returned five values. |
| Superset chart / dashboard | Blocked | Explore and saving a query dataset return HTTP 500. `apache-iotdb` 2.0.11's `IoTDBSQLCompiler.visit_select` is incompatible with Superset 4.1.1's SQLAlchemy 1.4.52: it first raises `UnboundLocalError` for `select_stmt`, and a compatibility probe then reaches unsupported `correlate_froms`. No chart or dataset was saved. |
| GitHub-hosted workflow run / GHCR push | Not run here | Workflow changes were statically inspected; this environment cannot trigger a GitHub Actions run or publish to GHCR. These will execute on a push/PR under GitHub Actions. |

## Changes Exercised

- `src/bin/iggy-to-iotdb.rs` now consumes Iggy's zero-based partition `0`. The previous value `1` was rejected by the server, preventing all IoTDB writes.
- CI now runs the repository's Docker-backed integration test, which waits for non-empty IoTDB results and Superset health rather than relying on missing Compose healthchecks and a fixed sleep.
- Main-branch image publishing now authenticates to GHCR with `GITHUB_TOKEN` and publishes both runtime and Superset images with `latest` and commit-SHA tags.

## Remaining Limitation

The IoTDB SQLAlchemy package installed by the project is experimental. Direct SQL Lab querying works, but `apache-iotdb` 2.0.11's chart compiler targets a different SQLAlchemy API than Superset 4.1.1 provides. A bounded patch was not maintainable because fixing initial undefined state exposed further API incompatibilities. Upgrade to a compatible dialect/Superset pair and repeat Explore/chart validation before claiming dashboard support. The local chart attempt did not save a dataset or chart.
