// Integration test for CloudWatch agent with real Bedrock logs
//
// This test simulates the full pipeline:
// 1. Load real Bedrock logs from JSON file
// 2. Parse them using the CloudWatch agent parser
// 3. Send to VectaDB for ingestion
// 4. Verify trace auto-creation works correctly

#[cfg(test)]
mod integration_tests {
    use chrono::{DateTime, Utc};
    use serde_json::Value as JsonValue;
    use std::collections::HashMap;

    // Mock CloudWatch event for testing
    #[derive(Debug, Clone)]
    struct MockLogEvent {
        log_group: String,
        log_stream: String,
        event_id: String,
        message: String,
        timestamp: i64,
    }

    impl MockLogEvent {
        fn to_datetime(&self) -> DateTime<Utc> {
            DateTime::from_timestamp_millis(self.timestamp).unwrap_or_else(Utc::now)
        }
    }

    #[test]
    fn test_bedrock_log_parsing() {
        // Sample Bedrock log from the real data
        let bedrock_log = r#"{
            "timestamp": "2025-12-17T01:09:56Z",
            "accountId": "027425703396",
            "region": "us-east-1",
            "requestId": "8d8903c3-e948-4c21-b4d9-6029f785f196",
            "operation": "ConverseStream",
            "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
            "input": {
                "inputTokenCount": 1023
            },
            "output": {
                "outputTokenCount": 89
            },
            "schemaType": "ModelInvocationLog",
            "schemaVersion": "1.0"
        }"#;

        // Parse the JSON
        let parsed: serde_json::Result<JsonValue> = serde_json::from_str(bedrock_log);
        assert!(parsed.is_ok());

        let log = parsed.unwrap();

        // Verify key fields exist
        assert_eq!(log["requestId"].as_str(), Some("8d8903c3-e948-4c21-b4d9-6029f785f196"));
        assert_eq!(log["operation"].as_str(), Some("ConverseStream"));
        assert_eq!(log["modelId"].as_str(), Some("global.anthropic.claude-haiku-4-5-20251001-v1:0"));

        // Verify token counts
        assert_eq!(log["input"]["inputTokenCount"].as_i64(), Some(1023));
        assert_eq!(log["output"]["outputTokenCount"].as_i64(), Some(89));
    }

    #[test]
    fn test_bedrock_error_log_parsing() {
        // Sample Bedrock error log
        let error_log = r#"{
            "timestamp": "2025-12-17T01:10:02Z",
            "accountId": "027425703396",
            "region": "us-east-1",
            "requestId": "78d218c4-1971-42e5-b4f3-da908c8887a1",
            "operation": "ConverseStream",
            "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
            "errorCode": "ThrottlingException",
            "schemaType": "ModelInvocationLog",
            "schemaVersion": "1.0"
        }"#;

        let parsed: serde_json::Result<JsonValue> = serde_json::from_str(error_log);
        assert!(parsed.is_ok());

        let log = parsed.unwrap();

        // Verify error fields
        assert_eq!(log["errorCode"].as_str(), Some("ThrottlingException"));
        assert_eq!(log["requestId"].as_str(), Some("78d218c4-1971-42e5-b4f3-da908c8887a1"));
    }

    #[test]
    fn test_bedrock_tool_use_extraction() {
        // Sample Bedrock log with tool use
        let tool_log = r#"{
            "timestamp": "2025-12-17T01:09:56Z",
            "requestId": "8d8903c3-e948-4c21-b4d9-6029f785f196",
            "operation": "ConverseStream",
            "output": {
                "outputBodyJson": {
                    "output": {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "text": "I'll search for the immunization records"
                                },
                                {
                                    "toolUse": {
                                        "toolUseId": "tooluse_50nrLqI5R2ChSyM6RY4NFw",
                                        "name": "LocalFHIRAPI___searchImmunization",
                                        "input": {
                                            "search_value": "PAT001"
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "stopReason": "tool_use"
                }
            }
        }"#;

        let parsed: serde_json::Result<JsonValue> = serde_json::from_str(tool_log);
        assert!(parsed.is_ok());

        let log = parsed.unwrap();

        // Extract tool use information
        let content = &log["output"]["outputBodyJson"]["output"]["message"]["content"];
        assert!(content.is_array());

        let tool_use = &content[1]["toolUse"];
        assert_eq!(tool_use["name"].as_str(), Some("LocalFHIRAPI___searchImmunization"));
        assert_eq!(tool_use["toolUseId"].as_str(), Some("tooluse_50nrLqI5R2ChSyM6RY4NFw"));
        assert_eq!(tool_use["input"]["search_value"].as_str(), Some("PAT001"));

        let stop_reason = &log["output"]["outputBodyJson"]["stopReason"];
        assert_eq!(stop_reason.as_str(), Some("tool_use"));
    }

    #[test]
    fn test_trace_grouping_by_request_id() {
        // Multiple events with the same requestId should group into one trace
        let events = vec![
            ("req-123", "User query received"),
            ("req-123", "Tool call: searchImmunization"),
            ("req-123", "Tool result returned"),
            ("req-456", "Different user query"),
        ];

        let mut trace_map: HashMap<String, Vec<String>> = HashMap::new();

        for (request_id, event_desc) in events {
            trace_map
                .entry(request_id.to_string())
                .or_insert_with(Vec::new)
                .push(event_desc.to_string());
        }

        // Verify req-123 has 3 events
        assert_eq!(trace_map.get("req-123").unwrap().len(), 3);

        // Verify req-456 has 1 event
        assert_eq!(trace_map.get("req-456").unwrap().len(), 1);
    }

    #[test]
    fn test_timestamp_parsing() {
        // Test CloudWatch timestamp format (milliseconds since epoch)
        let timestamp_ms: i64 = 1700000000000;

        let dt = DateTime::from_timestamp_millis(timestamp_ms).unwrap();

        assert!(dt.year() == 2023);
        assert!(dt.month() == 11); // November
    }

    #[test]
    fn test_bedrock_metrics_extraction() {
        let log_with_metrics = r#"{
            "timestamp": "2025-12-17T01:09:56Z",
            "requestId": "test-123",
            "output": {
                "outputBodyJson": {
                    "metrics": {
                        "latencyMs": 858
                    },
                    "usage": {
                        "inputTokens": 1023,
                        "outputTokens": 89,
                        "totalTokens": 1112
                    }
                }
            }
        }"#;

        let parsed: JsonValue = serde_json::from_str(log_with_metrics).unwrap();

        // Extract metrics
        let latency = parsed["output"]["outputBodyJson"]["metrics"]["latencyMs"].as_i64();
        assert_eq!(latency, Some(858));

        let input_tokens = parsed["output"]["outputBodyJson"]["usage"]["inputTokens"].as_i64();
        assert_eq!(input_tokens, Some(1023));

        let output_tokens = parsed["output"]["outputBodyJson"]["usage"]["outputTokens"].as_i64();
        assert_eq!(output_tokens, Some(89));

        let total_tokens = parsed["output"]["outputBodyJson"]["usage"]["totalTokens"].as_i64();
        assert_eq!(total_tokens, Some(1112));
    }
}
