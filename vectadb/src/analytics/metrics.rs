//! Metrics collection for VectaDB

use super::{MetricPoint, QueryStats};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// Metrics collector
#[derive(Clone)]
pub struct MetricsCollector {
    metrics: Arc<Mutex<HashMap<String, Vec<MetricPoint>>>>,
    query_durations: Arc<Mutex<Vec<f64>>>,
    query_errors: Arc<Mutex<u64>>,
    query_total: Arc<Mutex<u64>>,
}

impl MetricsCollector {
    pub fn new() -> Self {
        Self {
            metrics: Arc::new(Mutex::new(HashMap::new())),
            query_durations: Arc::new(Mutex::new(Vec::new())),
            query_errors: Arc::new(Mutex::new(0)),
            query_total: Arc::new(Mutex::new(0)),
        }
    }

    /// Record a metric value
    pub fn record(&self, name: impl Into<String>, value: f64, labels: Vec<(String, String)>) {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64;

        let point = MetricPoint {
            timestamp,
            value,
            labels,
        };

        let mut metrics = self.metrics.lock().unwrap();
        metrics
            .entry(name.into())
            .or_insert_with(Vec::new)
            .push(point);
    }

    /// Record query duration
    pub fn record_query(&self, duration: Duration, success: bool) {
        let duration_ms = duration.as_secs_f64() * 1000.0;

        {
            let mut durations = self.query_durations.lock().unwrap();
            durations.push(duration_ms);

            // Keep only last 10000 queries
            if durations.len() > 10000 {
                durations.drain(0..1000);
            }
        }

        {
            let mut total = self.query_total.lock().unwrap();
            *total += 1;
        }

        if !success {
            let mut errors = self.query_errors.lock().unwrap();
            *errors += 1;
        }
    }

    /// Get query statistics
    pub fn get_query_stats(&self) -> QueryStats {
        let durations = self.query_durations.lock().unwrap();
        let errors = *self.query_errors.lock().unwrap();
        let total = *self.query_total.lock().unwrap();

        if durations.is_empty() {
            return QueryStats {
                total_queries: total,
                avg_duration_ms: 0.0,
                p50_duration_ms: 0.0,
                p95_duration_ms: 0.0,
                p99_duration_ms: 0.0,
                error_rate: 0.0,
            };
        }

        let mut sorted = durations.clone();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());

        let avg = sorted.iter().sum::<f64>() / sorted.len() as f64;
        let p50 = percentile(&sorted, 50.0);
        let p95 = percentile(&sorted, 95.0);
        let p99 = percentile(&sorted, 99.0);
        let error_rate = if total > 0 {
            errors as f64 / total as f64
        } else {
            0.0
        };

        QueryStats {
            total_queries: total,
            avg_duration_ms: avg,
            p50_duration_ms: p50,
            p95_duration_ms: p95,
            p99_duration_ms: p99,
            error_rate,
        }
    }

    /// Get all metrics
    pub fn get_metrics(&self, name: &str) -> Vec<MetricPoint> {
        let metrics = self.metrics.lock().unwrap();
        metrics.get(name).cloned().unwrap_or_default()
    }

    /// Clear old metrics
    pub fn cleanup(&self, retention_secs: i64) {
        let cutoff = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64
            - retention_secs;

        let mut metrics = self.metrics.lock().unwrap();
        for points in metrics.values_mut() {
            points.retain(|p| p.timestamp > cutoff * 1000);
        }
    }
}

impl Default for MetricsCollector {
    fn default() -> Self {
        Self::new()
    }
}

fn percentile(sorted_data: &[f64], p: f64) -> f64 {
    if sorted_data.is_empty() {
        return 0.0;
    }
    let index = ((p / 100.0) * (sorted_data.len() - 1) as f64).round() as usize;
    sorted_data[index]
}

/// Query performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryMetrics {
    pub query_type: String,
    pub duration_ms: f64,
    pub entities_scanned: u64,
    pub results_returned: u64,
    pub success: bool,
}

/// Overall performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    pub timestamp: i64,
    pub queries_per_second: f64,
    pub avg_query_duration_ms: f64,
    pub cache_hit_rate: f64,
    pub active_connections: u32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metrics_collector() {
        let collector = MetricsCollector::new();

        collector.record("test_metric", 42.0, vec![]);
        let metrics = collector.get_metrics("test_metric");
        assert_eq!(metrics.len(), 1);
        assert_eq!(metrics[0].value, 42.0);
    }

    #[test]
    fn test_query_stats() {
        let collector = MetricsCollector::new();

        collector.record_query(Duration::from_millis(100), true);
        collector.record_query(Duration::from_millis(200), true);
        collector.record_query(Duration::from_millis(150), false);

        let stats = collector.get_query_stats();
        assert_eq!(stats.total_queries, 3);
        assert!(stats.avg_duration_ms > 0.0);
        assert!(stats.error_rate > 0.0);
    }

    #[test]
    fn test_percentile() {
        let data = vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0];
        // P50 of [1..10] is 5.5, rounds to 6
        assert_eq!(percentile(&data, 50.0), 6.0);
        // P95 of [1..10] is 9.5, rounds to 10
        assert_eq!(percentile(&data, 95.0), 10.0);
    }
}
