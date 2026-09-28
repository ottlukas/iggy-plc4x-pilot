use anyhow::{Context, Result};
use serde_json::Value;
use std::future::Future;

pub fn reading_topic(topic_prefix: &str, payload: &[u8]) -> Result<String> {
    let reading: Value = serde_json::from_slice(payload).context("decoding PLC reading")?;
    let device = reading["device"]
        .as_str()
        .context("reading missing device")?;
    let measurement = reading["measurements"]
        .as_array()
        .and_then(|items| items.first())
        .and_then(Value::as_str)
        .context("reading missing measurement")?;
    anyhow::ensure!(
        !topic_prefix.trim_matches('/').is_empty(),
        "empty MQTT topic prefix"
    );
    Ok(format!(
        "{}/{device}/{measurement}",
        topic_prefix.trim_end_matches('/')
    ))
}

pub async fn publish_reading<F, Fut>(publisher: F, topic_prefix: &str, payload: &[u8]) -> Result<()>
where
    F: FnOnce(String, Vec<u8>) -> Fut,
    Fut: Future<Output = Result<()>>,
{
    let topic = reading_topic(topic_prefix, payload)?;
    publisher(topic, payload.to_vec()).await
}

pub async fn forward_mqtt_payload<F, Fut>(writer: F, payload: &[u8]) -> Result<()>
where
    F: FnOnce(String) -> Fut,
    Fut: Future<Output = Result<()>>,
{
    let payload = std::str::from_utf8(payload).context("MQTT payload is not UTF-8")?;
    writer(payload.to_owned()).await
}

pub async fn write_iotdb_reading<F, Fut>(client: F, payload: &[u8]) -> Result<()>
where
    F: FnOnce(String) -> Fut,
    Fut: Future<Output = Result<()>>,
{
    let reading: crate::iotdb::Reading =
        serde_json::from_slice(payload).context("decoding PLC reading")?;
    client(reading.insert_sql()?).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    const PAYLOAD: &[u8] = br#"{"device":"root.sg.line_1","timestamp":123,"measurements":["temperature"],"values":[21.5]}"#;

    #[tokio::test]
    async fn bridge_publishes_reading_to_device_measurement_topic() {
        let published = Mutex::new(Vec::new());
        publish_reading(
            |topic, payload| async {
                published.lock().unwrap().push((topic, payload));
                Ok(())
            },
            "iggy/plc/",
            PAYLOAD,
        )
        .await
        .unwrap();
        assert_eq!(
            published.lock().unwrap().as_slice(),
            &[(
                "iggy/plc/root.sg.line_1/temperature".into(),
                PAYLOAD.to_vec()
            )]
        );
    }

    #[tokio::test]
    async fn mqtt_relay_forwards_payload_to_mock_iggy_writer() {
        let messages = Mutex::new(Vec::new());
        forward_mqtt_payload(
            |payload| async {
                messages.lock().unwrap().push(payload);
                Ok(())
            },
            PAYLOAD,
        )
        .await
        .unwrap();
        assert_eq!(
            messages.lock().unwrap().as_slice(),
            &[std::str::from_utf8(PAYLOAD).unwrap()]
        );
    }

    #[tokio::test]
    async fn iotdb_relay_writes_validated_sql_through_mock_client() {
        let statements = Mutex::new(Vec::new());
        write_iotdb_reading(
            |sql| async {
                statements.lock().unwrap().push(sql);
                Ok(())
            },
            PAYLOAD,
        )
        .await
        .unwrap();
        assert_eq!(
            statements.lock().unwrap().as_slice(),
            &["INSERT INTO root.sg.line_1(time, temperature) VALUES (123, 21.5)"]
        );
    }

    #[tokio::test]
    async fn relays_reject_invalid_payloads_before_writing() {
        assert!(
            forward_mqtt_payload(|_| async { Ok(()) }, &[0xff])
                .await
                .is_err()
        );
        assert!(
            write_iotdb_reading(|_| async { Ok(()) }, br#"{"device":"root.sg;drop"}"#)
                .await
                .is_err()
        );
        assert!(reading_topic("iggy/plc", br#"{"device":"root.sg.line_1"}"#).is_err());
    }
}
