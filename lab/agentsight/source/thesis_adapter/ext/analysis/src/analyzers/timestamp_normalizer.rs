// SPDX-License-Identifier: MIT
// Copyright (c) 2026 eunomia-bpf org.

//! Timestamp Normalizer Analyzer
//!
//! Converts all timestamps from nanoseconds since boot to milliseconds since UNIX epoch.
//! This ensures timestamps are standardized for frontend consumption.

use super::Analyzer;
use crate::event::Event;
use crate::time::{boot_ns_to_epoch_ms, get_boot_time_ns, get_boot_time_uncertainty_ns};
use async_trait::async_trait;
use futures::stream::{Stream, StreamExt};
use std::pin::Pin;

type EventStream = Pin<Box<dyn Stream<Item = Event> + Send>>;

#[derive(Debug)]
pub struct TimestampNormalizer {}

impl TimestampNormalizer {
    pub fn new() -> Self {
        Self {}
    }
}

impl Default for TimestampNormalizer {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl Analyzer for TimestampNormalizer {
    async fn process(
        &mut self,
        stream: EventStream,
    ) -> Result<EventStream, Box<dyn std::error::Error + Send + Sync>> {
        let normalized_stream = stream.map(|mut event| {
            // Convert timestamp from nanoseconds since boot to milliseconds since UNIX epoch
            let raw_boot_ns = event.timestamp;
            let boot_epoch_ns = get_boot_time_ns();
            let timestamp_ms = boot_ns_to_epoch_ms(raw_boot_ns);
            if let Some(data) = event.data.as_object_mut() {
                data.insert(
                    "_agentsight_clock".to_string(),
                    serde_json::json!({
                        "raw_boot_ns": raw_boot_ns,
                        "boot_epoch_ns": boot_epoch_ns,
                        "epoch_ms": timestamp_ms,
                        "anchor_uncertainty_ns": get_boot_time_uncertainty_ns(),
                        "conversion": "boot_epoch_ns_plus_bpf_ktime_ns"
                    }),
                );
            }
            event.timestamp = timestamp_ms;
            event
        });

        Ok(Box::pin(normalized_stream))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use futures::stream;
    use serde_json::json;

    #[tokio::test]
    async fn test_timestamp_normalizer() {
        let mut normalizer = TimestampNormalizer::new();

        // Create test event with nanoseconds since boot (e.g., 1 second after boot)
        let test_event = Event::new_with_timestamp(
            1_000_000_000, // 1 second in nanoseconds
            "test".to_string(),
            1234,
            "test_comm".to_string(),
            json!({"test": "data"}),
        );

        let input_stream = stream::iter(vec![test_event]);
        let output_stream = normalizer.process(Box::pin(input_stream)).await.unwrap();

        let results: Vec<Event> = output_stream.collect().await;
        assert_eq!(results.len(), 1);

        // Timestamp should be converted to milliseconds since epoch
        // Should be much larger than 1 second (boot time + 1 second)
        assert!(results[0].timestamp > 1_000_000_000_000); // Should be > year 2001 in ms
        assert_eq!(
            results[0].data.pointer("/_agentsight_clock/raw_boot_ns"),
            Some(&json!(1_000_000_000u64))
        );
        assert_eq!(
            results[0].data.pointer("/_agentsight_clock/epoch_ms"),
            Some(&json!(results[0].timestamp))
        );
        assert!(
            results[0]
                .data
                .pointer("/_agentsight_clock/anchor_uncertainty_ns")
                .and_then(serde_json::Value::as_u64)
                .is_some_and(|value| value > 0),
            "normalized runtime evidence must carry a nonzero clock-resolution floor"
        );
    }

    #[tokio::test]
    async fn test_timestamp_normalizer_multiple_events() {
        let mut normalizer = TimestampNormalizer::new();

        let events = vec![
            Event::new_with_timestamp(
                1_000_000_000, // 1 second
                "test".to_string(),
                1234,
                "test1".to_string(),
                json!({"id": 1}),
            ),
            Event::new_with_timestamp(
                2_000_000_000, // 2 seconds
                "test".to_string(),
                1234,
                "test2".to_string(),
                json!({"id": 2}),
            ),
            Event::new_with_timestamp(
                3_000_000_000, // 3 seconds
                "test".to_string(),
                1234,
                "test3".to_string(),
                json!({"id": 3}),
            ),
        ];

        let input_stream = stream::iter(events);
        let output_stream = normalizer.process(Box::pin(input_stream)).await.unwrap();

        let results: Vec<Event> = output_stream.collect().await;
        assert_eq!(results.len(), 3);

        // Verify timestamps are in order and normalized
        assert!(results[0].timestamp < results[1].timestamp);
        assert!(results[1].timestamp < results[2].timestamp);

        // All should be in milliseconds since epoch (reasonable timestamp)
        for result in &results {
            assert!(result.timestamp > 1_000_000_000_000); // > year 2001
        }
    }
}
