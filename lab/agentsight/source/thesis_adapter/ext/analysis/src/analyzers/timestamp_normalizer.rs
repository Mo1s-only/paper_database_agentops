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
        // The process BPF runner supplies a CLOCK_SYNC sample from the same
        // monotonic domain as its events. Prefer that fresh sample to the
        // process-wide cached boot epoch, which can drift after a WSL clock
        // adjustment. Other runners retain the existing fallback conversion.
        let mut process_clock_anchor: Option<(u64, u64)> = None;
        let normalized_stream = stream.map(move |mut event| {
            if event.source == "diagnostic"
                && event.data.get("event").and_then(|value| value.as_str()) == Some("CLOCK_SYNC")
                && let (Some(mono_ns), Some(wall_time_ns)) = (
                    event.data.get("mono_ns").and_then(|value| value.as_u64()),
                    event.data.get("wall_time_ns").and_then(|value| value.as_u64()),
                )
            {
                process_clock_anchor = Some((mono_ns, wall_time_ns));
            }
            // Convert timestamp from nanoseconds since boot to milliseconds since UNIX epoch
            let raw_boot_ns = event.timestamp;
            let (boot_epoch_ns, timestamp_ms, uncertainty_ns, conversion) =
                if let Some((mono_ns, wall_time_ns)) =
                    process_clock_anchor.filter(|_| event.source == "process" || event.source == "diagnostic") {
                    let epoch_ns = wall_time_ns.saturating_sub(mono_ns);
                    (epoch_ns, epoch_ns.saturating_add(raw_boot_ns) / 1_000_000,
                     get_boot_time_uncertainty_ns().max(1_000_000),
                     "clock_sync_epoch_ns_plus_bpf_ktime_ns")
                } else {
                    (get_boot_time_ns(), boot_ns_to_epoch_ms(raw_boot_ns),
                     get_boot_time_uncertainty_ns(), "boot_epoch_ns_plus_bpf_ktime_ns")
                };
            if let Some(data) = event.data.as_object_mut() {
                data.insert(
                    "_agentsight_clock".to_string(),
                    serde_json::json!({
                        "raw_boot_ns": raw_boot_ns,
                        "boot_epoch_ns": boot_epoch_ns,
                        "epoch_ms": timestamp_ms,
                        "anchor_uncertainty_ns": uncertainty_ns,
                        "conversion": conversion
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

    #[tokio::test]
    async fn process_clock_sync_reanchors_subsequent_kernel_events() {
        let mut normalizer = TimestampNormalizer::new();
        let sync = Event::new_with_timestamp(
            1_000_000_000,
            "diagnostic".to_string(),
            0,
            "process".to_string(),
            json!({
                "event": "CLOCK_SYNC",
                "mono_ns": 1_000_000_000u64,
                "wall_time_ns": 1_700_000_001_000_000_000u64
            }),
        );
        let exec = Event::new_with_timestamp(
            2_000_000_000,
            "process".to_string(),
            42,
            "claude".to_string(),
            json!({"event": "EXEC"}),
        );
        let ssl = Event::new_with_timestamp(
            2_000_000_000,
            "ssl".to_string(),
            42,
            "claude".to_string(),
            json!({"tid": 7}),
        );
        let output = normalizer
            .process(Box::pin(stream::iter(vec![sync, exec, ssl])))
            .await
            .unwrap();
        let events: Vec<Event> = output.collect().await;
        assert_eq!(events[0].timestamp, 1_700_000_001_000);
        assert_eq!(events[1].timestamp, 1_700_000_002_000);
        assert_eq!(
            events[1].data.pointer("/_agentsight_clock/conversion"),
            Some(&json!("clock_sync_epoch_ns_plus_bpf_ktime_ns"))
        );
        assert_eq!(
            events[2].data.pointer("/_agentsight_clock/conversion"),
            Some(&json!("boot_epoch_ns_plus_bpf_ktime_ns"))
        );
    }
}
