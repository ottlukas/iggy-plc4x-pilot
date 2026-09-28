use anyhow::Result;
use iggy::prelude::*;
use iggy_plc4x_pilot::{config::Config, iggy_client, mqtt, pipeline};
use rumqttc::{Event, Incoming};
use std::str::FromStr;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();
    let config = Config::load()?;
    let client = iggy_client::connect(
        &config.iggy.address,
        &config.iggy.username,
        &config.iggy.password,
    )
    .await?;
    let producer = client
        .producer(&config.iggy.stream, &config.iggy.topic)?
        .build();
    producer.init().await?;

    let (mqtt_client, mut eventloop) = mqtt::client(
        &config.mqtt.host,
        config.mqtt.port,
        &format!("{}-iggy", config.mqtt.client_id),
    );
    let filter = format!("{}/#", config.mqtt.topic_prefix.trim_end_matches('/'));
    loop {
        match eventloop.poll().await {
            Ok(Event::Incoming(Incoming::ConnAck(_))) => {
                mqtt::subscribe(&mqtt_client, &filter).await?
            }
            Ok(Event::Incoming(Incoming::Publish(message))) => {
                let producer = &producer;
                pipeline::forward_mqtt_payload(
                    |payload| async move {
                        producer.send_one(IggyMessage::from_str(&payload)?).await?;
                        Ok(())
                    },
                    &message.payload,
                )
                .await?;
                tracing::debug!(topic = %message.topic, "appended MQTT reading to Iggy");
            }
            Ok(_) => {}
            Err(error) => {
                tracing::warn!(%error, "MQTT source relay disconnected; reconnecting");
                tokio::time::sleep(std::time::Duration::from_secs(1)).await;
            }
        }
    }
}
