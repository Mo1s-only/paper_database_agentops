// SPDX-License-Identifier: MIT
// Copyright (c) 2026 eunomia-bpf org.

use super::protocol_events::HTTPEvent;
use super::{Analyzer, AnalyzerError};
use crate::event::Event;
use crate::runners::EventStream;
use async_trait::async_trait;
use flate2::{Decompress, FlushDecompress};
use futures::{stream, stream::StreamExt};
use hpack::Decoder as HpackDecoder;
use std::collections::{HashMap, HashSet};
use std::hash::Hash;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;
use std::sync::Mutex;

const MAX_HTTP2_STREAMS: usize = 1024;
const MAX_HTTP2_PENDING_HEADERS: usize = 1024;
const MAX_HTTP2_PENDING_BYTES: usize = MAX_HTTP_BODY_BYTES + MAX_HTTP2_HEADER_BLOCK_BYTES;
const MAX_HTTP_BODY_BYTES: usize = 1024 * 1024;
const MAX_HTTP2_HEADER_BLOCK_BYTES: usize = 64 * 1024;

/// HTTP Parser Analyzer that parses SSL traffic into HTTP requests/responses
pub struct HTTPParser {
    /// Flag to include raw data in parsed events (default: true)
    include_raw_data: bool,
    http1: HTTP1State,
    http2: HTTP2State,
    websocket: WebSocketState,
}

#[derive(Default)]
struct HTTPParserDiagnostics {
    ssl_events: AtomicU64,
    ssl_read_events: AtomicU64,
    ssl_read_bytes: AtomicU64,
    ssl_write_events: AtomicU64,
    ssl_write_bytes: AtomicU64,
    unknown_direction_events: AtomicU64,
    http_responses: AtomicU64,
    http_response_body_bytes: AtomicU64,
    max_pending_http2_bytes: AtomicUsize,
    max_pending_http2_streams: AtomicUsize,
    max_pending_http2_header_blocks: AtomicUsize,
    current_pending_http2_bytes: AtomicUsize,
    current_pending_http2_buffers: AtomicUsize,
    http2_need_more: AtomicU64,
    http2_not_http2: AtomicU64,
    http2_invocations: AtomicU64,
    http1_pending_events: AtomicU64,
    unparsed_ssl_events: AtomicU64,
    max_pending_http1_bytes: AtomicUsize,
    current_pending_http1_bytes: AtomicUsize,
    current_pending_http1_buffers: AtomicUsize,
    pending_http1_request_buffers: AtomicUsize,
    pending_http1_response_buffers: AtomicUsize,
    pending_http1_header_wait_buffers: AtomicUsize,
    pending_http1_content_length_buffers: AtomicUsize,
    pending_http1_chunked_buffers: AtomicUsize,
    pending_http1_expected_body_bytes: AtomicUsize,
    pending_http1_chunked_wait_stage: AtomicUsize,
    pending_http1_chunked_completed_chunks: AtomicUsize,
    pending_http1_chunked_progress_offset: AtomicUsize,
    pending_http1_first_chunk_size: AtomicUsize,
    pending_http1_first_chunk_boundary_class: AtomicUsize,
    ssl_connection_id_missing_events: AtomicU64,
    ssl_connection_ids: Mutex<HashSet<u64>>,
    ssl_sequence_gaps: AtomicU64,
    ssl_sequence_reorders: AtomicU64,
    ssl_connection_sequences: Mutex<HashMap<u64, u64>>,
    truncated_ssl_events: AtomicU64,
    ssl_bytes_lost: AtomicU64,
    request_header_frames: AtomicU64,
    response_header_frames: AtomicU64,
    continuation_frames: AtomicU64,
    request_data_frames: AtomicU64,
    response_data_frames: AtomicU64,
    request_data_bytes: AtomicU64,
    response_data_bytes: AtomicU64,
    per_thread: Mutex<HashMap<(u32, u64), ThreadCaptureDiagnostics>>,
}

#[derive(Default)]
struct ThreadCaptureDiagnostics {
    read_events: u64,
    write_events: u64,
    http2_frames: u64,
    data_frames: u64,
    data_bytes: u64,
}

impl Drop for HTTPParserDiagnostics {
    fn drop(&mut self) {
        eprintln!(
            "[HTTPParser capture diagnostics] ssl_events={} ssl_read_events={} ssl_read_bytes={} ssl_write_events={} ssl_write_bytes={} unknown_direction_events={} truncated_ssl_events={} ssl_bytes_lost={} http_responses={} http_response_body_bytes={} http2_invocations={} http2_need_more={} http2_not_http2={} http1_pending_events={} unparsed_ssl_events={} max_pending_http1_bytes={} final_pending_http1_bytes={} final_pending_http1_buffers={} pending_http1_requests={} pending_http1_responses={} pending_http1_header_wait={} pending_http1_content_length={} pending_http1_chunked={} pending_http1_expected_body_bytes={} pending_http1_chunked_wait_stage={} pending_http1_chunked_completed_chunks={} pending_http1_chunked_progress_offset={} pending_http1_first_chunk_size={} pending_http1_first_chunk_boundary_class={} ssl_connection_id_missing_events={} distinct_ssl_connection_ids={} ssl_sequence_gaps={} ssl_sequence_reorders={} request_header_frames={} response_header_frames={} continuation_frames={} request_data_frames={} response_data_frames={} request_data_bytes={} response_data_bytes={} max_pending_http2_bytes={} max_pending_http2_streams={} max_pending_http2_header_blocks={} final_pending_http2_bytes={} final_pending_http2_buffers={} per_thread={:?}",
            self.ssl_events.load(Ordering::Relaxed),
            self.ssl_read_events.load(Ordering::Relaxed),
            self.ssl_read_bytes.load(Ordering::Relaxed),
            self.ssl_write_events.load(Ordering::Relaxed),
            self.ssl_write_bytes.load(Ordering::Relaxed),
            self.unknown_direction_events.load(Ordering::Relaxed),
            self.truncated_ssl_events.load(Ordering::Relaxed),
            self.ssl_bytes_lost.load(Ordering::Relaxed),
            self.http_responses.load(Ordering::Relaxed),
            self.http_response_body_bytes.load(Ordering::Relaxed),
            self.http2_invocations.load(Ordering::Relaxed),
            self.http2_need_more.load(Ordering::Relaxed),
            self.http2_not_http2.load(Ordering::Relaxed),
            self.http1_pending_events.load(Ordering::Relaxed),
            self.unparsed_ssl_events.load(Ordering::Relaxed),
            self.max_pending_http1_bytes.load(Ordering::Relaxed),
            self.current_pending_http1_bytes.load(Ordering::Relaxed),
            self.current_pending_http1_buffers.load(Ordering::Relaxed),
            self.pending_http1_request_buffers.load(Ordering::Relaxed),
            self.pending_http1_response_buffers.load(Ordering::Relaxed),
            self.pending_http1_header_wait_buffers.load(Ordering::Relaxed),
            self.pending_http1_content_length_buffers.load(Ordering::Relaxed),
            self.pending_http1_chunked_buffers.load(Ordering::Relaxed),
            self.pending_http1_expected_body_bytes.load(Ordering::Relaxed),
            self.pending_http1_chunked_wait_stage.load(Ordering::Relaxed),
            self.pending_http1_chunked_completed_chunks.load(Ordering::Relaxed),
            self.pending_http1_chunked_progress_offset.load(Ordering::Relaxed),
            self.pending_http1_first_chunk_size.load(Ordering::Relaxed),
            self.pending_http1_first_chunk_boundary_class.load(Ordering::Relaxed),
            self.ssl_connection_id_missing_events.load(Ordering::Relaxed),
            self.ssl_connection_ids.lock().map(|ids| ids.len()).unwrap_or_default(),
            self.ssl_sequence_gaps.load(Ordering::Relaxed),
            self.ssl_sequence_reorders.load(Ordering::Relaxed),
            self.request_header_frames.load(Ordering::Relaxed),
            self.response_header_frames.load(Ordering::Relaxed),
            self.continuation_frames.load(Ordering::Relaxed),
            self.request_data_frames.load(Ordering::Relaxed),
            self.response_data_frames.load(Ordering::Relaxed),
            self.request_data_bytes.load(Ordering::Relaxed),
            self.response_data_bytes.load(Ordering::Relaxed),
            self.max_pending_http2_bytes.load(Ordering::Relaxed),
            self.max_pending_http2_streams.load(Ordering::Relaxed),
            self.max_pending_http2_header_blocks.load(Ordering::Relaxed),
            self.current_pending_http2_bytes.load(Ordering::Relaxed),
            self.current_pending_http2_buffers.load(Ordering::Relaxed),
            self.per_thread.lock().map(|threads| threads.iter().map(|(key, v)| (*key, v.read_events, v.write_events, v.http2_frames, v.data_frames, v.data_bytes)).collect::<Vec<_>>()).unwrap_or_default(),
        );
    }
}

#[derive(Default)]
struct HTTP1State {
    pending: HashMap<(u32, u64, u64, HTTP2Direction), PendingHTTP1Message>,
}

struct PendingHTTP1Message {
    bytes: Vec<u8>,
    header_len: usize,
    framing: HTTP1BodyFraming,
}

#[derive(Clone, Copy)]
enum HTTP1BodyFraming {
    Headers,
    ContentLength(usize),
    Chunked,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum HTTP2Direction {
    Request,
    Response,
}

type HTTP2StreamKey = (u32, u64, u32);
type HTTP2ConnectionKey = (u32, u64, HTTP2Direction);

#[derive(Default)]
struct HTTP2StreamState {
    request_headers: HashMap<String, String>,
    response_headers: HashMap<String, String>,
    request_body: Vec<u8>,
    response_body: Vec<u8>,
    request_emitted: bool,
    response_emitted: bool,
}

struct PendingHTTP2Headers {
    direction: HTTP2Direction,
    block: Vec<u8>,
}

struct HTTP2Frame<'a> {
    frame_type: u8,
    flags: u8,
    stream_id: u32,
    payload: &'a [u8],
}

struct HTTP2State {
    request_decoder: HpackDecoder<'static>,
    response_decoder: HpackDecoder<'static>,
    streams: HashMap<HTTP2StreamKey, HTTP2StreamState>,
    pending_headers: HashMap<HTTP2StreamKey, PendingHTTP2Headers>,
    pending_bytes: HashMap<HTTP2ConnectionKey, Vec<u8>>,
}

#[derive(Default)]
struct WebSocketState {
    connections: HashMap<u32, WebSocketConnection>,
}

struct WebSocketConnection {
    path: String,
    headers: HashMap<String, String>,
    inflater: Decompress,
}

