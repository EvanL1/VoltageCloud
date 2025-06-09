/// IoT PoC Lambda Processor in Rust
/// (Legacy) Processes Kinesis records and writes to TimeStream and S3

use anyhow::{Context, Result};
use aws_config::BehaviorVersion;
use aws_sdk_s3::types::ByteStream;
use aws_sdk_timestream::types::{Dimension, Record, MeasureValueType, TimeUnit};
use base64::prelude::*;
use chrono::{DateTime, Utc};
use lambda_runtime::{run, service_fn, Error, LambdaEvent};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::collections::HashMap;
use std::env;
use tracing::{info, error, warn};

#[derive(Debug, Deserialize)]
struct KinesisEvent {
    #[serde(rename = "Records")]
    records: Vec<KinesisRecord>,
}

#[derive(Debug, Deserialize)]
struct KinesisRecord {
    kinesis: KinesisData,
    #[serde(rename = "eventSourceARN")]
    event_source_arn: Option<String>,
}

#[derive(Debug, Deserialize)]
struct KinesisData {
    data: String,
}

#[derive(Debug, Serialize)]
struct ProcessingResult {
    #[serde(rename = "statusCode")]
    status_code: u16,
    successful_records: u32,
    failed_records: u32,
    timestream_records: usize,
    timestream_success: bool,
}

/// Custom error type for model service operations
#[derive(Debug, thiserror::Error)]
pub enum ModelSrvError {
    #[error("S3 operation failed: {0}")]
    S3Error(String),
    #[error("TimeStream operation failed: {0}")]
    TimeStreamError(String),
    #[error("Data processing error: {0}")]
    ProcessingError(String),
}

struct IotProcessor {
    s3_client: aws_sdk_s3::Client,
    timestream_client: aws_sdk_timestream::Client,
    database_name: String,
    table_name: String,
    bucket_name: String,
}

impl IotProcessor {
    /// Initialize IoT processor with AWS clients and configuration
    async fn new() -> Result<Self, ModelSrvError> {
        let config = aws_config::defaults(BehaviorVersion::latest())
            .load()
            .await;

        let s3_client = aws_sdk_s3::Client::new(&config);
        let timestream_client = aws_sdk_timestream::Client::new(&config);

        let database_name = env::var("TDB")
            .map_err(|_| ModelSrvError::ProcessingError("TDB environment variable not set".to_string()))?;
        let table_name = env::var("TBL")
            .map_err(|_| ModelSrvError::ProcessingError("TBL environment variable not set".to_string()))?;
        let bucket_name = env::var("BUCKET")
            .map_err(|_| ModelSrvError::ProcessingError("BUCKET environment variable not set".to_string()))?;

        Ok(Self {
            s3_client,
            timestream_client,
            database_name,
            table_name,
            bucket_name,
        })
    }

    /// Extract device ID from payload or generate fallback
    fn extract_device_id(&self, payload: &Map<String, Value>) -> String {
        if let Some(Value::String(source_topic)) = payload.get("source_topic") {
            let parts: Vec<&str> = source_topic.split('/').collect();
            if parts.len() >= 2 {
                return parts[1].to_string(); // devices/{device_id}/data
            }
        }
        
        format!("unknown_{}", chrono::Utc::now().timestamp())
    }

    /// Save raw message to S3 with date-based partitioning
    async fn save_to_s3(&self, device_id: &str, payload: &Map<String, Value>) -> Result<(), ModelSrvError> {
        let timestamp = payload
            .get("event_time")
            .or_else(|| payload.get("ts"))
            .and_then(|v| v.as_i64())
            .unwrap_or_else(|| chrono::Utc::now().timestamp_millis());

        let dt = if timestamp > 1_000_000_000_000 {
            DateTime::from_timestamp_millis(timestamp)
        } else {
            DateTime::from_timestamp(timestamp, 0)
        };

        let date_time = dt.unwrap_or_else(|| Utc::now());
        let s3_key = format!(
            "raw/{}/{}/{}.json",
            device_id,
            date_time.format("%Y/%m/%d"),
            timestamp
        );

        let body = serde_json::to_string(payload)
            .map_err(|e| ModelSrvError::ProcessingError(format!("JSON serialization failed: {}", e)))?;

        self.s3_client
            .put_object()
            .bucket(&self.bucket_name)
            .key(&s3_key)
            .body(ByteStream::from(body.into_bytes()))
            .content_type("application/json")
            .send()
            .await
            .map_err(|e| ModelSrvError::S3Error(format!("Failed to upload to S3: {}", e)))?;

        info!("Saved raw data to S3: {}", s3_key);
        Ok(())
    }

    /// Create TimeStream records from IoT payload
    fn create_timestream_records(&self, device_id: &str, payload: &Map<String, Value>) -> Vec<Record> {
        let mut records = Vec::new();
        
        let timestamp = payload
            .get("event_time")
            .or_else(|| payload.get("ts"))
            .and_then(|v| v.as_i64())
            .unwrap_or_else(|| chrono::Utc::now().timestamp_millis());

        let timestamp_str = timestamp.to_string();
        let excluded_fields = ["ts", "event_time", "source_topic"];

        for (key, value) in payload {
            if excluded_fields.contains(&key.as_str()) {
                continue;
            }

            if let Some(numeric_value) = value.as_f64() {
                let dimensions = vec![
                    Dimension::builder()
                        .name("deviceId")
                        .value(device_id)
                        .build()
                        .expect("Failed to build deviceId dimension"),
                    Dimension::builder()
                        .name("metric")
                        .value(key)
                        .build()
                        .expect("Failed to build metric dimension"),
                ];

                let record = Record::builder()
                    .dimensions(dimensions)
                    .measure_name("value")
                    .measure_value(numeric_value.to_string())
                    .measure_value_type(MeasureValueType::Double)
                    .time(timestamp_str.clone())
                    .time_unit(TimeUnit::Milliseconds)
                    .build()
                    .expect("Failed to build TimeStream record");

                records.push(record);
            }
        }

        records
    }

