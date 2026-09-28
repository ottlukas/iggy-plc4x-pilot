use rumqttc::{AsyncClient, Event, EventLoop, Incoming, MqttOptions, QoS};
use std::time::Duration;

pub fn client(host: &str, port: u16, client_id: &str) -> (AsyncClient, EventLoop) {
    let mut options = MqttOptions::new(client_id, host, port);
    options.set_keep_alive(Duration::from_secs(20));
    AsyncClient::new(options, 64)
}

pub async fn run_publisher_eventloop(mut eventloop: EventLoop) {
    loop {
        if let Err(error) = eventloop.poll().await {
            tracing::warn!(%error, "MQTT connection interrupted; reconnecting");
            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }
}

pub async fn next_publish(eventloop: &mut EventLoop) -> Option<(String, Vec<u8>)> {
    loop {
        match eventloop.poll().await {
            Ok(Event::Incoming(Incoming::Publish(message))) => {
                return Some((message.topic, message.payload.to_vec()));
            }
            Ok(Event::Incoming(Incoming::ConnAck(_))) => {
                tracing::debug!("connected to MQTT broker");
            }
            Ok(_) => {}
            Err(error) => {
                tracing::warn!(%error, "MQTT connection interrupted; reconnecting");
                tokio::time::sleep(Duration::from_secs(1)).await;
            }
        }
    }
}

pub async fn subscribe(client: &AsyncClient, topic: &str) -> anyhow::Result<()> {
    client.subscribe(topic, QoS::AtMostOnce).await?;
    Ok(())
}
