FROM rust:1-bookworm AS rust-build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked --bins

FROM maven:3.9.9-eclipse-temurin-21 AS plc4x-build
WORKDIR /src
COPY java-reader/pom.xml ./pom.xml
COPY java-reader/src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=rust-build /src/target/release/plc4x-mqtt-bridge /app/
COPY --from=rust-build /src/target/release/mqtt-to-iggy /app/
COPY --from=rust-build /src/target/release/iggy-to-iotdb /app/
COPY --from=rust-build /src/target/release/modbus-simulator /app/
COPY --from=plc4x-build /src/target/plc4x-reader.jar /app/
ENV PILOT_CONFIG=/app/config.toml