impl Default for HTTP2State {
    fn default() -> Self {
        Self {
            request_decoder: HpackDecoder::new(),
            response_decoder: HpackDecoder::new(),
            streams: HashMap::new(),
            pending_headers: HashMap::new(),
            pending_bytes: HashMap::new(),
        }
    }
}

#[derive(Clone, PartialEq, Debug)]
pub enum HTTPMessageType {
    Request,
    Response,
}

/// Parsed HTTP message
#[derive(Clone, Debug)]
pub struct HTTPMessage {
    pub message_type: HTTPMessageType,
    pub first_line: String,
    pub headers: HashMap<String, String>,
    pub body: Option<String>,
    pub body_bytes: Option<Vec<u8>>,
    pub raw_data: String,
    // Request-specific fields
    pub method: Option<String>,
    pub path: Option<String>,
    pub protocol: Option<String>,
    // Response-specific fields
    pub status_code: Option<u16>,
    pub status_text: Option<String>,
}

impl Default for HTTPParser {
    fn default() -> Self {
        Self::new()
    }
}

impl HTTPParser {
    /// Create a new HTTPParser with default settings (raw data included)
    pub fn new() -> Self {
        HTTPParser {
            include_raw_data: true,
            http1: HTTP1State::default(),
            http2: HTTP2State::default(),
            websocket: WebSocketState::default(),
        }
    }

    /// Disable raw data inclusion
    pub fn disable_raw_data(mut self) -> Self {
        self.include_raw_data = false;
        self
    }

    /// Check if SSL data contains HTTP protocol data
    pub fn is_http_data(data: &str) -> bool {
        // Look for HTTP patterns
        let has_http_request = data.contains("HTTP/1.")
            && (data.contains("GET ")
                || data.contains("POST ")
                || data.contains("PUT ")
                || data.contains("DELETE ")
                || data.contains("HEAD ")
                || data.contains("OPTIONS ")
                || data.contains("PATCH "));

        let has_http_response = data.starts_with("HTTP/1.") || data.contains("\r\nHTTP/1.");

        // Look for common HTTP headers
        let has_http_headers = data.contains("Content-Type:")
            || data.contains("content-type:")
            || data.contains("Host:")
            || data.contains("host:")
            || data.contains("User-Agent:")
            || data.contains("user-agent:");

        has_http_request || has_http_response || has_http_headers
    }

    /// Parse HTTP message from accumulated data
    pub fn parse_http_message(data: &str) -> Option<HTTPMessage> {
        Self::parse_http_message_bytes(data.as_bytes())
    }

    fn parse_http_message_bytes(data: &[u8]) -> Option<HTTPMessage> {
        let header_end = data.windows(4).position(|window| window == b"\r\n\r\n")?;
        let header_text = String::from_utf8_lossy(&data[..header_end]);
        let lines: Vec<&str> = header_text.split("\r\n").collect();

        if lines.is_empty() {
            return None;
        }

        let first_line = lines[0];
        let mut headers = HashMap::new();
        let mut message_type = HTTPMessageType::Request;
        let mut method = None;
        let mut path = None;
        let mut protocol = None;
        let mut status_code = None;
        let mut status_text = None;

        // Parse first line to determine message type
        if first_line.starts_with("HTTP/") {
            // Response
            message_type = HTTPMessageType::Response;
            let parts: Vec<&str> = first_line.splitn(3, ' ').collect();
            if parts.len() >= 2 {
                if let Ok(code) = parts[1].parse::<u16>() {
                    status_code = Some(code);
                }
                if parts.len() >= 3 {
                    status_text = Some(parts[2].to_string());
                }
                protocol = Some(parts[0].to_string());
            }
        } else {
            // Request
            let parts: Vec<&str> = first_line.splitn(3, ' ').collect();
            if parts.len() < 3
                || !matches!(
                    parts[0],
                    "GET" | "POST" | "PUT" | "DELETE" | "HEAD" | "OPTIONS" | "PATCH"
                )
                || !parts[2].starts_with("HTTP/")
            {
                return None;
            }
            method = Some(parts[0].to_string());
            path = Some(parts[1].to_string());
            protocol = Some(parts[2].to_string());
        }

        // Parse headers
        for line in lines.iter().skip(1) {
            if let Some(colon_pos) = line.find(':') {
                let key = line[..colon_pos].trim().to_lowercase();
                let value = line[colon_pos + 1..].trim().to_string();
                headers.insert(key, value);
            }
        }

        // Keep the entity bytes separately: a UTF-8 lossy conversion is fine
        // for displaying SSE text, but it corrupts compressed/binary bodies
        // before `body_hex` can preserve them for decompression.
        let body_bytes = data.get(header_end + 4..).filter(|body| !body.is_empty()).map(<[u8]>::to_vec);
        let body = body_bytes
            .as_deref()
            .map(|body| String::from_utf8_lossy(body).into_owned());

        Some(HTTPMessage {
            message_type,
            first_line: first_line.to_string(),
            headers,
            body,
            body_bytes,
            raw_data: String::from_utf8_lossy(data).into_owned(),
            method,
            path,
            protocol,
            status_code,
            status_text,
        })
    }

    /// Create HTTP event from parsed message
    fn create_http_event(
        tid: u64,
        parsed_message: HTTPMessage,
        original_event: &Event,
        include_raw_data: bool,
    ) -> Event {
        let message_type_str = match parsed_message.message_type {
            HTTPMessageType::Request => "request",
            HTTPMessageType::Response => "response",
        };

        // Determine content properties
        let content_length = parsed_message
            .headers
            .get("content-length")
            .and_then(|v| v.parse::<usize>().ok());
        let is_chunked = parsed_message
            .headers
            .get("transfer-encoding")
            .map(|v| v.to_lowercase().contains("chunked"))
            .unwrap_or(false);
        let has_body = parsed_message.body.is_some();
        let body_hex = parsed_message.body_bytes.as_deref().map(hex::encode);

        // Calculate total size from parsed components
        let total_size = parsed_message.first_line.len() +
            parsed_message.headers.iter().map(|(k, v)| k.len() + v.len() + 4).sum::<usize>() + // +4 for ": \r\n"
            parsed_message.body_bytes.as_ref().map(|b| b.len()).unwrap_or(0) +
            4; // +4 for \r\n\r\n separator

        HTTPEvent {
            tid,
            message_type: message_type_str.to_string(),
            first_line: parsed_message.first_line,
            method: parsed_message.method,
            path: parsed_message.path,
            protocol: parsed_message.protocol,
            status_code: parsed_message.status_code,
            status_text: parsed_message.status_text,
            headers: parsed_message.headers,
            body: parsed_message.body,
            body_hex,
            total_size,
            has_body,
            is_chunked,
            content_length,
            original_source: "ssl".to_string(),
            raw_data: include_raw_data.then_some(parsed_message.raw_data),
        }
        .to_event(original_event)
    }

    /// Handle SSL events (HTTP request/response data)
    fn handle_ssl_event(
        http1: &mut HTTP1State,
        http2: &mut HTTP2State,
        websocket: &mut WebSocketState,
        event: Event,
        include_raw_data: bool,
        diagnostics: &HTTPParserDiagnostics,
    ) -> Vec<Event> {
        let ssl_data = &event.data;

        let data_str = match ssl_data.get("data").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => return vec![event],
        };

        let data_bytes = ssl_data
            .get("data_hex")
            .and_then(|v| v.as_str())
            .and_then(|v| hex::decode(v).ok())
            .unwrap_or_else(|| ssl_json_string_to_bytes(data_str));

        if let Some(parsed_message) = http1.handle_fragment(&event, &data_bytes) {
            websocket.observe_handshake(&event, &parsed_message);
            let tid = ssl_data.get("tid").and_then(|v| v.as_u64()).unwrap_or(0);
            return vec![Self::create_http_event(
                tid,
                parsed_message,
                &event,
                include_raw_data,
            )];
        }
        if http1.is_buffering(&event) {
            return Vec::new();
        }

        // Only process if it's HTTP data AND can be parsed as a complete HTTP message
        if Self::is_http_data(data_str)
            && let Some(parsed_message) = Self::parse_http_message(data_str)
        {
            websocket.observe_handshake(&event, &parsed_message);
            let tid = ssl_data.get("tid").and_then(|v| v.as_u64()).unwrap_or(0);
            return vec![Self::create_http_event(
                tid,
                parsed_message,
                &event,
                include_raw_data,
            )];
        }

        if let Some(events) = websocket.handle_event(&event, &data_bytes, include_raw_data) {
            return events;
        }
        if let Some(events) = http2.handle_event(&event, &data_bytes, include_raw_data, diagnostics) {
            return events;
        }

        // If not parseable as HTTP, pass through original event
        vec![event]
    }
}

impl HTTP1State {
    fn key(event: &Event) -> Option<(u32, u64, u64, HTTP2Direction)> {
        let tid = event.data.get("tid").and_then(|v| v.as_u64())?;
        let connection_id = event
            .data
            .get("connection_id")
            .and_then(|value| value.as_u64())
            .unwrap_or(0);
        let direction = direction_from_function(
            event
                .data
                .get("function")
                .and_then(|v| v.as_str())
                .unwrap_or(""),
        )?;
        Some((event.pid, tid, connection_id, direction))
    }

    fn handle_fragment(&mut self, event: &Event, bytes: &[u8]) -> Option<HTTPMessage> {
        let key = Self::key(event)?;
        if let Some(pending) = self.pending.get_mut(&key) {
            if pending.bytes.len().saturating_add(bytes.len()) > MAX_HTTP_BODY_BYTES {
                self.pending.remove(&key);
                return None;
            }
            pending.bytes.extend_from_slice(bytes);
            if matches!(pending.framing, HTTP1BodyFraming::Headers) {
                let Some((header_len, framing)) = http1_message_framing(&pending.bytes) else {
                    if pending.bytes.windows(4).any(|window| window == b"\r\n\r\n") {
                        let pending = self.pending.remove(&key)?;
                        return HTTPParser::parse_http_message_bytes(&pending.bytes);
                    }
                    return None;
                };
                pending.header_len = header_len;
                pending.framing = framing;
            }
            let complete = match pending.framing {
                HTTP1BodyFraming::Headers => false,
                HTTP1BodyFraming::ContentLength(body_len) => pending
                    .header_len
                    .checked_add(body_len)
                    .is_some_and(|message_len| pending.bytes.len() >= message_len),
                HTTP1BodyFraming::Chunked => {
                    decode_http1_chunked_body(&pending.bytes, pending.header_len).is_some()
                }
            };
            if !complete {
                return None;
            }
            let pending = self.pending.remove(&key)?;
            return parse_pending_http1_message(pending);
        }

        let Some((header_len, framing)) = http1_message_framing(bytes) else {
            let direction = direction_from_function(
                event.data.get("function").and_then(|value| value.as_str()).unwrap_or(""),
            )?;
            if !bytes.windows(4).any(|window| window == b"\r\n\r\n")
                && starts_like_http1(bytes, direction)
            {
                self.pending.insert(key, PendingHTTP1Message {
                    bytes: bytes.to_vec(),
                    header_len: 0,
                    framing: HTTP1BodyFraming::Headers,
                });
                evict_over_capacity(&mut self.pending, MAX_HTTP2_STREAMS);
            }
            return None;
        };
        match framing {
            HTTP1BodyFraming::Headers => return None,
            HTTP1BodyFraming::ContentLength(expected_len) => {
                let message_len = header_len.checked_add(expected_len)?;
                if bytes.len() >= message_len || message_len > MAX_HTTP_BODY_BYTES {
                    return None;
                }
            }
            HTTP1BodyFraming::Chunked => {
                if let Some((decoded, end)) = decode_http1_chunked_body(bytes, header_len) {
                    return parse_http1_chunked_message(bytes, &decoded, end, header_len);
                }
            }
        }
        self.pending.insert(key, PendingHTTP1Message {
            bytes: bytes.to_vec(),
            header_len,
            framing,
        });
        evict_over_capacity(&mut self.pending, MAX_HTTP2_STREAMS);
        None
    }

