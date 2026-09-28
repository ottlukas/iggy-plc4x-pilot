use std::{process::Command, time::Duration};

struct ComposeStack {
    project: String,
    manifest_dir: String,
}

impl ComposeStack {
    fn command(&self) -> Command {
        let mut command = Command::new("docker");
        command
            .current_dir(&self.manifest_dir)
            .args(["compose", "-p", &self.project]);
        command
    }

    fn start(&self) -> Result<(), String> {
        let output = self
            .command()
            .args([
                "up",
                "--build",
                "-d",
                "bifromq",
                "iggy",
                "iotdb",
                "modbus-simulator",
                "plc4x-bridge",
                "mqtt-to-iggy",
                "iggy-to-iotdb",
                "superset",
            ])
            .output()
            .map_err(|error| format!("starting Compose stack: {error}"))?;
        if !output.status.success() {
            return Err(format!(
                "Compose startup failed: {}{}",
                String::from_utf8_lossy(&output.stdout),
                String::from_utf8_lossy(&output.stderr)
            ));
        }
        Ok(())
    }
}

impl Drop for ComposeStack {
    fn drop(&mut self) {
        let _ = self
            .command()
            .args(["down", "--volumes", "--remove-orphans"])
            .status();
    }
}

#[tokio::test]
async fn modbus_to_iotdb_pipeline_writes_a_reading() {
    let manifest_dir = env!("CARGO_MANIFEST_DIR").to_owned();
    let project = std::env::var("PILOT_COMPOSE_PROJECT")
        .unwrap_or_else(|_| format!("iggy-plc4x-integration-{}", std::process::id()));
    let stack = ComposeStack {
        project,
        manifest_dir,
    };
    stack.start().expect("Compose stack should start");

    let client = reqwest::Client::new();
    let endpoint = "http://127.0.0.1:18080/rest/v2/query";
    let superset_health = "http://127.0.0.1:8088/health";
    let deadline = tokio::time::Instant::now() + Duration::from_secs(8 * 60);
    let mut last_error = String::from("IoTDB has not returned a reading yet");

    while tokio::time::Instant::now() < deadline {
        let superset_ready = client
            .get(superset_health)
            .send()
            .await
            .is_ok_and(|response| response.status().is_success());
        let result = client
            .post(endpoint)
            .basic_auth("root", Some("root"))
            .json(&serde_json::json!({ "sql": "SELECT temperature FROM root.sg.line_1" }))
            .send()
            .await;
        match result {
            Ok(response) if response.status().is_success() => {
                let body = response.text().await.unwrap_or_default();
                let parsed = serde_json::from_str::<serde_json::Value>(&body).ok();
                let has_rows = parsed
                    .as_ref()
                    .and_then(|value| value.get("values"))
                    .and_then(serde_json::Value::as_array)
                    .is_some_and(|rows| !rows.is_empty());
                if has_rows && superset_ready {
                    return;
                }
                last_error = if has_rows {
                    "IoTDB contains readings, but Superset is not healthy yet".to_owned()
                } else {
                    format!("IoTDB query has no rows yet: {body}")
                };
            }
            Ok(response) => {
                last_error = format!("IoTDB query returned {}", response.status());
            }
            Err(error) => last_error = error.to_string(),
        }
        tokio::time::sleep(Duration::from_secs(5)).await;
    }

    panic!("pipeline did not write a reading before timeout: {last_error}");
}
