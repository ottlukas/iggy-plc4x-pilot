use anyhow::{Context, Result};
use iggy_plc4x_pilot::{config::Config, mqtt};
use rumqttc::QoS;
use std::process::Stdio;
use tokio::{
    io::{AsyncBufReadExt, BufReader},
    process::Command,
};
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();
    let config = Config::load()?;
    let (client, eventloop) = mqtt::client(
        &config.mqtt.host,
        config.mqtt.port,
        &format!("{}-bridge", config.mqtt.client_id),
    );
    tokio::spawn(mqtt::run_publisher_eventloop(eventloop));

    let mut command = Command::new("java");
    command
        .arg("-jar")
        .arg("/app/plc4x-reader.jar")
        .arg("--endpoint")
        .arg(&config.plc.endpoint)
        .arg("--device")
        .arg(&config.plc.device)
        .arg("--device-prefix")
        .arg(&config.iotdb.device_prefix)
        .arg("--poll-ms")
        .arg(config.plc.poll_interval_ms.to_string())
        .arg("--topic-prefix")
        .arg(&config.mqtt.topic_prefix);
    for tag in &config.plc.tags {
        command
            .arg("--tag")
            .arg(format!("{}={}", tag.name, tag.address));
    }
    command.stdout(Stdio::piped()).stderr(Stdio::inherit());
    let mut child = command.spawn().context("starting PLC4X Java reader")?;
    let stdout = child
        .stdout
        .take()
        .context("capturing PLC4X reader output")?;
    let mut lines = BufReader::new(stdout).lines();

    while let Some(line) = lines.next_line().await? {
        let Some(payload) = line.strip_prefix("READING:") else {
            tracing::debug!(line, "PLC4X reader output");
            continue;
        };
        let value: serde_json::Value =
            serde_json::from_str(payload).context("invalid reading from PLC4X helper")?;
        let device = value["device"].as_str().context("reading missing device")?;
        let measurement = value["measurements"][0]
            .as_str()
            .context("reading missing measurement")?;
        let topic = format!(
            "{}/{}/{}",
            config.mqtt.topic_prefix.trim_end_matches('/'),
            device,
            measurement
        );
        if let Err(error) = client.publish(topic, QoS::AtMostOnce, false, payload).await {
            tracing::warn!(%error, "MQTT publish failed; the next PLC poll will retry");
        }
    }

    let status = child.wait().await?;
    anyhow::ensure!(
        !status.success(),
        "PLC4X reader exited unexpectedly: {status}"
    );
    Ok(())
}