    fn is_buffering(&self, event: &Event) -> bool {
        Self::key(event).is_some_and(|key| self.pending.contains_key(&key))
    }
}

fn http1_message_framing(bytes: &[u8]) -> Option<(usize, HTTP1BodyFraming)> {
    let header_end = bytes.windows(4).position(|window| window == b"\r\n\r\n")?;
    let headers = String::from_utf8_lossy(&bytes[..header_end]);
    let first_line = headers.lines().next()?;
    let is_http1 = first_line.starts_with("HTTP/1.")
        || ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"]
            .iter()
            .any(|method| first_line.starts_with(&format!("{method} ")));
    if !is_http1 {
        return None;
    }
    let mut content_length = None;
    let mut is_chunked = false;
    for line in headers.lines().skip(1) {
        let (name, value) = line.split_once(':')?;
        if name.trim().eq_ignore_ascii_case("content-length") {
            content_length = value.trim().parse::<usize>().ok();
        } else if name.trim().eq_ignore_ascii_case("transfer-encoding")
            && value.to_ascii_lowercase().contains("chunked")
        {
            is_chunked = true;
        }
    }
    let header_len = header_end.checked_add(4)?;
    if is_chunked {
        Some((header_len, HTTP1BodyFraming::Chunked))
    } else {
        Some((header_len, HTTP1BodyFraming::ContentLength(content_length?)))
    }
}

fn parse_pending_http1_message(pending: PendingHTTP1Message) -> Option<HTTPMessage> {
    match pending.framing {
        HTTP1BodyFraming::ContentLength(body_len) => {
            let message_len = pending.header_len.checked_add(body_len)?;
            if pending.bytes.len() < message_len {
                return None;
            }
            HTTPParser::parse_http_message_bytes(&pending.bytes[..message_len])
        }
        HTTP1BodyFraming::Chunked => {
            let (decoded, end) = decode_http1_chunked_body(&pending.bytes, pending.header_len)?;
            parse_http1_chunked_message(&pending.bytes, &decoded, end, pending.header_len)
        }
        HTTP1BodyFraming::Headers => None,
    }
}

fn starts_like_http1(bytes: &[u8], direction: HTTP2Direction) -> bool {
    let prefixes: &[&[u8]] = match direction {
        HTTP2Direction::Request => &[
            b"GET ", b"POST ", b"PUT ", b"DELETE ", b"HEAD ", b"OPTIONS ", b"PATCH ",
        ],
        HTTP2Direction::Response => &[b"HTTP/1."],
    };
    prefixes.iter().any(|prefix| prefix.starts_with(bytes) || bytes.starts_with(prefix))
}

fn parse_http1_chunked_message(
    raw: &[u8],
    decoded_body: &[u8],
    raw_end: usize,
    header_len: usize,
) -> Option<HTTPMessage> {
    let mut normalized = raw.get(..header_len)?.to_vec();
    normalized.extend_from_slice(decoded_body);
    let raw_text = String::from_utf8_lossy(raw.get(..raw_end)?).into_owned();
    let mut message = HTTPParser::parse_http_message_bytes(&normalized)?;
    message.raw_data = raw_text;
    Some(message)
}

fn decode_http1_chunked_body(bytes: &[u8], mut cursor: usize) -> Option<(Vec<u8>, usize)> {
    let mut decoded = Vec::new();
    loop {
        let line_end = bytes.get(cursor..)?.windows(2).position(|pair| pair == b"\r\n")? + cursor;
        let line = std::str::from_utf8(bytes.get(cursor..line_end)?).ok()?;
        let size = usize::from_str_radix(line.split(';').next()?.trim(), 16).ok()?;
        cursor = line_end.checked_add(2)?;
        if size == 0 {
            if bytes.get(cursor..cursor.saturating_add(2)) == Some(b"\r\n") {
                return Some((decoded, cursor + 2));
            }
            if bytes.get(cursor) == Some(&b'\n') {
                return Some((decoded, cursor + 1));
            }
            if let Some(relative_end) = bytes
                .get(cursor..)?
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
            {
                let trailer_end = relative_end + cursor;
                return Some((decoded, trailer_end + 4));
            }
            let trailer_end = bytes.get(cursor..)?.windows(2).position(|window| window == b"\n\n")? + cursor;
            return Some((decoded, trailer_end + 2));
        }
        if decoded.len().checked_add(size)? > MAX_HTTP_BODY_BYTES {
            return None;
        }
        let data_end = cursor.checked_add(size)?;
        decoded.extend_from_slice(bytes.get(cursor..data_end)?);
        cursor = data_end.checked_add(http1_chunk_delimiter_len(bytes, data_end)?)?;
    }
}

fn http1_chunk_delimiter_len(bytes: &[u8], offset: usize) -> Option<usize> {
    if bytes.get(offset..offset.checked_add(2)?)? == b"\r\n" {
        Some(2)
    } else if bytes.get(offset) == Some(&b'\n') {
        Some(1)
    } else {
        None
    }
}

// Diagnostic codes are intentionally content-free: 0=complete, 1=waiting for
// a chunk-size line, 2=invalid UTF-8 size line, 3=invalid hex size, 4=waiting
// for payload, 5=waiting for payload CRLF, 6=invalid payload CRLF,
// 7=waiting for terminating chunk/trailers, 8=arithmetic overflow.
fn http1_chunked_wait_stage(bytes: &[u8], mut cursor: usize) -> usize {
    loop {
        let Some(relative_end) = bytes.get(cursor..).and_then(|tail| {
            tail.windows(2).position(|pair| pair == b"\r\n")
        }) else {
            return 1;
        };
        let line_end = cursor + relative_end;
        let Ok(line) = std::str::from_utf8(&bytes[cursor..line_end]) else {
            return 2;
        };
        let Some(size_text) = line.split(';').next() else {
            return 3;
        };
        let Ok(size) = usize::from_str_radix(size_text.trim(), 16) else {
            return 3;
        };
        cursor = line_end + 2;
        if size == 0 {
            if bytes.get(cursor..cursor.saturating_add(2)) == Some(b"\r\n")
                || bytes.get(cursor) == Some(&b'\n')
                || bytes.get(cursor..).is_some_and(|tail| tail.windows(4).any(|w| w == b"\r\n\r\n"))
                || bytes.get(cursor..).is_some_and(|tail| tail.windows(2).any(|w| w == b"\n\n"))
            {
                return 0;
            }
            return 7;
        }
        let Some(data_end) = cursor.checked_add(size) else {
            return 8;
        };
        if bytes.len() < data_end {
            return 2;
        }
        let Some(delimiter_len) = http1_chunk_delimiter_len(bytes, data_end) else {
            if bytes.len() == data_end || bytes.get(data_end) == Some(&b'\r') && bytes.len() == data_end + 1 {
                return 5;
            }
            return 6;
        };
        cursor = data_end + delimiter_len;
    }
}

fn http1_chunked_progress(bytes: &[u8], mut cursor: usize) -> (usize, usize) {
    let mut completed_chunks = 0;
    loop {
        let Some(relative_end) = bytes.get(cursor..).and_then(|tail| {
            tail.windows(2).position(|pair| pair == b"\r\n")
        }) else {
            return (completed_chunks, cursor);
        };
        let line_end = cursor + relative_end;
        let Ok(line) = std::str::from_utf8(&bytes[cursor..line_end]) else {
            return (completed_chunks, cursor);
        };
        let Ok(size) = usize::from_str_radix(line.split(';').next().unwrap_or("").trim(), 16) else {
            return (completed_chunks, cursor);
        };
        cursor = line_end + 2;
        if size == 0 {
            return (completed_chunks, cursor);
        }
        let Some(data_end) = cursor.checked_add(size) else {
            return (completed_chunks, cursor);
        };
        let Some(delimiter_len) = http1_chunk_delimiter_len(bytes, data_end) else {
            return (completed_chunks, data_end);
        };
        cursor = data_end + delimiter_len;
        completed_chunks += 1;
    }
}

fn http1_first_chunk_metadata(bytes: &[u8], header_len: usize) -> (usize, usize) {
    let Some(relative_end) = bytes.get(header_len..).and_then(|tail| {
        tail.windows(2).position(|pair| pair == b"\r\n")
    }) else {
        return (0, 0);
    };
    let line_end = header_len + relative_end;
    let Ok(line) = std::str::from_utf8(&bytes[header_len..line_end]) else {
        return (0, 0);
    };
    let Ok(size) = usize::from_str_radix(line.split(';').next().unwrap_or("").trim(), 16) else {
        return (0, 0);
    };
    let payload_start = line_end + 2;
    let Some(boundary_start) = payload_start.checked_add(size) else {
        return (size, 0);
    };
    let class = |byte: Option<&u8>| match byte.copied() {
        Some(b'\r') => 1,
        Some(b'\n') => 2,
        Some(b' ' | b'\t') => 3,
        Some(0x20..=0x7e) => 4,
        Some(_) => 5,
        None => 0,
    };
    let first = class(bytes.get(boundary_start));
    let second = class(boundary_start.checked_add(1).and_then(|index| bytes.get(index)));
    (size, first * 10 + second)
}

