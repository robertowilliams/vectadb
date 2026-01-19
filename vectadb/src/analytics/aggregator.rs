//! Metrics aggregation

use super::MetricPoint;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Time window for aggregation
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum TimeWindow {
    Minute,
    Hour,
    Day,
    Week,
}

impl TimeWindow {
    pub fn duration_ms(&self) -> i64 {
        match self {
            TimeWindow::Minute => 60 * 1000,
            TimeWindow::Hour => 60 * 60 * 1000,
            TimeWindow::Day => 24 * 60 * 60 * 1000,
            TimeWindow::Week => 7 * 24 * 60 * 60 * 1000,
        }
    }
}

/// Aggregated metric value
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AggregatedMetric {
    pub window_start: i64,
    pub window_end: i64,
    pub min: f64,
    pub max: f64,
    pub avg: f64,
    pub sum: f64,
    pub count: u64,
}

/// Metrics aggregator
pub struct MetricsAggregator;

impl MetricsAggregator {
    /// Aggregate metrics by time window
    pub fn aggregate(points: &[MetricPoint], window: TimeWindow) -> Vec<AggregatedMetric> {
        if points.is_empty() {
            return Vec::new();
        }

        let window_ms = window.duration_ms();
        let mut buckets: HashMap<i64, Vec<f64>> = HashMap::new();

        // Group points into time buckets
        for point in points {
            let bucket = (point.timestamp / window_ms) * window_ms;
            buckets.entry(bucket).or_default().push(point.value);
        }

        // Calculate statistics for each bucket
        let mut results: Vec<_> = buckets
            .into_iter()
            .map(|(bucket, values)| {
                let min = values.iter().copied().fold(f64::INFINITY, f64::min);
                let max = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                let sum: f64 = values.iter().sum();
                let count = values.len() as u64;
                let avg = sum / count as f64;

                AggregatedMetric {
                    window_start: bucket,
                    window_end: bucket + window_ms,
                    min,
                    max,
                    avg,
                    sum,
                    count,
                }
            })
            .collect();

        results.sort_by_key(|m| m.window_start);
        results
    }

    /// Calculate moving average
    pub fn moving_average(points: &[MetricPoint], window_size: usize) -> Vec<MetricPoint> {
        if points.is_empty() || window_size == 0 || window_size > points.len() {
            return Vec::new();
        }

        let mut result = Vec::new();
        for i in (window_size - 1)..points.len() {
            let start = i.saturating_sub(window_size - 1);
            let window = &points[start..=i];
            let avg = window.iter().map(|p| p.value).sum::<f64>() / window_size as f64;

            result.push(MetricPoint {
                timestamp: points[i].timestamp,
                value: avg,
                labels: points[i].labels.clone(),
            });
        }

        result
    }

    /// Calculate rate of change
    pub fn rate_of_change(points: &[MetricPoint]) -> Vec<MetricPoint> {
        if points.len() < 2 {
            return Vec::new();
        }

        let mut result = Vec::new();
        for i in 1..points.len() {
            let time_diff = (points[i].timestamp - points[i - 1].timestamp) as f64 / 1000.0; // seconds
            if time_diff > 0.0 {
                let value_diff = points[i].value - points[i - 1].value;
                let rate = value_diff / time_diff;

                result.push(MetricPoint {
                    timestamp: points[i].timestamp,
                    value: rate,
                    labels: points[i].labels.clone(),
                });
            }
        }

        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_aggregate() {
        let points = vec![
            MetricPoint {
                timestamp: 1000,
                value: 10.0,
                labels: vec![],
            },
            MetricPoint {
                timestamp: 2000,
                value: 20.0,
                labels: vec![],
            },
            MetricPoint {
                timestamp: 61000,
                value: 30.0,
                labels: vec![],
            },
        ];

        let aggregated = MetricsAggregator::aggregate(&points, TimeWindow::Minute);
        assert_eq!(aggregated.len(), 2);
        assert_eq!(aggregated[0].avg, 15.0);
    }

    #[test]
    fn test_moving_average() {
        let points = vec![
            MetricPoint {
                timestamp: 1000,
                value: 10.0,
                labels: vec![],
            },
            MetricPoint {
                timestamp: 2000,
                value: 20.0,
                labels: vec![],
            },
            MetricPoint {
                timestamp: 3000,
                value: 30.0,
                labels: vec![],
            },
        ];

        let ma = MetricsAggregator::moving_average(&points, 2);
        assert_eq!(ma.len(), 2);
        assert_eq!(ma[0].value, 15.0);
        assert_eq!(ma[1].value, 25.0);
    }
}
