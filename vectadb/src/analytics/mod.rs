//! Analytics module for VectaDB
//!
//! Provides performance metrics, query analysis, and anomaly detection.

pub mod metrics;
pub mod aggregator;
pub mod analyzer;

pub use metrics::{MetricsCollector, QueryMetrics, PerformanceMetrics};
pub use aggregator::{MetricsAggregator, TimeWindow};
pub use analyzer::{QueryAnalyzer, AnomalyDetector};

use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Analytics configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalyticsConfig {
    /// Enable metrics collection
    pub enabled: bool,

    /// Metrics retention period
    pub retention_days: u32,

    /// Sampling rate (0.0 to 1.0)
    pub sampling_rate: f64,

    /// Anomaly detection threshold
    pub anomaly_threshold: f64,
}

impl Default for AnalyticsConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            retention_days: 30,
            sampling_rate: 1.0,
            anomaly_threshold: 2.0, // 2 standard deviations
        }
    }
}

/// Metric data point
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricPoint {
    pub timestamp: i64,
    pub value: f64,
    pub labels: Vec<(String, String)>,
}

/// Query performance statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryStats {
    pub total_queries: u64,
    pub avg_duration_ms: f64,
    pub p50_duration_ms: f64,
    pub p95_duration_ms: f64,
    pub p99_duration_ms: f64,
    pub error_rate: f64,
}

/// System health metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthMetrics {
    pub timestamp: i64,
    pub cpu_usage_percent: f64,
    pub memory_usage_mb: f64,
    pub active_connections: u32,
    pub queries_per_second: f64,
}

/// Anomaly detection result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Anomaly {
    pub timestamp: i64,
    pub metric_name: String,
    pub expected_value: f64,
    pub actual_value: f64,
    pub severity: AnomalySeverity,
    pub description: String,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum AnomalySeverity {
    Low,
    Medium,
    High,
    Critical,
}
