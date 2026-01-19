// CloudWatch Logs client for fetching log events

use anyhow::{Context, Result};
use aws_sdk_cloudwatchlogs::{
    types::{FilteredLogEvent, OutputLogEvent},
    Client as CWClient,
};
use chrono::{DateTime, Utc};
use tracing::{debug, info, warn};

/// CloudWatch Logs client wrapper
pub struct CloudWatchClient {
    client: CWClient,
}

/// Log event from CloudWatch
#[derive(Debug, Clone)]
pub struct LogEvent {
    /// Log group name
    pub log_group: String,
    /// Log stream name
    pub log_stream: String,
    /// Event ID (unique identifier from CloudWatch)
    pub event_id: String,
    /// Event message (the actual log line)
    pub message: String,
    /// Event timestamp (milliseconds since epoch)
    pub timestamp: i64,
}

impl CloudWatchClient {
    /// Create a new CloudWatch client
    pub async fn new(region: &str) -> Result<Self> {
        info!("Initializing CloudWatch client for region: {}", region);

        let config = aws_config::defaults(aws_config::BehaviorVersion::latest())
            .region(aws_sdk_cloudwatchlogs::config::Region::new(region.to_string()))
            .load()
            .await;

        let client = CWClient::new(&config);

        Ok(Self { client })
    }

    /// Create CloudWatch client with custom AWS config
    pub fn with_config(config: &aws_config::SdkConfig) -> Self {
        let client = CWClient::new(config);
        Self { client }
    }

    /// Fetch log events from a log group using filter pattern
    /// Returns events from all log streams in the group
    pub async fn fetch_log_events(
        &self,
        log_group: &str,
        start_time: i64,
        end_time: i64,
        filter_pattern: Option<&str>,
        limit: Option<i32>,
    ) -> Result<Vec<LogEvent>> {
        debug!(
            "Fetching logs from group: {} (start: {}, end: {}, filter: {:?})",
            log_group, start_time, end_time, filter_pattern
        );

        let mut request = self
            .client
            .filter_log_events()
            .log_group_name(log_group)
            .start_time(start_time)
            .end_time(end_time);

        if let Some(pattern) = filter_pattern {
            request = request.filter_pattern(pattern);
        }

        if let Some(lim) = limit {
            request = request.limit(lim);
        }

        let mut events = Vec::new();
        let mut next_token: Option<String> = None;

        // Handle pagination
        loop {
            let mut req = request.clone();

            if let Some(token) = next_token {
                req = req.next_token(token);
            }

            let response = req
                .send()
                .await
                .context("Failed to fetch log events from CloudWatch")?;

            if let Some(log_events) = response.events {
                for event in log_events {
                    if let Some(log_event) = Self::convert_filtered_event(log_group, event) {
                        events.push(log_event);
                    }
                }
            }

            // Check for more pages
            next_token = response.next_token;
            if next_token.is_none() {
                break;
            }

            // Safety limit: don't fetch more than 10,000 events in one call
            if events.len() >= 10_000 {
                warn!(
                    "Reached safety limit of 10,000 events for log group: {}",
                    log_group
                );
                break;
            }
        }

        info!(
            "Fetched {} events from log group: {}",
            events.len(),
            log_group
        );

        Ok(events)
    }

    /// Fetch log events from a specific log stream
    pub async fn fetch_from_stream(
        &self,
        log_group: &str,
        log_stream: &str,
        start_time: i64,
        end_time: i64,
        limit: Option<i32>,
    ) -> Result<Vec<LogEvent>> {
        debug!(
            "Fetching logs from stream: {}/{}",
            log_group, log_stream
        );

        let mut request = self
            .client
            .get_log_events()
            .log_group_name(log_group)
            .log_stream_name(log_stream)
            .start_time(start_time)
            .end_time(end_time)
            .start_from_head(true); // Read from oldest to newest

        if let Some(lim) = limit {
            request = request.limit(lim);
        }

        let response = request
            .send()
            .await
            .context("Failed to fetch log events from stream")?;

        let mut events = Vec::new();

        if let Some(log_events) = response.events {
            for event in log_events {
                if let Some(log_event) = Self::convert_output_event(log_group, log_stream, event) {
                    events.push(log_event);
                }
            }
        }

        debug!(
            "Fetched {} events from stream: {}/{}",
            events.len(),
            log_group,
            log_stream
        );

        Ok(events)
    }

    /// List all log streams in a log group
    pub async fn list_log_streams(&self, log_group: &str) -> Result<Vec<String>> {
        debug!("Listing log streams in group: {}", log_group);

        let response = self
            .client
            .describe_log_streams()
            .log_group_name(log_group)
            .order_by(aws_sdk_cloudwatchlogs::types::OrderBy::LastEventTime)
            .descending(true)
            .send()
            .await
            .context("Failed to list log streams")?;

        let streams = response
            .log_streams
            .unwrap_or_default()
            .into_iter()
            .filter_map(|s| s.log_stream_name)
            .collect();

        Ok(streams)
    }

    /// Convert FilteredLogEvent to LogEvent
    fn convert_filtered_event(log_group: &str, event: FilteredLogEvent) -> Option<LogEvent> {
        Some(LogEvent {
            log_group: log_group.to_string(),
            log_stream: event.log_stream_name.unwrap_or_default(),
            event_id: event.event_id.unwrap_or_default(),
            message: event.message.unwrap_or_default(),
            timestamp: event.timestamp.unwrap_or(0),
        })
    }

    /// Convert OutputLogEvent to LogEvent
    fn convert_output_event(
        log_group: &str,
        log_stream: &str,
        event: OutputLogEvent,
    ) -> Option<LogEvent> {
        Some(LogEvent {
            log_group: log_group.to_string(),
            log_stream: log_stream.to_string(),
            event_id: format!("{}", event.timestamp.unwrap_or(0)),
            message: event.message.unwrap_or_default(),
            timestamp: event.timestamp.unwrap_or(0),
        })
    }
}

impl LogEvent {
    /// Convert CloudWatch timestamp (milliseconds) to DateTime<Utc>
    pub fn to_datetime(&self) -> DateTime<Utc> {
        DateTime::from_timestamp_millis(self.timestamp).unwrap_or_else(Utc::now)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_log_event_timestamp_conversion() {
        let event = LogEvent {
            log_group: "/test".to_string(),
            log_stream: "stream-1".to_string(),
            event_id: "1".to_string(),
            message: "test message".to_string(),
            timestamp: 1700000000000, // Nov 14, 2023
        };

        let dt = event.to_datetime();
        assert!(dt.timestamp() > 0);
    }
}
