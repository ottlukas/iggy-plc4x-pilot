use anyhow::Result;
use iggy::prelude::*;

pub async fn connect(address: &str, username: &str, password: &str) -> Result<IggyClient> {
    let client = IggyClientBuilder::new()
        .with_tcp()
        .with_server_address(address.to_owned())
        .build()?;
    client.connect().await?;
    client.login_user(username, password).await?;
    Ok(client)
}
