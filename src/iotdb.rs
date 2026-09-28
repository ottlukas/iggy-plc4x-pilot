use anyhow::{Context, Result, bail};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct Reading {
    pub device: String,
    pub timestamp: i64,
    pub measurements: Vec<String>,
    pub values: Vec<serde_json::Value>,
}

impl Reading {
    pub fn insert_sql(&self) -> Result<String> {
        anyhow::ensure!(
            self.measurements.len() == self.values.len(),
            "measurement/value count mismatch"
        );
        anyhow::ensure!(
            !self.measurements.is_empty(),
            "reading contains no measurements"
        );
        anyhow::ensure!(
            self.device.split('.').all(super::config::is_identifier),
            "invalid IoTDB device path"
        );
        anyhow::ensure!(
            self.measurements
                .iter()
                .all(|name| super::config::is_identifier(name)),
            "invalid IoTDB measurement name"
        );

        let measurements = self.measurements.join(", ");
        let values = self
            .values
            .iter()
            .map(sql_value)
            .collect::<Result<Vec<_>>>()?
            .join(", ");
        Ok(format!(
            "INSERT INTO {}(time, {}) VALUES ({}, {})",
            self.device, measurements, self.timestamp, values
        ))
    }
}

fn sql_value(value: &serde_json::Value) -> Result<String> {
    match value {
        serde_json::Value::Number(number) => Ok(number.to_string()),
        serde_json::Value::Bool(value) => Ok(value.to_string()),
        serde_json::Value::String(value) => Ok(format!("'{}'", value.replace('\'', "''"))),
        _ => bail!("unsupported IoTDB scalar value: {value}"),
    }
}

pub async fn write(
    client: &reqwest::Client,
    endpoint: &str,
    user: &str,
    password: &str,
    payload: &[u8],
) -> Result<()> {
    let reading: Reading = serde_json::from_slice(payload).context("decoding PLC reading")?;
    let sql = reading.insert_sql()?;
    let response = client
        .post(endpoint)
        .basic_auth(user, Some(password))
        .json(&serde_json::json!({ "sql": sql }))
        .send()
        .await
        .context("sending insert to IoTDB REST API")?;
    let status = response.status();
    let body = response.text().await.unwrap_or_default();
    let rejected = serde_json::from_str::<serde_json::Value>(&body)
        .ok()
        .and_then(|response| response.get("code").and_then(serde_json::Value::as_i64))
        .is_some_and(|code| code != 200);
    if !status.is_success() || rejected {
        bail!("IoTDB rejected insert ({status}): {body}");
    }
    Ok(())
}

pub async fn create_database(
    client: &reqwest::Client,
    endpoint: &str,
    user: &str,
    password: &str,
    database: &str,
) -> Result<()> {
    anyhow::ensure!(
        database.split('.').all(super::config::is_identifier),
        "invalid IoTDB database path"
    );
    let response = client
        .post(endpoint)
        .basic_auth(user, Some(password))
        .json(&serde_json::json!({ "sql": format!("CREATE DATABASE IF NOT EXISTS {database}") }))
        .send()
        .await
        .context("creating IoTDB database")?;
    let status = response.status();
    let body = response.text().await.unwrap_or_default();
    let rejected = serde_json::from_str::<serde_json::Value>(&body)
        .ok()
        .and_then(|response| response.get("code").and_then(serde_json::Value::as_i64))
        .is_some_and(|code| code != 200);
    if !status.is_success() || rejected {
        bail!("IoTDB database setup failed ({status}): {body}");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_tree_insert_and_escapes_strings() {
        let reading = Reading {
            device: "root.sg.line_1".into(),
            timestamp: 123,
            measurements: vec!["temperature".into(), "status".into()],
            values: vec![serde_json::json!(21.5), serde_json::json!("operator's")],
        };
        assert_eq!(
            reading.insert_sql().unwrap(),
            r#"INSERT INTO root.sg.line_1(time, temperature, status) VALUES (123, 21.5, 'operator''s')"#
        );
    }

    #[test]
    fn rejects_sql_identifiers_from_payload() {
        let reading = Reading {
            device: "root.sg;delete".into(),
            timestamp: 1,
            measurements: vec!["x".into()],
            values: vec![serde_json::json!(1)],
        };
        assert!(reading.insert_sql().is_err());
    }
}