impl WebSocketState {
    fn observe_handshake(&mut self, event: &Event, message: &HTTPMessage) {
        if message.message_type != HTTPMessageType::Request
            || !message
                .headers
                .get("upgrade")
                .is_some_and(|v| v.eq_ignore_ascii_case("websocket"))
        {
            return;
        }
        let Some(path) = message.path.as_ref() else {
            return;
        };
        if !path.contains("/v1/responses") && !path.contains("/codex/responses") {
            return;
        }
        self.connections.insert(
            event.pid,
            WebSocketConnection {
                path: path.clone(),
                headers: message.headers.clone(),
                inflater: Decompress::new(false),
            },
        );
    }

    fn handle_event(
        &mut self,
        event: &Event,
        bytes: &[u8],
        include_raw_data: bool,
    ) -> Option<Vec<Event>> {
        let connection = self.connections.get_mut(&event.pid)?;
        let (compressed, mut payload) = parse_masked_websocket_frame(bytes)?;
        if compressed {
            payload.extend_from_slice(&[0, 0, 0xff, 0xff]);
            let mut decoded = Vec::with_capacity(MAX_HTTP_BODY_BYTES);
            let input_before = connection.inflater.total_in();
            connection
                .inflater
                .decompress_vec(&payload, &mut decoded, FlushDecompress::Sync)
                .ok()?;
            if connection.inflater.total_in() - input_before != payload.len() as u64 {
                return None;
            }
            payload = decoded;
        }
        let body = String::from_utf8(payload).ok()?;
        let json: serde_json::Value = serde_json::from_str(&body).ok()?;
        if json.get("type").and_then(|v| v.as_str()) != Some("response.create") {
            return None;
        }
        Some(vec![create_websocket_request_event(
            event,
            &connection.path,
            &connection.headers,
            body,
            include_raw_data,
        )])
    }
}

fn parse_masked_websocket_frame(bytes: &[u8]) -> Option<(bool, Vec<u8>)> {
    if bytes.len() < 2
        || bytes[0] & 0x80 == 0
        || bytes[0] & 0x30 != 0
        || !matches!(bytes[0] & 0x0f, 1 | 2)
        || bytes[1] & 0x80 == 0
    {
        return None;
    }
    let mut offset = 2;
    let mut payload_len = (bytes[1] & 0x7f) as usize;
    if payload_len == 126 {
        payload_len = usize::from(u16::from_be_bytes(
            bytes.get(offset..offset + 2)?.try_into().ok()?,
        ));
        offset += 2;
    } else if payload_len == 127 {
        payload_len = usize::try_from(u64::from_be_bytes(
            bytes.get(offset..offset + 8)?.try_into().ok()?,
        ))
        .ok()?;
        offset += 8;
    }
    let mask: [u8; 4] = bytes.get(offset..offset + 4)?.try_into().ok()?;
    offset += 4;
    let payload = bytes.get(offset..offset.checked_add(payload_len)?)?;
    if offset + payload_len != bytes.len() {
        return None;
    }
    Some((
        bytes[0] & 0x40 != 0,
        payload
            .iter()
            .enumerate()
            .map(|(i, byte)| byte ^ mask[i % 4])
            .collect(),
    ))
}

fn create_websocket_request_event(
    original_event: &Event,
    path: &str,
    headers: &HashMap<String, String>,
    body: String,
    include_raw_data: bool,
) -> Event {
    let tid = original_event
        .data
        .get("tid")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    HTTPEvent {
        tid,
        message_type: "request".to_string(),
        first_line: format!("POST {path} WebSocket"),
        method: Some("POST".to_string()),
        path: Some(path.to_string()),
        protocol: Some("WebSocket".to_string()),
        status_code: None,
        status_text: None,
        headers: headers.clone(),
        content_length: Some(body.len()),
        has_body: true,
        is_chunked: false,
        body_hex: Some(hex::encode(body.as_bytes())),
        total_size: headers_size(headers) + body.len(),
        original_source: "ssl.websocket".to_string(),
        raw_data: include_raw_data.then(|| body.clone()),
        body: Some(body),
    }
    .to_event(original_event)
}

impl HTTP2State {
    fn handle_event(
        &mut self,
        original_event: &Event,
        bytes: &[u8],
        include_raw_data: bool,
        diagnostics: &HTTPParserDiagnostics,
    ) -> Option<Vec<Event>> {
        diagnostics.http2_invocations.fetch_add(1, Ordering::Relaxed);
        let tid = original_event
            .data
            .get("tid")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let direction = direction_from_function(
            original_event
                .data
                .get("function")
                .and_then(|v| v.as_str())
                .unwrap_or(""),
        )?;
        let connection_key = (original_event.pid, tid, direction);
        let mut buffered = self
            .pending_bytes
            .remove(&connection_key)
            .unwrap_or_default();
        let had_buffered_bytes = !buffered.is_empty();
        buffered.extend_from_slice(bytes);
        if buffered.len() > MAX_HTTP2_PENDING_BYTES {
            return had_buffered_bytes
                .then(|| vec![ssl_event_with_bytes(original_event, &buffered)]);
        }
        let (frames, consumed) = match parse_http2_frames_prefix(&buffered, direction) {
            HTTP2ParseResult::NotHttp2 => {
                diagnostics.http2_not_http2.fetch_add(1, Ordering::Relaxed);
                return had_buffered_bytes
                    .then(|| vec![ssl_event_with_bytes(original_event, &buffered)]);
            }
            HTTP2ParseResult::NeedMore => {
                diagnostics.http2_need_more.fetch_add(1, Ordering::Relaxed);
                self.pending_bytes.insert(connection_key, buffered);
                evict_over_capacity(&mut self.pending_bytes, MAX_HTTP2_STREAMS);
                return Some(Vec::new());
            }
            HTTP2ParseResult::Parsed { frames, consumed } => (frames, consumed),
        };
        let mut events = Vec::new();

        for frame in frames {
            if let Ok(mut per_thread) = diagnostics.per_thread.lock() {
                let stats = per_thread.entry((original_event.pid, tid)).or_default();
                stats.http2_frames += 1;
                if frame.frame_type == 0x0 {
                    stats.data_frames += 1;
                    stats.data_bytes += data_payload(frame.flags, frame.payload).len() as u64;
                }
            }
            match (direction, frame.frame_type) {
                (HTTP2Direction::Request, 0x1) => {
                    diagnostics.request_header_frames.fetch_add(1, Ordering::Relaxed);
                }
                (HTTP2Direction::Response, 0x1) => {
                    diagnostics.response_header_frames.fetch_add(1, Ordering::Relaxed);
                }
                (_, 0x9) => {
                    diagnostics.continuation_frames.fetch_add(1, Ordering::Relaxed);
                }
                (HTTP2Direction::Request, 0x0) => {
                    diagnostics.request_data_frames.fetch_add(1, Ordering::Relaxed);
                    diagnostics.request_data_bytes.fetch_add(
                        data_payload(frame.flags, frame.payload).len() as u64,
                        Ordering::Relaxed,
                    );
                }
                (HTTP2Direction::Response, 0x0) => {
                    diagnostics.response_data_frames.fetch_add(1, Ordering::Relaxed);
                    diagnostics.response_data_bytes.fetch_add(
                        data_payload(frame.flags, frame.payload).len() as u64,
                        Ordering::Relaxed,
                    );
                }
                _ => {}
            }
            let key = (original_event.pid, tid, frame.stream_id);
            match frame.frame_type {
                0x0 => {
                    if frame.stream_id == 0 {
                        continue;
                    }
                    let payload = data_payload(frame.flags, frame.payload);
                    let state = self.streams.entry(key).or_default();
                    match direction {
                        HTTP2Direction::Request => {
                            extend_capped(&mut state.request_body, payload, MAX_HTTP_BODY_BYTES);
                            if frame.flags & 0x1 != 0 && !state.request_emitted {
                                events.push(create_http2_request_event(
                                    tid,
                                    frame.stream_id,
                                    state,
                                    original_event,
                                    include_raw_data,
                                ));
                                state.request_emitted = true;
                            }
                        }
                        HTTP2Direction::Response => {
                            extend_capped(&mut state.response_body, payload, MAX_HTTP_BODY_BYTES);
                            if (frame.flags & 0x1 != 0
                                || looks_like_complete_json(&state.response_body))
                                && !state.response_emitted
                            {
                                events.push(create_http2_response_event(
                                    tid,
                                    frame.stream_id,
                                    state,
                                    original_event,
                                    include_raw_data,
                                ));
                                state.response_emitted = true;
                            }
                        }
                    }
                }
                0x1 => {
                    if frame.stream_id == 0 {
                        continue;
                    }
                    let fragment = headers_payload(frame.flags, frame.payload);
                    if frame.flags & 0x4 != 0 {
                        if let Some(headers) = self.decode_headers(direction, fragment) {
                            let state = self.streams.entry(key).or_default();
                            apply_headers(state, direction, headers);
                            if frame.flags & 0x1 != 0 {
                                match direction {
                                    HTTP2Direction::Request if !state.request_emitted => {
                                        events.push(create_http2_request_event(
                                            tid,
                                            frame.stream_id,
                                            state,
                                            original_event,
                                            include_raw_data,
                                        ));
                                        state.request_emitted = true;
                                    }
                                    HTTP2Direction::Response if !state.response_emitted => {
                                        events.push(create_http2_response_event(
                                            tid,
                                            frame.stream_id,
                                            state,
                                            original_event,
                                            include_raw_data,
                                        ));
                                        state.response_emitted = true;
                                    }
                                    _ => {}
                                }
                            }
                        }
                    } else if fragment.len() <= MAX_HTTP2_HEADER_BLOCK_BYTES {
                        self.pending_headers.insert(
                            key,
                            PendingHTTP2Headers {
                                direction,
                                block: fragment.to_vec(),
                            },
                        );
                        evict_over_capacity(&mut self.pending_headers, MAX_HTTP2_PENDING_HEADERS);
                    }
                }
                0x9 => {
                    if frame.stream_id == 0 {
                        continue;
                    }
                    let Some(mut pending) = self.pending_headers.remove(&key) else {
                        continue;
                    };
                    pending.block.extend_from_slice(frame.payload);
                    if pending.block.len() > MAX_HTTP2_HEADER_BLOCK_BYTES {
                        continue;
                    }
                    if frame.flags & 0x4 != 0 {
                        if let Some(headers) =
                            self.decode_headers(pending.direction, &pending.block)
                        {
                            let state = self.streams.entry(key).or_default();
                            apply_headers(state, pending.direction, headers);
                        }
                    } else {
                        self.pending_headers.insert(key, pending);
                    }
                }
                _ => {}
            }

            if self
                .streams
                .get(&key)
                .map(|s| s.request_emitted && s.response_emitted)
                .unwrap_or(false)
            {
                self.streams.remove(&key);
            }
            evict_over_capacity(&mut self.streams, MAX_HTTP2_STREAMS);
        }

        let remaining = buffered[consumed..].to_vec();
        if remaining.is_empty() {
            self.pending_bytes.remove(&connection_key);
        } else {
            self.pending_bytes.insert(connection_key, remaining);
            evict_over_capacity(&mut self.pending_bytes, MAX_HTTP2_STREAMS);
        }

        Some(if events.is_empty() {
            Vec::new()
        } else {
            events
        })
    }

