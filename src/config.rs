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

#[cfg(test)]
mod tests {
    use super::*;

    const VALID_CONFIG: &str = r#"
        [plc]
        endpoint = "modbus-tcp://localhost:502"
        device = "line_1"
        poll_interval_ms = 100
        [[plc.tags]]
        name = "temperature"
        address = "holding-register:0:UINT"

        [mqtt]
        host = "localhost"
        port = 1883
        topic_prefix = "iggy/plc"
        client_id = "test-client"

        [iggy]
        address = "localhost:8090"
        username = "iggy"
        password = "iggy"
        stream = "plc_raw"
        topic = "readings"

        [iotdb]
        endpoint = "http://localhost:18080/rest/v2/nonQuery"
        device_prefix = "root.sg"
        username = "root"
        password = "root"
    "#;

    fn parse_and_validate(contents: &str) -> Result<Config> {
        let config: Config = toml::from_str(contents)?;
        config.validate()?;
        Ok(config)
    }

    #[test]
    fn parses_and_validates_complete_config() {
        let config = parse_and_validate(VALID_CONFIG).unwrap();
        assert_eq!(config.plc.tags[0].name, "temperature");
        assert_eq!(config.mqtt.port, 1883);
        assert_eq!(config.iotdb.device_prefix, "root.sg");
    }

    #[test]
    fn rejects_zero_poll_interval() {
        let invalid = VALID_CONFIG.replace("poll_interval_ms = 100", "poll_interval_ms = 0");
        assert!(
            parse_and_validate(&invalid)
                .unwrap_err()
                .to_string()
                .contains("poll_interval_ms must be positive")
        );
    }

    #[test]
    fn rejects_invalid_tag_and_device_identifiers() {
        let invalid_tag = VALID_CONFIG.replace("name = \"temperature\"", "name = \"temp-value\"");
        assert!(parse_and_validate(&invalid_tag).is_err());

        let invalid_device = VALID_CONFIG.replace("device = \"line_1\"", "device = \"line-1\"");
        assert!(parse_and_validate(&invalid_device).is_err());
    }

    #[test]
    fn rejects_empty_tags_and_non_http_iotdb_endpoint() {
        let no_tags = VALID_CONFIG.replace(
            "        [[plc.tags]]\n        name = \"temperature\"\n        address = \"holding-register:0:UINT\"\n",
            "",
        );
        assert!(parse_and_validate(&no_tags).is_err());

        let invalid_endpoint =
            VALID_CONFIG.replace("http://localhost:18080", "tcp://localhost:18080");
        assert!(parse_and_validate(&invalid_endpoint).is_err());
    }
}
