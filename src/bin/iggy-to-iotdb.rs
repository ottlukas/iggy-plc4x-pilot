use anyhow::Result;
use futures_util::StreamExt;
use iggy::prelude::*;
use iggy_plc4x_pilot::{config::Config, iggy_client, iotdb, pipeline};
use std::time::Duration;
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
    let http = reqwest::Client::new();
    iotdb::create_database(
        &http,
        &config.iotdb.endpoint,
        &config.iotdb.username,
        &config.iotdb.password,
        &config.iotdb.device_prefix,
    )
    .await?;
    let mut consumer = client
        .consumer("iotdb-writer", &config.iggy.stream, &config.iggy.topic, 1)?
        .auto_commit(AutoCommit::Disabled)
        .polling_strategy(PollingStrategy::next())
        .init_retries(
            60,
            NonZeroIggyDuration::new(Duration::from_secs(1)).expect("one second is nonzero"),
        )
        .build();
    consumer.init().await?;

    while let Some(received) = consumer.next().await {
        let received = match received {
            Ok(message) => message,
            Err(error) => {
                tracing::warn!(%error, "Iggy poll failed");
                continue;
            }
        };
        loop {
            let http = &http;
            let endpoint = &config.iotdb.endpoint;
            let username = &config.iotdb.username;
            let password = &config.iotdb.password;
            match pipeline::write_iotdb_reading(
                |sql| async move {
                    iotdb::execute_sql(
                        http,
                        endpoint,
                        username,
                        password,
                        &sql,
                    )
                    .await
                },
                &received.message.payload,
            )
            .await
            {
                Ok(()) => break,
                Err(error) => {
                    tracing::warn!(%error, "IoTDB write failed; retaining Iggy offset and retrying");
                    tokio::time::sleep(std::time::Duration::from_secs(2)).await;
                }
            }
        }
        consumer
            .store_offset(received.message.header.offset, Some(received.partition_id))
            .await?;
    }
    consumer.shutdown().await?;
    Ok(())
}