    fn decode_headers(
        &mut self,
        direction: HTTP2Direction,
        block: &[u8],
    ) -> Option<HashMap<String, String>> {
        let decoder = match direction {
            HTTP2Direction::Request => &mut self.request_decoder,
            HTTP2Direction::Response => &mut self.response_decoder,
        };
        let decoded = decoder.decode(block).ok()?;
        let mut headers = HashMap::new();
        for (name, value) in decoded {
            let name = String::from_utf8_lossy(&name).to_ascii_lowercase();
            let value = String::from_utf8_lossy(&value).to_string();
            headers.insert(name, value);
        }
        if let Some(authority) = headers.get(":authority").cloned() {
            headers.entry("host".to_string()).or_insert(authority);
        }
        Some(headers)
    }
}

fn apply_headers(
    state: &mut HTTP2StreamState,
    direction: HTTP2Direction,
    headers: HashMap<String, String>,
) {
    match direction {
        HTTP2Direction::Request => state.request_headers.extend(headers),
        HTTP2Direction::Response => state.response_headers.extend(headers),
    }
}

fn direction_from_function(function: &str) -> Option<HTTP2Direction> {
    let upper = function.to_ascii_uppercase();
    if upper.contains("READ") || upper.contains("RECV") {
        Some(HTTP2Direction::Response)
    } else if upper.contains("WRITE") || upper.contains("SEND") {
        Some(HTTP2Direction::Request)
    } else {
        None
    }
}

enum HTTP2ParseResult<'a> {
    NotHttp2,
    NeedMore,
    Parsed {
        frames: Vec<HTTP2Frame<'a>>,
        consumed: usize,
    },
}

fn parse_http2_frames_prefix(bytes: &[u8], direction: HTTP2Direction) -> HTTP2ParseResult<'_> {
    const PREFACE: &[u8] = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n";
    const HTTP1_REQUEST_PREFIXES: &[&[u8]] = &[
        b"GET ",
        b"POST ",
        b"PUT ",
        b"DELETE ",
        b"HEAD ",
        b"OPTIONS ",
        b"PATCH ",
        b"CONNECT ",
        b"TRACE ",
    ];
    let mut offset = 0usize;
    if direction == HTTP2Direction::Request && !bytes.is_empty() {
        let compared = bytes.len().min(PREFACE.len());
        if bytes[..compared] == PREFACE[..compared] {
            if bytes.len() < PREFACE.len() {
                return HTTP2ParseResult::NeedMore;
            }
            offset = PREFACE.len();
        }
    }

    let remaining = &bytes[offset..];
    let http1_prefixes = match direction {
        HTTP2Direction::Request => HTTP1_REQUEST_PREFIXES,
        HTTP2Direction::Response => &[b"HTTP/1.".as_slice()],
    };
    if !remaining.is_empty()
        && http1_prefixes
            .iter()
            .any(|prefix| remaining.starts_with(prefix) || prefix.starts_with(remaining))
    {
        return HTTP2ParseResult::NotHttp2;
    }
    if remaining.len() < 9 {
        return if offset > 0 {
            HTTP2ParseResult::Parsed {
                frames: Vec::new(),
                consumed: offset,
            }
        } else {
            HTTP2ParseResult::NeedMore
        };
    }

    let mut frames = Vec::new();
    while offset + 9 <= bytes.len() {
        let frame_start = offset;
        let length = ((bytes[offset] as usize) << 16)
            | ((bytes[offset + 1] as usize) << 8)
            | bytes[offset + 2] as usize;
        let frame_type = bytes[offset + 3];
        let flags = bytes[offset + 4];
        let stream_id = ((bytes[offset + 5] as u32 & 0x7f) << 24)
            | ((bytes[offset + 6] as u32) << 16)
            | ((bytes[offset + 7] as u32) << 8)
            | bytes[offset + 8] as u32;
        offset += 9;
        if length > MAX_HTTP2_PENDING_BYTES {
            return HTTP2ParseResult::NotHttp2;
        }
        if length > bytes.len().saturating_sub(offset) {
            offset = frame_start;
            break;
        }
        let stream_id_valid = match frame_type {
            0x4 | 0x6 | 0x7 => stream_id == 0,
            0x0 | 0x1 | 0x3 | 0x5 | 0x8 | 0x9 => stream_id != 0,
            _ => true,
        };
        if !stream_id_valid {
            if frames.is_empty() && frame_start == 0 {
                return HTTP2ParseResult::NotHttp2;
            }
            offset = frame_start;
            break;
        }
        let payload = &bytes[offset..offset + length];
        offset += length;
        // Skip unknown frame types per HTTP/2 spec (only process 0x0..=0x9)
        if frame_type > 0x9 {
            continue;
        }
        frames.push(HTTP2Frame {
            frame_type,
            flags,
            stream_id,
            payload,
        });
    }

    if offset == 0 && frames.is_empty() {
        HTTP2ParseResult::NeedMore
    } else {
        HTTP2ParseResult::Parsed {
            frames,
            consumed: offset,
        }
    }
}

fn headers_payload(flags: u8, payload: &[u8]) -> &[u8] {
    let mut start = 0usize;
    let mut end = payload.len();
    if flags & 0x8 != 0 {
        let Some(pad_len) = payload.first().copied() else {
            return &[];
        };
        start += 1;
        end = end.saturating_sub(pad_len as usize);
    }
    if flags & 0x20 != 0 {
        start = start.saturating_add(5);
    }
    if start > end || end > payload.len() {
        &[]
    } else {
        &payload[start..end]
    }
}

fn data_payload(flags: u8, payload: &[u8]) -> &[u8] {
    if flags & 0x8 == 0 {
        return payload;
    }
    let Some(pad_len) = payload.first().copied() else {
        return &[];
    };
    let start = 1usize;
    let end = payload.len().saturating_sub(pad_len as usize);
    if start > end || end > payload.len() {
        &[]
    } else {
        &payload[start..end]
    }
}

fn looks_like_complete_json(bytes: &[u8]) -> bool {
    let text = String::from_utf8_lossy(bytes);
    text.contains("usageMetadata") && serde_json::from_str::<serde_json::Value>(&text).is_ok()
}

fn create_http2_request_event(
    tid: u64,
    stream_id: u32,
    state: &HTTP2StreamState,
    original_event: &Event,
    include_raw_data: bool,
) -> Event {
    let method = state.request_headers.get(":method").cloned();
    let path = state.request_headers.get(":path").cloned();
    let first_line = format!(
        "{} {} HTTP/2",
        method.as_deref().unwrap_or("HTTP"),
        path.as_deref().unwrap_or("/")
    );
    let body = body_string(&state.request_body);
    let body_hex = (!state.request_body.is_empty()).then(|| hex::encode(&state.request_body));
    let total_size = headers_size(&state.request_headers) + state.request_body.len();
    HTTPEvent {
        tid: synthetic_http2_tid(tid, stream_id),
        message_type: "request".to_string(),
        first_line,
        method,
        path,
        protocol: Some("HTTP/2".to_string()),
        status_code: None,
        status_text: None,
        headers: state.request_headers.clone(),
        content_length: body.as_ref().map(String::len),
        has_body: body.is_some(),
        is_chunked: false,
        body,
        body_hex,
        total_size,
        original_source: "ssl.http2".to_string(),
        raw_data: include_raw_data
            .then(|| String::from_utf8_lossy(&state.request_body).to_string()),
    }
    .to_event(original_event)
}

fn create_http2_response_event(
    tid: u64,
    stream_id: u32,
    state: &HTTP2StreamState,
    original_event: &Event,
    include_raw_data: bool,
) -> Event {
    let status_code = state
        .response_headers
        .get(":status")
        .and_then(|s| s.parse::<u16>().ok())
        .or(Some(200));
    let first_line = format!("HTTP/2 {}", status_code.unwrap_or(200));
    let body = body_string(&state.response_body);
    let body_hex = (!state.response_body.is_empty()).then(|| hex::encode(&state.response_body));
    let total_size = headers_size(&state.response_headers) + state.response_body.len();
    HTTPEvent {
        tid: synthetic_http2_tid(tid, stream_id),
        message_type: "response".to_string(),
        first_line,
        method: None,
        path: None,
        protocol: Some("HTTP/2".to_string()),
        status_code,
        status_text: None,
        headers: state.response_headers.clone(),
        content_length: body.as_ref().map(String::len),
        has_body: body.is_some(),
        is_chunked: false,
        body,
        body_hex,
        total_size,
        original_source: "ssl.http2".to_string(),
        raw_data: include_raw_data
            .then(|| String::from_utf8_lossy(&state.response_body).to_string()),
    }
    .to_event(original_event)
}

fn synthetic_http2_tid(tid: u64, stream_id: u32) -> u64 {
    tid.saturating_mul(1_000_000)
        .saturating_add(stream_id as u64)
}

fn body_string(body: &[u8]) -> Option<String> {
    if body.is_empty() {
        None
    } else {
        Some(String::from_utf8_lossy(body).to_string())
    }
}

fn headers_size(headers: &HashMap<String, String>) -> usize {
    headers.iter().map(|(k, v)| k.len() + v.len()).sum()
}

fn ssl_json_string_to_bytes(data: &str) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(data.len());
    for ch in data.chars() {
        let code = ch as u32;
        if code <= 0xff {
            bytes.push(code as u8);
        } else {
            let mut buf = [0u8; 4];
            bytes.extend_from_slice(ch.encode_utf8(&mut buf).as_bytes());
        }
    }
    bytes
}

fn ssl_event_with_bytes(original_event: &Event, bytes: &[u8]) -> Event {
    let mut event = original_event.clone();
    if let Some(data) = event.data.as_object_mut() {
        data.insert(
            "data".to_string(),
            bytes
                .iter()
                .map(|byte| char::from(*byte))
                .collect::<String>()
                .into(),
        );
        data.insert("data_hex".to_string(), hex::encode(bytes).into());
    }
    event
}

