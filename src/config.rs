use anyhow::{Context, Result};
use serde::Deserialize;
use std::path::Path;

#[derive(Clone, Debug, Deserialize)]
pub struct Config {
    pub plc: PlcConfig,
    pub mqtt: MqttConfig,
    pub iggy: IggyConfig,
    pub iotdb: IoTDBConfig,
}

#[derive(Clone, Debug, Deserialize)]
pub struct PlcConfig {
    pub endpoint: String,
    pub device: String,
    pub poll_interval_ms: u64,
    pub tags: Vec<PlcTag>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct PlcTag {
    pub name: String,
    pub address: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct MqttConfig {
    pub host: String,
    pub port: u16,
    pub topic_prefix: String,
    pub client_id: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct IggyConfig {
    pub address: String,
    pub username: String,
    pub password: String,
    pub stream: String,
    pub topic: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct IoTDBConfig {
    pub endpoint: String,
    pub device_prefix: String,
    pub username: String,
    pub password: String,
}

impl Config {
    pub fn load() -> Result<Self> {
        let path = std::env::var("PILOT_CONFIG").unwrap_or_else(|_| "/app/config.toml".into());
        let contents = std::fs::read_to_string(Path::new(&path))
            .with_context(|| format!("reading configuration {path}"))?;
        let config: Self = toml::from_str(&contents).context("parsing TOML configuration")?;
        config.validate()?;
        Ok(config)
    }

    fn validate(&self) -> Result<()> {
        anyhow::ensure!(
            self.plc.poll_interval_ms > 0,
            "plc.poll_interval_ms must be positive"
        );
        anyhow::ensure!(!self.plc.tags.is_empty(), "configure at least one PLC tag");
        anyhow::ensure!(
            !self.mqtt.topic_prefix.is_empty(),
            "mqtt.topic_prefix cannot be empty"
        );
        for tag in &self.plc.tags {
            anyhow::ensure!(is_identifier(&tag.name), "invalid tag name: {}", tag.name);
        }
        anyhow::ensure!(
            self.plc.device.split('.').all(is_identifier),
            "plc.device must contain simple path segments"
        );
        anyhow::ensure!(
            self.iotdb.endpoint.starts_with("http://")
                || self.iotdb.endpoint.starts_with("https://"),
            "iotdb.endpoint must be an HTTP URL"
        );
        anyhow::ensure!(
            self.iotdb.device_prefix.split('.').all(is_identifier),
            "iotdb.device_prefix must contain simple path segments"
        );
        Ok(())
    }
}

pub fn is_identifier(value: &str) -> bool {
    let mut chars = value.chars();
    matches!(chars.next(), Some(ch) if ch.is_ascii_alphabetic() || ch == '_')
        && chars.all(|ch| ch.is_ascii_alphanumeric() || ch == '_')
}
