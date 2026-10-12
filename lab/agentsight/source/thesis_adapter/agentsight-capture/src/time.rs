// SPDX-License-Identifier: MIT
// Copyright (c) 2026 eunomia-bpf org.

//! Timestamp conversion utilities
//!
//! All timestamps in the system are standardized to milliseconds since UNIX epoch
//! for consistency and ease of use in the frontend.

use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Copy)]
struct BootEpochAnchor {
    epoch_ns: u64,
    uncertainty_ns: u64,
}

/// Cached high-precision mapping from CLOCK_MONOTONIC to UNIX epoch.
static BOOT_EPOCH_ANCHOR: OnceLock<BootEpochAnchor> = OnceLock::new();

fn realtime_ns() -> Option<u64> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .ok()
        .and_then(|duration| u64::try_from(duration.as_nanos()).ok())
}

#[cfg(target_os = "linux")]
fn monotonic_ns() -> Option<u64> {
    let mut value = libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    // SAFETY: value points to writable memory and CLOCK_MONOTONIC is supported on Linux.
    let status = unsafe { libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut value) };
    if status != 0 || value.tv_sec < 0 || value.tv_nsec < 0 {
        return None;
    }
    (value.tv_sec as u64)
        .checked_mul(1_000_000_000)
        .and_then(|seconds| seconds.checked_add(value.tv_nsec as u64))
}

#[cfg(target_os = "linux")]
fn clock_resolution_ns(clock_id: libc::clockid_t) -> Option<u64> {
    let mut value = libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    // SAFETY: value points to writable memory and the supplied clock IDs are supported on Linux.
    let status = unsafe { libc::clock_getres(clock_id, &mut value) };
    if status != 0 || value.tv_sec < 0 || value.tv_nsec < 0 {
        return None;
    }
    (value.tv_sec as u64)
        .checked_mul(1_000_000_000)
        .and_then(|seconds| seconds.checked_add(value.tv_nsec as u64))
}

#[cfg(target_os = "linux")]
fn paired_clock_resolution_floor_ns() -> u64 {
    clock_resolution_ns(libc::CLOCK_REALTIME)
        .into_iter()
        .chain(clock_resolution_ns(libc::CLOCK_MONOTONIC))
        .max()
        .unwrap_or(1)
        .max(1)
}

#[cfg(not(target_os = "linux"))]
fn monotonic_ns() -> Option<u64> {
    None
}

#[cfg(not(target_os = "linux"))]
fn paired_clock_resolution_floor_ns() -> u64 {
    1
}

fn uncertainty_with_resolution_floor(measured_half_width_ns: u64, resolution_ns: u64) -> u64 {
    measured_half_width_ns.max(resolution_ns).max(1)
}

fn fallback_boot_epoch_ns() -> u64 {
    if let Ok(boot_time) = u64::try_from(sysinfo::System::boot_time())
        && boot_time > 0
    {
        return boot_time.saturating_mul(1_000_000_000);
    }

    let now_ns = realtime_ns().unwrap_or(0);
    let uptime_ns = sysinfo::System::uptime()
        .max(1)
        .saturating_mul(1_000_000_000);
    now_ns.saturating_sub(uptime_ns)
}

fn measure_boot_epoch_anchor() -> BootEpochAnchor {
    let mut best: Option<BootEpochAnchor> = None;
    let resolution_floor_ns = paired_clock_resolution_floor_ns();
    for _ in 0..8 {
        let Some(before_ns) = realtime_ns() else {
            continue;
        };
        let Some(monotonic_ns) = monotonic_ns() else {
            continue;
        };
        let Some(after_ns) = realtime_ns() else {
            continue;
        };
        if after_ns < before_ns {
            continue;
        }
        let width_ns = after_ns - before_ns;
        let midpoint_ns = before_ns.saturating_add(width_ns / 2);
        let candidate = BootEpochAnchor {
            epoch_ns: midpoint_ns.saturating_sub(monotonic_ns),
            uncertainty_ns: uncertainty_with_resolution_floor(
                width_ns.saturating_add(1) / 2,
                resolution_floor_ns,
            ),
        };
        if best.is_none_or(|current| candidate.uncertainty_ns < current.uncertainty_ns) {
            best = Some(candidate);
        }
    }
    best.unwrap_or(BootEpochAnchor {
        epoch_ns: fallback_boot_epoch_ns(),
        uncertainty_ns: 1_000_000_000,
    })
}

