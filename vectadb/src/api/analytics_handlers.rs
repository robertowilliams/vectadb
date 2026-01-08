//! Analytics API handlers

use axum::{
    extract::{Query as AxumQuery, State},
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

use crate::analytics::{
    AggregatedMetric, Anomaly, MetricsAggregator, MetricsCollector, QueryAnalyzer, QueryStats,
    TimeWindow,
};
use crate::api::types::ErrorResponse;

/// Analytics state
#[derive(Clone)]
pub struct AnalyticsState {
    pub metrics: Arc<MetricsCollector>,
}

impl AnalyticsState {
    pub fn new() -> Self {
        Self {
            metrics: Arc::new(MetricsCollector::new()),
        }
    }
}

/// Query parameters for analytics
#[derive(Debug, Deserialize)]
pub struct AnalyticsQueryParams {
    pub window: Option<String>,
    pub metric: Option<String>,
}

/// Analytics summary response
#[derive(Debug, Serialize)]
pub struct AnalyticsSummary {
    pub query_stats: QueryStats,
    pub total_metrics: usize,
    pub available_metrics: Vec<String>,
}

/// Get analytics summary
pub async fn get_analytics_summary(
    State(state): State<AnalyticsState>,
) -> Result<Json<AnalyticsSummary>, (StatusCode, Json<ErrorResponse>)> {
    let query_stats = state.metrics.get_query_stats();

    let summary = AnalyticsSummary {
        query_stats,
        total_metrics: 0,
        available_metrics: vec![
            "query_duration".to_string(),
            "entity_count".to_string(),
            "relation_count".to_string(),
        ],
    };

    Ok(Json(summary))
}

/// Get query statistics
pub async fn get_query_stats(
    State(state): State<AnalyticsState>,
) -> Result<Json<QueryStats>, (StatusCode, Json<ErrorResponse>)> {
    let stats = state.metrics.get_query_stats();
    Ok(Json(stats))
}

/// Get aggregated metrics
pub async fn get_aggregated_metrics(
    State(state): State<AnalyticsState>,
    AxumQuery(params): AxumQuery<AnalyticsQueryParams>,
) -> Result<Json<Vec<AggregatedMetric>>, (StatusCode, Json<ErrorResponse>)> {
    let metric_name = params.metric.unwrap_or_else(|| "query_duration".to_string());
    let window = parse_time_window(params.window.as_deref())?;

    let points = state.metrics.get_metrics(&metric_name);
    let aggregated = MetricsAggregator::aggregate(&points, window);

    Ok(Json(aggregated))
}

/// Detect anomalies
pub async fn detect_anomalies(
    State(state): State<AnalyticsState>,
    AxumQuery(params): AxumQuery<AnalyticsQueryParams>,
) -> Result<Json<Vec<Anomaly>>, (StatusCode, Json<ErrorResponse>)> {
    use crate::analytics::AnomalyDetector;

    let metric_name = params.metric.unwrap_or_else(|| "query_duration".to_string());
    let points = state.metrics.get_metrics(&metric_name);

    let detector = AnomalyDetector::default();
    let anomalies = detector.detect(metric_name, &points);

    Ok(Json(anomalies))
}

fn parse_time_window(window: Option<&str>) -> Result<TimeWindow, (StatusCode, Json<ErrorResponse>)> {
    match window {
        Some("minute") => Ok(TimeWindow::Minute),
        Some("hour") => Ok(TimeWindow::Hour),
        Some("day") => Ok(TimeWindow::Day),
        Some("week") => Ok(TimeWindow::Week),
        None => Ok(TimeWindow::Hour),
        Some(other) => Err((
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse {
                error: format!("Invalid time window: {}", other),
            }),
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_time_window() {
        assert!(matches!(
            parse_time_window(Some("hour")).unwrap(),
            TimeWindow::Hour
        ));
        assert!(matches!(
            parse_time_window(Some("day")).unwrap(),
            TimeWindow::Day
        ));
        assert!(parse_time_window(Some("invalid")).is_err());
    }
}
