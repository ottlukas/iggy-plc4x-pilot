use anyhow::Result;
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::TcpListener,
};
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();
    let listener = TcpListener::bind("0.0.0.0:502").await?;
    tracing::info!("Modbus TCP simulator listening on 0.0.0.0:502");
    loop {
        let (mut socket, _) = listener.accept().await?;
        tokio::spawn(async move {
            let mut register: u16 = 100;
            loop {
                let mut header = [0_u8; 7];
                if socket.read_exact(&mut header).await.is_err() {
                    break;
                }
                let length = u16::from_be_bytes([header[4], header[5]]) as usize;
                if length < 2 || length > 254 {
                    break;
                }
                let mut pdu = vec![0_u8; length - 1];
                if socket.read_exact(&mut pdu).await.is_err() {
                    break;
                }
                let Some(response) = response_frame(header, &pdu, register) else {
                    break;
                };
                register = register.wrapping_add(1);
                if socket.write_all(&response).await.is_err() {
                    break;
                }
            }
        });
    }
}

fn response_frame(header: [u8; 7], request: &[u8], register: u16) -> Option<Vec<u8>> {
    if request.len() != 5
        || !matches!(request[0], 3 | 4)
        || request[1..3] != [0, 0]
        || request[3..5] != [0, 1]
    {
        return None;
    }

    let mut response = Vec::with_capacity(11);
    response.extend_from_slice(&header[..4]);
    response.extend_from_slice(&5_u16.to_be_bytes());
    response.push(header[6]);
    response.extend_from_slice(&[request[0], 2, (register >> 8) as u8, register as u8]);
    Some(response)
}

#[cfg(test)]
mod tests {
    use super::response_frame;

    #[test]
    fn declared_length_matches_response_payload() {
        let header = [0, 1, 0, 0, 0, 6, 1];
        let response = response_frame(header, &[3, 0, 0, 0, 1], 123).unwrap();
        let declared = u16::from_be_bytes([response[4], response[5]]) as usize;
        assert_eq!(declared, response.len() - 6);
        assert_eq!(&response[7..], &[3, 2, 0, 123]);
    }

    #[test]
    fn unsupported_registers_are_rejected() {
        let header = [0, 1, 0, 0, 0, 6, 1];
        assert!(response_frame(header, &[3, 0, 1, 0, 1], 123).is_none());
        assert!(response_frame(header, &[3, 0, 0, 0, 2], 123).is_none());
    }
}