    /// Write records to TimeStream
    async fn write_to_timestream(&self, records: Vec<Record>) -> Result<(), ModelSrvError> {
        if records.is_empty() {
            info!("No records to write to TimeStream");
            return Ok(());
        }

        self.timestream_client
            .write_records()
            .database_name(&self.database_name)
            .table_name(&self.table_name)
            .set_records(Some(records.clone()))
            .send()
            .await
            .map_err(|e| ModelSrvError::TimeStreamError(format!("Failed to write to TimeStream: {}", e)))?;

        info!("Successfully wrote {} records to TimeStream", records.len());
        Ok(())
    }

    /// Process a single Kinesis record
    async fn process_record(&self, record: &KinesisRecord) -> Result<Vec<Record>, ModelSrvError> {
        // Decode base64 Kinesis data
        let decoded_data = BASE64_STANDARD
            .decode(&record.kinesis.data)
            .map_err(|e| ModelSrvError::ProcessingError(format!("Base64 decode failed: {}", e)))?;

        let payload_str = String::from_utf8(decoded_data)
            .map_err(|e| ModelSrvError::ProcessingError(format!("UTF-8 decode failed: {}", e)))?;

        let payload: Map<String, Value> = serde_json::from_str(&payload_str)
            .map_err(|e| ModelSrvError::ProcessingError(format!("JSON parse failed: {}", e)))?;

        info!("Processing payload: {:?}", payload);

        // Extract device ID
        let device_id = self.extract_device_id(&payload);

        // Save to S3
        self.save_to_s3(&device_id, &payload).await?;

        // Create TimeStream records
        let ts_records = self.create_timestream_records(&device_id, &payload);
        
        Ok(ts_records)
    }
}

/// Main Lambda handler function
async fn function_handler(event: LambdaEvent<KinesisEvent>) -> Result<ProcessingResult, Error> {
    let processor = IotProcessor::new().await
        .map_err(|e| Error::from(format!("Failed to initialize processor: {}", e)))?;

    info!("Processing {} Kinesis records", event.payload.records.len());

    let mut successful_records = 0u32;
    let mut failed_records = 0u32;
    let mut all_ts_records = Vec::new();

    for record in &event.payload.records {
        match processor.process_record(record).await {
            Ok(ts_records) => {
                all_ts_records.extend(ts_records);
                successful_records += 1;
            }
            Err(e) => {
                error!("Failed to process record: {}", e);
                failed_records += 1;
            }
        }
    }

    // Batch write to TimeStream
    let ts_success = match processor.write_to_timestream(all_ts_records.clone()).await {
        Ok(_) => true,
        Err(e) => {
            error!("TimeStream write failed: {}", e);
            false
        }
    };

    let result = ProcessingResult {
        status_code: 200,
        successful_records,
        failed_records,
        timestream_records: all_ts_records.len(),
        timestream_success: ts_success,
    };

    info!("Processing completed: {:?}", result);
    Ok(result)
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .with_target(false)
        .without_time()
        .init();

    run(service_fn(function_handler)).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_extract_device_id_with_topic() {
        let processor = IotProcessor {
            s3_client: todo!(),
            timestream_client: todo!(),
            database_name: "test".to_string(),
            table_name: "test".to_string(),
            bucket_name: "test".to_string(),
        };

        let mut payload = Map::new();
        payload.insert("source_topic".to_string(), json!("devices/sensor01/data"));
        payload.insert("temp".to_string(), json!(25.0));

        let device_id = processor.extract_device_id(&payload);
        assert_eq!(device_id, "sensor01");
    }

    #[test]
    fn test_extract_device_id_fallback() {
        let processor = IotProcessor {
            s3_client: todo!(),
            timestream_client: todo!(),
            database_name: "test".to_string(),
            table_name: "test".to_string(),
            bucket_name: "test".to_string(),
        };

        let mut payload = Map::new();
        payload.insert("temp".to_string(), json!(25.0));

        let device_id = processor.extract_device_id(&payload);
        assert!(device_id.starts_with("unknown_"));
    }

    #[test]
    fn test_create_timestream_records() {
        let processor = IotProcessor {
            s3_client: todo!(),
            timestream_client: todo!(),
            database_name: "test".to_string(),
            table_name: "test".to_string(),
            bucket_name: "test".to_string(),
        };

        let mut payload = Map::new();
        payload.insert("temp".to_string(), json!(25.5));
        payload.insert("humidity".to_string(), json!(60.0));
        payload.insert("ts".to_string(), json!(1717910400));
        payload.insert("source_topic".to_string(), json!("devices/test/data"));

        let records = processor.create_timestream_records("test_device", &payload);
        assert_eq!(records.len(), 2); // temp and humidity
    }
} 