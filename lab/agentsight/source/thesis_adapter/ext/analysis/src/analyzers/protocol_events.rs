// SPDX-License-Identifier: MIT
// Copyright (c) 2026 eunomia-bpf org.

use crate::event::Event;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

/// SSE Processor Event - represents a complete SSE interaction with timing information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SSEProcessorEvent {
    pub connection_id: String,
    pub message_id: Option<String>,
    pub start_time: u64,
    pub end_time: u64,
    pub duration_ns: u64,
    pub original_source: String,
    pub host: Option<String>,
    pub method: Option<String>,
    pub path: Option<String>,
    pub status_code: Option<u16>,
    pub function: String,
    pub tid: u64,
    pub json_content: String,
    pub text_content: String,
    pub total_size: usize,
    pub event_count: usize,
    pub has_message_start: bool,
    pub sse_events: Vec<Value>,
}

impl SSEProcessorEvent {
    pub fn to_event(&self, original_event: &Event) -> Event {
        // Serialize struct to JSON Value to ensure exact match with struct fields
        let mut data = serde_json::to_value(self).unwrap_or_else(|_| serde_json::json!({}));
        preserve_clock_evidence(&mut data, original_event);

        // Use merged end_time if events were merged, otherwise use original timestamp
        let timestamp = if self.event_count > 1 {
            self.end_time
        } else {
            original_event.timestamp
        };

        Event::new_with_timestamp(
            timestamp,
            "sse_processor".to_string(),
            original_event.pid,
            original_event.comm.clone(),
            data,
        )
    }
}

/// HTTP Event - represents a parsed HTTP request or response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HTTPEvent {
    pub tid: u64,
    pub message_type: String,
    pub first_line: String,
    pub method: Option<String>,
    pub path: Option<String>,
    pub protocol: Option<String>,
    pub status_code: Option<u16>,
    pub status_text: Option<String>,
    pub headers: HashMap<String, String>,
    pub body: Option<String>,
    pub body_hex: Option<String>,
    pub total_size: usize,
    pub has_body: bool,
    pub is_chunked: bool,
    pub content_length: Option<usize>,
    pub original_source: String,
    pub raw_data: Option<String>,
}

impl HTTPEvent {
    pub fn to_event(&self, original_event: &Event) -> Event {
        // Serialize struct to JSON Value to ensure exact match with struct fields
        let mut data = serde_json::to_value(self).unwrap_or_else(|_| serde_json::json!({}));
        preserve_clock_evidence(&mut data, original_event);

        Event::new_with_timestamp(
            original_event.timestamp, // Use original event timestamp directly
            "http_parser".to_string(),
            original_event.pid,
            original_event.comm.clone(),
            data,
        )
    }
}

fn preserve_clock_evidence(data: &mut Value, original_event: &Event) {
    let Some(clock) = original_event.data.get("_agentsight_clock") else {
        return;
    };
    if let Some(object) = data.as_object_mut() {
        object.insert("_agentsight_clock".to_string(), clock.clone());
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn sse_event_preserves_timestamp_normalizer_evidence() {
        let source = Event::new_with_timestamp(
            2_100,
            "ssl".to_string(),
            7,
            "claude".to_string(),
            json!({
                "_agentsight_clock": {
                    "raw_boot_ns": 600_000_000u64,
                    "boot_epoch_ns": 1_500_000_000u64,
                    "epoch_ms": 2_100u64,
                    "anchor_uncertainty_ns": 10u64,
                    "conversion": "boot_epoch_ns_plus_bpf_ktime_ns"
                }
            }),
        );
        let event = SSEProcessorEvent {
            connection_id: "connection".to_string(),
            message_id: None,
            start_time: 2_100,
            end_time: 2_100,
            duration_ns: 0,
            original_source: "ssl".to_string(),
            host: None,
            method: None,
            path: None,
            status_code: None,
            function: "READ/RECV".to_string(),
            tid: 8,
            json_content: "{}".to_string(),
            text_content: String::new(),
            total_size: 2,
            event_count: 1,
            has_message_start: false,
            sse_events: Vec::new(),
        }
        .to_event(&source);
        assert_eq!(
            event.data.pointer("/_agentsight_clock/raw_boot_ns"),
            Some(&json!(600_000_000u64))
        );
    }
}
