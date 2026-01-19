//! Query analysis and anomaly detection

use super::{Anomaly, AnomalySeverity, MetricPoint};
use serde::{Deserialize, Serialize};

/// Query analyzer
pub struct QueryAnalyzer;

impl QueryAnalyzer {
    /// Analyze query performance patterns
    pub fn analyze_performance(durations: &[f64]) -> PerformanceAnalysis {
        if durations.is_empty() {
            return PerformanceAnalysis::default();
        }

        let mean = durations.iter().sum::<f64>() / durations.len() as f64;
        let variance = durations
            .iter()
            .map(|x| (x - mean).powi(2))
            .sum::<f64>()
            / durations.len() as f64;
        let std_dev = variance.sqrt();

        let mut sorted = durations.to_vec();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());

        PerformanceAnalysis {
            mean,
            std_dev,
            min: *sorted.first().unwrap(),
            max: *sorted.last().unwrap(),
            median: sorted[sorted.len() / 2],
            sample_count: durations.len(),
        }
    }

    /// Detect slow queries
    pub fn detect_slow_queries(durations: &[f64], threshold_ms: f64) -> Vec<usize> {
        durations
            .iter()
            .enumerate()
            .filter(|(_, &d)| d > threshold_ms)
            .map(|(i, _)| i)
            .collect()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PerformanceAnalysis {
    pub mean: f64,
    pub std_dev: f64,
    pub min: f64,
    pub max: f64,
    pub median: f64,
    pub sample_count: usize,
}

/// Anomaly detector
pub struct AnomalyDetector {
    threshold: f64, // Standard deviations
}

impl AnomalyDetector {
    pub fn new(threshold: f64) -> Self {
        Self { threshold }
    }

    /// Detect anomalies using statistical methods
    pub fn detect(&self, metric_name: String, points: &[MetricPoint]) -> Vec<Anomaly> {
        if points.len() < 10 {
            return Vec::new(); // Need minimum data
        }

        let values: Vec<f64> = points.iter().map(|p| p.value).collect();
        let mean = values.iter().sum::<f64>() / values.len() as f64;
        let variance = values
            .iter()
            .map(|x| (x - mean).powi(2))
            .sum::<f64>()
            / values.len() as f64;
        let std_dev = variance.sqrt();

        let mut anomalies = Vec::new();

        for point in points {
            let z_score = (point.value - mean).abs() / std_dev;

            if z_score > self.threshold {
                let severity = if z_score > self.threshold * 2.0 {
                    AnomalySeverity::Critical
                } else if z_score > self.threshold * 1.5 {
                    AnomalySeverity::High
                } else if z_score > self.threshold * 1.2 {
                    AnomalySeverity::Medium
                } else {
                    AnomalySeverity::Low
                };

                anomalies.push(Anomaly {
                    timestamp: point.timestamp,
                    metric_name: metric_name.clone(),
                    expected_value: mean,
                    actual_value: point.value,
                    severity,
                    description: format!(
                        "Value {} deviates from expected {} by {:.2} standard deviations",
                        point.value, mean, z_score
                    ),
                });
            }
        }

        anomalies
    }

    /// Detect sudden spikes or drops
    pub fn detect_sudden_changes(&self, points: &[MetricPoint], change_threshold: f64) -> Vec<Anomaly> {
        if points.len() < 2 {
            return Vec::new();
        }

        let mut anomalies = Vec::new();

        for i in 1..points.len() {
            let prev = points[i - 1].value;
            let curr = points[i].value;

            if prev == 0.0 {
                continue;
            }

            let change_pct = ((curr - prev) / prev).abs() * 100.0;

            if change_pct > change_threshold {
                let severity = if change_pct > change_threshold * 2.0 {
                    AnomalySeverity::Critical
                } else if change_pct > change_threshold * 1.5 {
                    AnomalySeverity::High
                } else {
                    AnomalySeverity::Medium
                };

                anomalies.push(Anomaly {
                    timestamp: points[i].timestamp,
                    metric_name: "sudden_change".to_string(),
                    expected_value: prev,
                    actual_value: curr,
                    severity,
                    description: format!(
                        "Value changed by {:.1}% from {} to {}",
                        change_pct, prev, curr
                    ),
                });
            }
        }

        anomalies
    }
}

impl Default for AnomalyDetector {
    fn default() -> Self {
        Self::new(2.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_performance_analysis() {
        let durations = vec![100.0, 150.0, 120.0, 130.0, 140.0];
        let analysis = QueryAnalyzer::analyze_performance(&durations);

        assert_eq!(analysis.mean, 128.0);
        assert_eq!(analysis.min, 100.0);
        assert_eq!(analysis.max, 150.0);
        assert_eq!(analysis.sample_count, 5);
    }

    #[test]
    fn test_detect_slow_queries() {
        let durations = vec![50.0, 100.0, 200.0, 80.0, 300.0];
        let slow = QueryAnalyzer::detect_slow_queries(&durations, 150.0);

        assert_eq!(slow.len(), 2);
        assert!(slow.contains(&2));
        assert!(slow.contains(&4));
    }

    #[test]
    fn test_anomaly_detection() {
        let points: Vec<MetricPoint> = (0..20)
            .map(|i| MetricPoint {
                timestamp: i * 1000,
                value: if i == 15 { 1000.0 } else { 100.0 },
                labels: vec![],
            })
            .collect();

        let detector = AnomalyDetector::new(2.0);
        let anomalies = detector.detect("test_metric".to_string(), &points);

        assert!(!anomalies.is_empty());
    }
}