#[async_trait]
impl Analyzer for HTTPParser {
    async fn process(&mut self, stream: EventStream) -> Result<EventStream, AnalyzerError> {
        let include_raw_data = self.include_raw_data;
        let mut http1 = std::mem::take(&mut self.http1);
        let mut http2 = std::mem::take(&mut self.http2);
        let mut websocket = std::mem::take(&mut self.websocket);
        let diagnostics = Arc::new(HTTPParserDiagnostics::default());

        let processed_stream = stream.flat_map(move |event| {
            if event.source == "ssl" {
                diagnostics.ssl_events.fetch_add(1, Ordering::Relaxed);
                if let Some(connection_id) = event
                    .data
                    .get("connection_id")
                    .and_then(|value| value.as_u64())
                    .filter(|value| *value != 0)
                {
                    if let Ok(mut ids) = diagnostics.ssl_connection_ids.lock() {
                        ids.insert(connection_id);
                    }
                    if let Some(sequence) = event
                        .data
                        .get("event_sequence")
                        .and_then(|value| value.as_u64())
                        .filter(|value| *value != 0)
                    {
                        if let Ok(mut sequences) = diagnostics.ssl_connection_sequences.lock() {
                            let previous = sequences.entry(connection_id).or_insert(0);
                            if *previous != 0 && sequence > previous.saturating_add(1) {
                                diagnostics.ssl_sequence_gaps.fetch_add(sequence - *previous - 1, Ordering::Relaxed);
                            } else if sequence <= *previous {
                                diagnostics.ssl_sequence_reorders.fetch_add(1, Ordering::Relaxed);
                            }
                            *previous = (*previous).max(sequence);
                        }
                    }
                } else {
                    diagnostics.ssl_connection_id_missing_events.fetch_add(1, Ordering::Relaxed);
                }
                let tid = event.data.get("tid").and_then(|value| value.as_u64()).unwrap_or(0);
                let function = event
                    .data
                    .get("function")
                    .and_then(|value| value.as_str())
                    .unwrap_or("");
                let captured_bytes = event
                    .data
                    .get("buf_size")
                    .and_then(|value| value.as_u64())
                    .or_else(|| {
                        event
                            .data
                            .get("data")
                            .and_then(|value| value.as_str())
                            .map(|value| value.len() as u64)
                    })
                    .unwrap_or(0);
                if function.contains("READ") || function.contains("RECV") {
                    diagnostics.ssl_read_events.fetch_add(1, Ordering::Relaxed);
                    diagnostics.ssl_read_bytes.fetch_add(captured_bytes, Ordering::Relaxed);
                    if let Ok(mut per_thread) = diagnostics.per_thread.lock() {
                        per_thread.entry((event.pid, tid)).or_default().read_events += 1;
                    }
                } else if function.contains("WRITE") || function.contains("SEND") {
                    diagnostics.ssl_write_events.fetch_add(1, Ordering::Relaxed);
                    diagnostics.ssl_write_bytes.fetch_add(captured_bytes, Ordering::Relaxed);
                    if let Ok(mut per_thread) = diagnostics.per_thread.lock() {
                        per_thread.entry((event.pid, tid)).or_default().write_events += 1;
                    }
                } else {
                    diagnostics.unknown_direction_events.fetch_add(1, Ordering::Relaxed);
                }
                if event.data.get("truncated").and_then(|value| value.as_bool()) == Some(true) {
                    diagnostics.truncated_ssl_events.fetch_add(1, Ordering::Relaxed);
                    diagnostics.ssl_bytes_lost.fetch_add(
                        event.data.get("bytes_lost").and_then(|value| value.as_u64()).unwrap_or(0),
                        Ordering::Relaxed,
                    );
                }
            }
            let events = if event.source == "ssl" {
                Self::handle_ssl_event(
                    &mut http1,
                    &mut http2,
                    &mut websocket,
                    event,
                    include_raw_data,
                    &diagnostics,
                )
            } else {
                vec![event]
            };
            for output in &events {
                if output.source == "ssl" {
                    diagnostics.unparsed_ssl_events.fetch_add(1, Ordering::Relaxed);
                }
                if output.source == "http_parser"
                    && output
                        .data
                        .get("message_type")
                        .and_then(|value| value.as_str())
                        == Some("response")
                {
                    diagnostics.http_responses.fetch_add(1, Ordering::Relaxed);
                    diagnostics.http_response_body_bytes.fetch_add(output
                        .data
                        .get("body")
                        .and_then(|value| value.as_str())
                        .map(|body| body.len() as u64)
                        .unwrap_or(0), Ordering::Relaxed);
                }
            }
            let pending_http1_bytes = http1.pending.values().map(|message| message.bytes.len()).sum();
            diagnostics.max_pending_http1_bytes.fetch_max(pending_http1_bytes, Ordering::Relaxed);
            diagnostics.current_pending_http1_bytes.store(pending_http1_bytes, Ordering::Relaxed);
            diagnostics.current_pending_http1_buffers.store(http1.pending.len(), Ordering::Relaxed);
            let mut request_buffers = 0;
            let mut response_buffers = 0;
            let mut header_wait_buffers = 0;
            let mut content_length_buffers = 0;
            let mut chunked_buffers = 0;
            let mut expected_body_bytes = 0usize;
            let mut chunked_wait_stage = 0usize;
            let mut chunked_completed_chunks = 0usize;
            let mut chunked_progress_offset = 0usize;
            let mut first_chunk_size = 0usize;
            let mut first_chunk_boundary_class = 0usize;
            for ((_, _, _, direction), pending) in &http1.pending {
                match direction {
                    HTTP2Direction::Request => request_buffers += 1,
                    HTTP2Direction::Response => response_buffers += 1,
                }
                match pending.framing {
                    HTTP1BodyFraming::Headers => header_wait_buffers += 1,
                    HTTP1BodyFraming::ContentLength(length) => {
                        content_length_buffers += 1;
                        expected_body_bytes = expected_body_bytes.saturating_add(length);
                    }
                    HTTP1BodyFraming::Chunked => {
                        chunked_buffers += 1;
                        chunked_wait_stage = http1_chunked_wait_stage(&pending.bytes, pending.header_len);
                        (chunked_completed_chunks, chunked_progress_offset) =
                            http1_chunked_progress(&pending.bytes, pending.header_len);
                        (first_chunk_size, first_chunk_boundary_class) =
                            http1_first_chunk_metadata(&pending.bytes, pending.header_len);
                    }
                }
            }
            diagnostics.pending_http1_request_buffers.store(request_buffers, Ordering::Relaxed);
            diagnostics.pending_http1_response_buffers.store(response_buffers, Ordering::Relaxed);
            diagnostics.pending_http1_header_wait_buffers.store(header_wait_buffers, Ordering::Relaxed);
            diagnostics.pending_http1_content_length_buffers.store(content_length_buffers, Ordering::Relaxed);
            diagnostics.pending_http1_chunked_buffers.store(chunked_buffers, Ordering::Relaxed);
            diagnostics.pending_http1_expected_body_bytes.store(expected_body_bytes, Ordering::Relaxed);
            diagnostics.pending_http1_chunked_wait_stage.store(chunked_wait_stage, Ordering::Relaxed);
            diagnostics.pending_http1_chunked_completed_chunks.store(chunked_completed_chunks, Ordering::Relaxed);
            diagnostics.pending_http1_chunked_progress_offset.store(chunked_progress_offset, Ordering::Relaxed);
            diagnostics.pending_http1_first_chunk_size.store(first_chunk_size, Ordering::Relaxed);
            diagnostics.pending_http1_first_chunk_boundary_class.store(first_chunk_boundary_class, Ordering::Relaxed);
            if !http1.pending.is_empty() {
                diagnostics.http1_pending_events.fetch_add(1, Ordering::Relaxed);
            }
            diagnostics.max_pending_http2_bytes.fetch_max(
                http2.pending_bytes.values().map(Vec::len).sum(),
                Ordering::Relaxed,
            );
            diagnostics.max_pending_http2_streams.fetch_max(http2.streams.len(), Ordering::Relaxed);
            diagnostics.max_pending_http2_header_blocks.fetch_max(
                http2.pending_headers.len(),
                Ordering::Relaxed,
            );
            diagnostics.current_pending_http2_bytes.store(
                http2.pending_bytes.values().map(Vec::len).sum(),
                Ordering::Relaxed,
            );
            diagnostics.current_pending_http2_buffers.store(http2.pending_bytes.len(), Ordering::Relaxed);
            stream::iter(events)
        });

        Ok(Box::pin(processed_stream))
    }
}

fn extend_capped(buffer: &mut Vec<u8>, data: &[u8], max: usize) {
    buffer.extend_from_slice(data);
    let overflow = buffer.len().saturating_sub(max);
    if overflow > 0 {
        buffer.drain(0..overflow);
    }
}