fn boot_epoch_anchor() -> &'static BootEpochAnchor {
    BOOT_EPOCH_ANCHOR.get_or_init(measure_boot_epoch_anchor)
}

/// Get the high-precision boot epoch offset in nanoseconds since UNIX epoch.
pub fn get_boot_time_ns() -> u64 {
    boot_epoch_anchor().epoch_ns
}

/// Get the uncertainty of the paired realtime/monotonic sample.
///
/// The value is never zero: it is bounded below by the larger reported resolution of
/// CLOCK_REALTIME and CLOCK_MONOTONIC on Linux.
pub fn get_boot_time_uncertainty_ns() -> u64 {
    boot_epoch_anchor().uncertainty_ns
}

/// Get the system boot time in seconds since UNIX epoch
///
/// This uses the platform process backend and caches the result.
pub fn get_boot_time_secs() -> i64 {
    (get_boot_time_ns() / 1_000_000_000) as i64
}

/// Convert nanoseconds since boot to milliseconds since UNIX epoch
///
/// This is used to convert eBPF timestamps (from bpf_ktime_get_ns()) to standard UNIX timestamps.
///
/// # Arguments
/// * `ns_since_boot` - Nanoseconds since system boot (from bpf_ktime_get_ns())
///
/// # Returns
/// Milliseconds since UNIX epoch (1970-01-01 00:00:00 UTC)
pub fn boot_ns_to_epoch_ms(ns_since_boot: u64) -> u64 {
    boot_ns_to_epoch_ms_with_boot_epoch(get_boot_time_ns(), ns_since_boot)
}

fn boot_ns_to_epoch_ms_with_boot_epoch(boot_epoch_ns: u64, ns_since_boot: u64) -> u64 {
    boot_epoch_ns.saturating_add(ns_since_boot) / 1_000_000
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_boot_time_is_reasonable() {
        let boot_time = get_boot_time_secs();
        // Boot time should be in the past (less than current time)
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;
        assert!(boot_time < now);
        // Boot time should be reasonable (after year 2020)
        assert!(boot_time > 1577836800); // 2020-01-01
    }

    #[test]
    fn test_boot_ns_to_epoch_ms_conversion() {
        // Test with a known timestamp: 1000 seconds after boot
        let ns_since_boot = 1_000_000_000_000u64; // 1000 seconds in nanoseconds
        let result_ms = boot_ns_to_epoch_ms(ns_since_boot);

        let expected_ms = (get_boot_time_ns() + ns_since_boot) / 1_000_000;

        assert_eq!(result_ms, expected_ms);
    }

    #[test]
    fn test_fractional_boot_epoch_is_preserved() {
        let result_ms = boot_ns_to_epoch_ms_with_boot_epoch(1_500_000_000, 600_000_000);
        assert_eq!(result_ms, 2_100);
    }

    #[test]
    fn test_boot_anchor_uncertainty_is_bounded() {
        assert!(get_boot_time_uncertainty_ns() > 0);
        assert!(get_boot_time_uncertainty_ns() <= 1_000_000_000);
    }

    #[test]
    fn test_clock_resolution_is_a_nonzero_uncertainty_floor() {
        assert_eq!(uncertainty_with_resolution_floor(0, 0), 1);
        assert_eq!(uncertainty_with_resolution_floor(0, 5), 5);
        assert_eq!(uncertainty_with_resolution_floor(3, 5), 5);
        assert_eq!(uncertainty_with_resolution_floor(7, 5), 7);
    }
}