fn evict_over_capacity<K, T>(map: &mut HashMap<K, T>, max: usize)
where
    K: Copy + Eq + Hash,
{
    while map.len() > max {
        let Some(key) = map.keys().next().copied() else {
            break;
        };
        map.remove(&key);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::analyzers::{HTTPDecompressor, SSEProcessor};
    use crate::view::MaterializedView;
    use flate2::write::GzEncoder;
    use flate2::{Compress, Compression, FlushCompress};
    use futures::StreamExt;
    use hpack::Encoder as HpackEncoder;
    use serde_json::json;
    use std::io::Write;

    fn ssl_event(timestamp: u64, function: &str, bytes: Vec<u8>) -> Event {
        Event::new_with_timestamp(
            timestamp,
            "ssl".to_string(),
            4242,
            "node".to_string(),
            json!({
                "tid": 7,
                "function": function,
                "data": bytes_to_ssl_json_string(&bytes),
                "data_hex": hex::encode(&bytes),
            }),
        )
    }

    fn bytes_to_ssl_json_string(bytes: &[u8]) -> String {
        bytes.iter().map(|b| char::from(*b)).collect()
    }

    #[test]
    fn preserves_binary_body_bytes_after_http1_chunked_reassembly() {
        let binary_body = [0x28, 0xb5, 0x2f, 0xfd, 0x00, 0xff, 0x19];
        let mut raw = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Encoding: zstd\r\n\r\n".to_vec();
        let header_len = raw.len();
        raw.extend_from_slice(format!("{:X}\r\n", binary_body.len()).as_bytes());
        raw.extend_from_slice(&binary_body);
        raw.extend_from_slice(b"\r\n0\r\n\r\n");

        let (decoded, raw_end) = decode_http1_chunked_body(&raw, header_len).unwrap();
        let message = parse_http1_chunked_message(&raw, &decoded, raw_end, header_len).unwrap();

        assert_eq!(message.body_bytes.as_deref(), Some(binary_body.as_slice()));
    }

    fn frame(frame_type: u8, flags: u8, stream_id: u32, payload: &[u8]) -> Vec<u8> {
        let len = payload.len();
        let mut out = vec![
            ((len >> 16) & 0xff) as u8,
            ((len >> 8) & 0xff) as u8,
            (len & 0xff) as u8,
            frame_type,
            flags,
            ((stream_id >> 24) & 0x7f) as u8,
            ((stream_id >> 16) & 0xff) as u8,
            ((stream_id >> 8) & 0xff) as u8,
            (stream_id & 0xff) as u8,
        ];
        out.extend_from_slice(payload);
        out
    }

    fn compressed_websocket_frame(compressor: &mut Compress, payload: &[u8]) -> Vec<u8> {
        let mut compressed = Vec::with_capacity(payload.len() * 2 + 64);
        compressor
            .compress_vec(payload, &mut compressed, FlushCompress::Sync)
            .unwrap();
        assert!(compressed.ends_with(&[0, 0, 0xff, 0xff]));
        compressed.truncate(compressed.len() - 4);

        let mut frame = vec![0xc1];
        if compressed.len() <= 125 {
            frame.push(0x80 | compressed.len() as u8);
        } else {
            frame.push(0x80 | 126);
            frame.extend_from_slice(&(compressed.len() as u16).to_be_bytes());
        }
        let mask = [0x12, 0x34, 0x56, 0x78];
        frame.extend_from_slice(&mask);
        frame.extend(
            compressed
                .iter()
                .enumerate()
                .map(|(i, byte)| byte ^ mask[i % 4]),
        );
        frame
    }

    #[tokio::test]
    async fn parses_compressed_websocket_responses_with_context_takeover() {
        let handshake = b"GET /backend-api/codex/responses HTTP/1.1\r\n\
Host: chatgpt.com\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\
sec-websocket-extensions: permessage-deflate\r\n\r\n"
            .to_vec();
        let shared = "shared context ".repeat(400);
        let first = json!({
            "type": "response.create",
            "model": "gpt-test",
            "input": [{"role": "developer", "content": shared}],
        })
        .to_string();
        let prompt = "agentsight websocket exact prompt 7f31";
        let second = json!({
            "type": "response.create",
            "model": "gpt-test",
            "input": [{"role": "user", "content": format!("{shared}{prompt}")}],
        })
        .to_string();
        let mut compressor = Compress::new(Compression::fast(), false);
        let input: EventStream = Box::pin(stream::iter(vec![
            ssl_event(1, "WRITE/SEND", handshake),
            ssl_event(
                2,
                "WRITE/SEND",
                compressed_websocket_frame(&mut compressor, first.as_bytes()),
            ),
            ssl_event(
                3,
                "WRITE/SEND",
                compressed_websocket_frame(&mut compressor, second.as_bytes()),
            ),
        ]));
        let mut parser = HTTPParser::new().disable_raw_data();
        let output: Vec<Event> = parser.process(input).await.unwrap().collect().await;

        assert_eq!(output.len(), 3);
        assert_eq!(output[2].data["path"], "/backend-api/codex/responses");
        assert!(output[2].data["body"].as_str().unwrap().contains(prompt));
        let mut view = MaterializedView::new();
        for event in output {
            view.ingest_event(&event).unwrap();
        }
        let calls = view.llm_call_rows(10);
        assert_eq!(calls.len(), 2);
        assert_eq!(calls[0].call_kind.as_deref(), Some("responses"));
        assert!(
            calls
                .iter()
                .any(|call| call.request.to_string().contains(prompt))
        );
    }

    #[tokio::test]
    async fn reassembles_fragmented_http1_request_before_materializing_call() {
        let request_body = br#"{"model":"deepseek-test","messages":[{"role":"user","content":"fragmented request"}]}"#;
        let request_head = format!(
            "POST /v1/messages HTTP/1.1\r\nHost: api.example.test\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n",
            request_body.len()
        );
        let mut request = request_head.as_bytes().to_vec();
        request.extend_from_slice(request_body);
        let split = request_head.len() + 8;
        let response_body = br#"{"model":"deepseek-test","content":[{"type":"text","text":"ok"}],"usage":{"input_tokens":5,"output_tokens":1}}"#;
        let response_head = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n",
            response_body.len()
        );
        let mut response = response_head.into_bytes();
        response.extend_from_slice(response_body);

        let input: EventStream = Box::pin(stream::iter(vec![
            ssl_event(1, "WRITE/SEND", request[..split].to_vec()),
            ssl_event(2, "WRITE/SEND", request[split..].to_vec()),
            ssl_event(3, "READ/RECV", response),
        ]));
        let mut parser = HTTPParser::new().disable_raw_data();
        let output: Vec<Event> = parser.process(input).await.unwrap().collect().await;

        assert_eq!(output.len(), 2);
        assert_eq!(output[0].data["message_type"], "request");
        assert_eq!(
            output[0].data["body"].as_str(),
            Some(String::from_utf8_lossy(request_body).as_ref())
        );
        assert_eq!(output[1].data["message_type"], "response");

        let mut view = MaterializedView::new();
        for event in output {
            view.ingest_event(&event).unwrap();
        }
        let calls = view.llm_call_rows(10);
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].status, "complete");
        assert_eq!(calls[0].request["model"], "deepseek-test");
        assert_eq!(calls[0].response["model"], "deepseek-test");
    }

    #[tokio::test]
    async fn reassembles_fragmented_http1_chunked_sse_response_before_materializing_tool_call() {
        let request_body = br#"{"model":"claude-test","stream":true,"messages":[{"role":"user","content":"run a command"}]}"#;
        let request_head = format!(
            "POST /v1/messages HTTP/1.1\r\nHost: api.example.test\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n",
            request_body.len()
        );
        let mut request = request_head.as_bytes().to_vec();
        request.extend_from_slice(request_body);

        let response_body = concat!(
            "event: message_start\ndata: {\"type\":\"message_start\",\"message\":{\"id\":\"msg_1\",\"type\":\"message\",\"role\":\"assistant\",\"model\":\"claude-test\",\"content\":[],\"usage\":{\"input_tokens\":12,\"output_tokens\":0}}}\n\n",
            "event: content_block_start\ndata: {\"type\":\"content_block_start\",\"index\":0,\"content_block\":{\"type\":\"tool_use\",\"id\":\"toolu_chunked_1\",\"name\":\"Bash\",\"input\":{}}}\n\n",
            "event: content_block_delta\ndata: {\"type\":\"content_block_delta\",\"index\":0,\"delta\":{\"type\":\"input_json_delta\",\"partial_json\":\"{\\\"command\\\":\\\"python3 x.py\\\"}\"}}\n\n",
            "event: content_block_stop\ndata: {\"type\":\"content_block_stop\",\"index\":0}\n\n",
            "event: message_delta\ndata: {\"type\":\"message_delta\",\"delta\":{\"stop_reason\":\"tool_use\",\"stop_sequence\":null},\"usage\":{\"output_tokens\":5}}\n\n",
            "event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n"
        )
        .as_bytes();

        let mut chunked_body = format!("{:X}\r\n", response_body.len()).into_bytes();
        chunked_body.extend_from_slice(response_body);
        chunked_body.extend_from_slice(b"\n0\r\n\n");
        let response_head = b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n\r\n";
        let mut response = response_head.to_vec();
        response.extend_from_slice(&chunked_body);

        let mut ssl_events = vec![ssl_event(1, "WRITE/SEND", request)];
        for (index, fragment) in response.chunks(19).enumerate() {
            ssl_events.push(ssl_event(
                (index + 2) as u64,
                "READ/RECV",
                fragment.to_vec(),
            ));
        }
        let input: EventStream = Box::pin(stream::iter(ssl_events));
        let mut parser = HTTPParser::new().disable_raw_data();
        let parsed = parser.process(input).await.unwrap();
        let mut decompressor = HTTPDecompressor::new();
        let decompressed = decompressor.process(parsed).await.unwrap();
        let mut sse = SSEProcessor::new();
        let output: Vec<Event> = sse.process(decompressed).await.unwrap().collect().await;

        assert_eq!(output.len(), 2);
        assert_eq!(output[0].data["message_type"], "request");
        assert_eq!(output[1].source, "sse_processor");
        assert_eq!(output[1].data["status_code"], 200);

        let mut view = MaterializedView::new();
        for event in output {
            view.ingest_event(&event).unwrap();
        }
        let snapshot = view.export_snapshot(crate::model::SnapshotOptions { audit_limit: 0 });
        assert_eq!(snapshot.summary.llm_calls, 1);
        assert_eq!(snapshot.summary.token_usage_rows, 1);
        assert_eq!(snapshot.summary.input_tokens, 12);
        assert_eq!(snapshot.summary.output_tokens, 5);
        assert_eq!(snapshot.tool_calls.len(), 1);
        assert_eq!(snapshot.tool_calls[0].tool_name.as_deref(), Some("Bash"));
        assert_eq!(
            snapshot.tool_calls[0].tool_call_id.as_deref(),
            Some("toolu_chunked_1")
        );
        assert_eq!(snapshot.tool_calls[0].input["command"], "python3 x.py");
    }

    #[tokio::test]
    async fn parses_http2_gemini_usage_into_http_events() {
        let mut request_encoder = HpackEncoder::new();
        let mut response_encoder = HpackEncoder::new();
        let request_headers = [
            (&b":method"[..], &b"POST"[..]),
            (&b":scheme"[..], &b"https"[..]),
            (&b":authority"[..], &b"cloudcode-pa.googleapis.com"[..]),
            (&b":path"[..], &b"/v1internal:generateContent"[..]),
        ];
        let response_headers = [
            (&b":status"[..], &b"200"[..]),
            (&b"content-type"[..], &b"application/json"[..]),
        ];
        let request_body = br#"{"model":"gemini-2.5-pro","request":{"contents":[]}}"#;
        let response_body = br#"{"usageMetadata":{"promptTokenCount":11,"candidatesTokenCount":4,"totalTokenCount":15}}"#;

        let mut request_bytes = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n".to_vec();
        request_bytes.extend(frame(0x1, 0x4, 1, &request_encoder.encode(request_headers)));
        request_bytes.extend(frame(0x0, 0x1, 1, request_body));

        let mut response_bytes = Vec::new();
        response_bytes.extend(frame(
            0x1,
            0x4,
            1,
            &response_encoder.encode(response_headers),
        ));
        response_bytes.extend(frame(0x0, 0x1, 1, response_body));

        let input: EventStream = Box::pin(stream::iter(vec![
            ssl_event(1, "WRITE/SEND", request_bytes),
            ssl_event(2, "READ/RECV", response_bytes),
        ]));
        let mut parser = HTTPParser::new().disable_raw_data();
        let output: Vec<Event> = parser.process(input).await.unwrap().collect().await;

        assert_eq!(output.len(), 2);
        assert_eq!(output[0].source, "http_parser");
        assert_eq!(output[0].data["message_type"], "request");
        assert_eq!(output[0].data["path"], "/v1internal:generateContent");
        assert_eq!(
            output[0].data["headers"]["host"],
            "cloudcode-pa.googleapis.com"
        );
        assert_eq!(output[1].source, "http_parser");
        assert_eq!(output[1].data["message_type"], "response");
        assert_eq!(output[1].data["status_code"], 200);
        assert!(
            output[1].data["body"]
                .as_str()
                .unwrap()
                .contains("usageMetadata")
        );

        let mut view = MaterializedView::new();
        for event in output {
            view.ingest_event(&event).unwrap();
        }
        let total = view
            .export_snapshot(crate::model::SnapshotOptions { audit_limit: 0 })
            .token_summary
            .into_iter()
            .map(|row| row.total_tokens)
            .sum::<i64>();
        assert_eq!(total, 15);
    }

    #[tokio::test]
    async fn http2_gzip_sse_capture_pipeline_reaches_materialized_view_across_byte_boundaries() {
        let mut request_encoder = HpackEncoder::new();
        let mut response_encoder = HpackEncoder::new();
        let request_headers = [
            (&b":method"[..], &b"POST"[..]),
            (&b":scheme"[..], &b"https"[..]),
            (&b":authority"[..], &b"api.openai.com"[..]),
            (&b":path"[..], &b"/v1/chat/completions"[..]),
        ];
        let response_headers = [
            (&b":status"[..], &b"200"[..]),
            (&b"content-type"[..], &b"text/event-stream"[..]),
            (&b"content-encoding"[..], &b"gzip"[..]),
        ];
        let request_body = br#"{"model":"gpt-test","metadata":{"session_id":"sess-h2"}}"#;
        let mut gzip = GzEncoder::new(Vec::new(), Compression::default());
        gzip.write_all(
            b"data: {\"id\":\"chatcmpl-tool\",\"object\":\"chat.completion.chunk\",\"model\":\"gpt-test\",\"choices\":[{\"index\":0,\"delta\":{\"tool_calls\":[{\"index\":0,\"id\":\"call_1\",\"type\":\"function\",\"function\":{\"name\":\"lookup\",\"arguments\":\"{\\\"q\\\":\\\"x\\\"}\"}}]},\"finish_reason\":null}]}\n\ndata: {\"id\":\"chatcmpl-tool\",\"object\":\"chat.completion.chunk\",\"model\":\"gpt-test\",\"choices\":[{\"index\":0,\"delta\":{},\"finish_reason\":\"tool_calls\"}],\"usage\":{\"prompt_tokens\":2,\"completion_tokens\":5}}\n\ndata: [DONE]\n\n",
        )
        .unwrap();
        let response_body = gzip.finish().unwrap();

        let mut request_bytes = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n".to_vec();
        request_bytes.extend(frame(0x1, 0x4, 1, &request_encoder.encode(request_headers)));
        request_bytes.extend(frame(0x0, 0x1, 1, request_body));

        let mut response_bytes = Vec::new();
        response_bytes.extend(frame(
            0x1,
            0x4,
            1,
            &response_encoder.encode(response_headers),
        ));
        response_bytes.extend(frame(0x0, 0x1, 1, &response_body));

        let mut input_events = vec![ssl_event(1, "WRITE/SEND", request_bytes)];
        input_events.extend(
            response_bytes
                .into_iter()
                .enumerate()
                .map(|(index, byte)| ssl_event(index as u64 + 2, "READ/RECV", vec![byte])),
        );
        let input: EventStream = Box::pin(stream::iter(input_events));
        let mut parser = HTTPParser::new().disable_raw_data();
        let parsed = parser.process(input).await.unwrap();
        let mut decompressor = HTTPDecompressor::new();
        let decompressed = decompressor.process(parsed).await.unwrap();
        let mut sse = SSEProcessor::new();
        let output: Vec<Event> = sse.process(decompressed).await.unwrap().collect().await;

        assert_eq!(output.len(), 2);
        assert_eq!(output[0].data["message_type"], "request");
        assert_eq!(output[1].source, "sse_processor");
        assert_eq!(output[1].data["status_code"], 200);

        let mut view = MaterializedView::new();
        for event in output {
            view.ingest_event(&event).unwrap();
        }
        let snapshot = view.export_snapshot(crate::model::SnapshotOptions { audit_limit: 0 });
        assert_eq!(snapshot.summary.llm_calls, 1);
        assert_eq!(snapshot.summary.token_usage_rows, 1);
        assert_eq!(snapshot.summary.input_tokens, 2);
        assert_eq!(snapshot.summary.output_tokens, 5);
        assert_eq!(snapshot.summary.total_tokens, 7);
        assert_eq!(snapshot.tool_calls.len(), 1);
        assert_eq!(snapshot.tool_calls[0].tool_name.as_deref(), Some("lookup"));
        assert_eq!(snapshot.tool_calls[0].input["q"], "x");
        let calls = view.llm_call_rows(10);
        assert_eq!(calls[0].status, "complete");
        assert_eq!(calls[0].session_id.as_deref(), Some("sess-h2"));
        assert_eq!(calls[0].call_kind.as_deref(), Some("chat"));
        assert_eq!(calls[0].finish_reason.as_deref(), Some("tool_calls"));
    }

    #[tokio::test]
    async fn http2_anthropic_sse_tool_input_delta_reaches_materialized_view() {
        let mut request_encoder = HpackEncoder::new();
        let mut response_encoder = HpackEncoder::new();
        let request_headers = [
            (&b":method"[..], &b"POST"[..]),
            (&b":scheme"[..], &b"https"[..]),
            (&b":authority"[..], &b"api.deepseek.com"[..]),
            (&b":path"[..], &b"/anthropic/v1/messages?beta=true"[..]),
            (&b"content-type"[..], &b"application/json"[..]),
        ];
        let response_headers = [
            (&b":status"[..], &b"200"[..]),
            (&b"content-type"[..], &b"text/event-stream"[..]),
        ];
        let request_body = br#"{"model":"deepseek-flash","stream":true,"messages":[{"role":"user","content":"run a command"}]}"#;
        let response_body = concat!(
            "event: message_start\ndata: {\"type\":\"message_start\",\"message\":{\"id\":\"msg_1\",\"type\":\"message\",\"role\":\"assistant\",\"model\":\"deepseek-flash\",\"content\":[],\"usage\":{\"input_tokens\":12,\"output_tokens\":0}}}\n\n",
            "event: content_block_start\ndata: {\"type\":\"content_block_start\",\"index\":0,\"content_block\":{\"type\":\"tool_use\",\"id\":\"toolu_1\",\"name\":\"Bash\",\"input\":{}}}\n\n",
            "event: content_block_delta\ndata: {\"type\":\"content_block_delta\",\"index\":0,\"delta\":{\"type\":\"input_json_delta\",\"partial_json\":\"{\\\"command\\\":\\\"python3 x.py\\\"}\"}}\n\n",
            "event: content_block_stop\ndata: {\"type\":\"content_block_stop\",\"index\":0}\n\n",
            "event: message_delta\ndata: {\"type\":\"message_delta\",\"delta\":{\"stop_reason\":\"tool_use\",\"stop_sequence\":null},\"usage\":{\"output_tokens\":5}}\n\n",
            "event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n"
        );

        let mut request_bytes = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n".to_vec();
        request_bytes.extend(frame(0x1, 0x4, 1, &request_encoder.encode(request_headers)));
        request_bytes.extend(frame(0x0, 0x1, 1, request_body));

        let mut response_bytes = Vec::new();
        response_bytes.extend(frame(
            0x1,
            0x4,
            1,
            &response_encoder.encode(response_headers),
        ));
        response_bytes.extend(frame(0x0, 0x1, 1, response_body.as_bytes()));

        let input: EventStream = Box::pin(stream::iter(vec![
            ssl_event(1, "WRITE/SEND", request_bytes),
            ssl_event(2, "READ/RECV", response_bytes),
        ]));
        let mut parser = HTTPParser::new().disable_raw_data();
        let parsed = parser.process(input).await.unwrap();
        let mut decompressor = HTTPDecompressor::new();
        let decompressed = decompressor.process(parsed).await.unwrap();
        let mut sse = SSEProcessor::new();
        let output: Vec<Event> = sse.process(decompressed).await.unwrap().collect().await;

        assert_eq!(output.len(), 2);
        assert_eq!(output[0].data["message_type"], "request");
        assert_eq!(output[1].source, "sse_processor");
        assert_eq!(output[1].data["status_code"], 200);

        let mut view = MaterializedView::new();
        for event in output {
            view.ingest_event(&event).unwrap();
        }
        let snapshot = view.export_snapshot(crate::model::SnapshotOptions { audit_limit: 0 });
        assert_eq!(snapshot.summary.llm_calls, 1);
        assert_eq!(snapshot.summary.token_usage_rows, 1);
        assert_eq!(snapshot.summary.input_tokens, 12);
        assert_eq!(snapshot.summary.output_tokens, 5);
        assert_eq!(snapshot.tool_calls.len(), 1);
        assert_eq!(snapshot.tool_calls[0].tool_name.as_deref(), Some("Bash"));
        assert_eq!(
            snapshot.tool_calls[0].tool_call_id.as_deref(),
            Some("toolu_1")
        );
        assert_eq!(snapshot.tool_calls[0].input["command"], "python3 x.py");
        let calls = view.llm_call_rows(10);
        assert_eq!(calls[0].status, "complete");
        assert_eq!(calls[0].finish_reason.as_deref(), Some("tool_use"));
    }

    #[test]
    fn rejects_non_http2_frames() {
        assert!(matches!(
            parse_http2_frames_prefix(b"GET / HTTP/1.1\r\n\r\n", HTTP2Direction::Request),
            HTTP2ParseResult::NotHttp2
        ));
    }

    #[test]
    fn decodes_http1_chunked_payload_with_lf_only_delimiters() {
        let encoded = b"4\r\nWiki\n0\r\n\n";
        let (decoded, end) = decode_http1_chunked_body(encoded, 0).unwrap();
        assert_eq!(decoded, b"Wiki");
        assert_eq!(end, encoded.len());
        assert_eq!(http1_chunked_wait_stage(encoded, 0), 0);
    }

    #[test]
    fn restores_json_escaped_ssl_bytes_without_utf8_ambiguity() {
        let escaped_latin1_byte = "\u{00e9}";
        let utf8_e_acute_as_byte_escapes = "\u{00c3}\u{00a9}";
        assert_eq!(ssl_json_string_to_bytes(escaped_latin1_byte), [0xe9]);
        assert_eq!(ssl_json_string_to_bytes(utf8_e_acute_as_byte_escapes), [0xc3, 0xa9]);
    }
}
