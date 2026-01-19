// Log parser for extracting structured data from CloudWatch logs

use regex::Regex;
use serde_json::Value as JsonValue;
use tracing::debug;

use crate::cloudwatch_client::LogEvent;
use crate::config::{LogGroupConfig, ParserRule, ParserType};
use crate::vectadb_client::EventIngestionRequest;

/// Log parser with built-in patterns for LangChain, LlamaIndex, etc.
pub struct LogParser {
    /// Built-in regex patterns
    built_in_patterns: BuiltInPatterns,
}

/// Built-in parser patterns for common frameworks
struct BuiltInPatterns {
    // LangChain patterns
    langchain_tool: Regex,
    langchain_chain: Regex,
    langchain_agent: Regex,

    // LlamaIndex patterns
    llamaindex_query: Regex,
    llamaindex_retrieve: Regex,

    // Generic patterns
    generic_error: Regex,

    // ID extraction patterns (for resilient trace detection)
    request_id: Regex,
    session_id: Regex,
    agent_id: Regex,
}

impl BuiltInPatterns {
    fn new() -> Self {
        Self {
            // LangChain tool calls
            langchain_tool: Regex::new(
                r"(?i)(?:Entering new|Finished|Running) (?P<tool_name>\w+)(?: tool)?.*?(?:input[:\s]+)?(?P<input>\{.*?\}|[^\n]+)"
            ).unwrap(),

            // LangChain chain execution
            langchain_chain: Regex::new(
                r"(?i)(?:Entering new|Finished) (?P<chain_type>\w+) chain.*?(?:with input[:\s]+)?(?P<input>.*)"
            ).unwrap(),

            // LangChain agent actions
            langchain_agent: Regex::new(
                r"(?i)Agent (?P<action>Action|Finished).*?(?:tool[:\s]+)?(?P<tool>\w+)?.*?(?:input[:\s]+)?(?P<input>.*)"
            ).unwrap(),

            // LlamaIndex query operations
            llamaindex_query: Regex::new(
                r"(?i)query[:\s]+(?P<query_text>[^\n]+).*?(?:response[:\s]+)?(?P<response>.*)"
            ).unwrap(),

            // LlamaIndex retrieval operations
            llamaindex_retrieve: Regex::new(
                r"(?i)retrieve.*?(?:query[:\s]+)?(?P<query>[^\n]+).*?(?:nodes[:\s]+)?(?P<node_count>\d+)"
            ).unwrap(),

            // Generic error pattern
            generic_error: Regex::new(
                r"(?i)(?P<level>ERROR|FATAL|EXCEPTION).*?(?P<message>.*?)(?:at|in|from)?\s*(?P<location>.*)"
            ).unwrap(),

            // ID extraction patterns with multiple fallbacks
            request_id: Regex::new(
                r"(?i)(?:request[-_]?id|req[-_]?id|trace[-_]?id)[:\s]+(?P<id>[a-zA-Z0-9\-]+)"
            ).unwrap(),

            session_id: Regex::new(
                r"(?i)(?:session[-_]?id|sess[-_]?id)[:\s]+(?P<id>[a-zA-Z0-9\-]+)"
            ).unwrap(),

            agent_id: Regex::new(
                r"(?i)(?:agent[-_]?id|agent[-_]?name)[:\s]+(?P<id>[a-zA-Z0-9\-]+)"
            ).unwrap(),
        }
    }

    /// Try to extract request/session ID from log message
    fn extract_request_id(&self, message: &str) -> Option<String> {
        self.request_id
            .captures(message)
            .and_then(|caps| caps.name("id"))
            .map(|m| m.as_str().to_string())
    }

    fn extract_session_id(&self, message: &str) -> Option<String> {
        self.session_id
            .captures(message)
            .and_then(|caps| caps.name("id"))
            .map(|m| m.as_str().to_string())
    }

    fn extract_agent_id(&self, message: &str) -> Option<String> {
        self.agent_id
            .captures(message)
            .and_then(|caps| caps.name("id"))
            .map(|m| m.as_str().to_string())
    }
}

impl LogParser {
    /// Create a new log parser
    pub fn new() -> Self {
        Self {
            built_in_patterns: BuiltInPatterns::new(),
        }
    }

    /// Parse log event using configured parsers
    pub fn parse(
        &self,
        event: &LogEvent,
        config: &LogGroupConfig,
    ) -> EventIngestionRequest {
        // Sort parsers by priority (lower number = higher priority)
        let mut sorted_parsers = config.parsers.clone();
        sorted_parsers.sort_by_key(|p| p.priority);

        // Try each parser in order
        for parser in &sorted_parsers {
            if let Some(parsed_event) = self.try_parse(event, parser, config) {
                debug!(
                    "Parsed event using parser: {} (type: {:?})",
                    parser.name, parser.parser_type
                );
                return parsed_event;
            }
        }

        // No parser matched - create fallback event
        debug!("No parser matched, creating fallback event");
        self.create_fallback_event(event, config)
    }

    /// Try to parse event with a specific parser rule
    fn try_parse(
        &self,
        event: &LogEvent,
        parser: &ParserRule,
        config: &LogGroupConfig,
    ) -> Option<EventIngestionRequest> {
        match parser.parser_type {
            ParserType::Json => self.try_parse_json(event, parser, config),
            ParserType::Regex => self.try_parse_regex(event, parser, config),
            ParserType::LangChain => self.try_parse_langchain(event, parser, config),
            ParserType::LlamaIndex => self.try_parse_llamaindex(event, parser, config),
        }
    }

    /// Try to parse as JSON
    fn try_parse_json(
        &self,
        event: &LogEvent,
        parser: &ParserRule,
        config: &LogGroupConfig,
    ) -> Option<EventIngestionRequest> {
        match serde_json::from_str::<JsonValue>(&event.message) {
            Ok(json) => {
                let mut properties = if let JsonValue::Object(map) = json {
                    JsonValue::Object(map)
                } else {
                    serde_json::json!({"message": json})
                };

                // Apply field mappings if specified
                if !parser.field_mapping.is_empty() {
                    if let Some(obj) = properties.as_object_mut() {
                        let mut mapped = serde_json::Map::new();
                        for (source_key, target_key) in &parser.field_mapping {
                            if let Some(value) = obj.get(source_key) {
                                mapped.insert(target_key.clone(), value.clone());
                            }
                        }
                        for (k, v) in mapped {
                            obj.insert(k, v);
                        }
                    }
                }

                Some(self.build_event(event, config, properties, parser.event_type.as_deref()))
            }
            Err(_) => None,
        }
    }

    /// Try to parse with regex pattern
    fn try_parse_regex(
        &self,
        event: &LogEvent,
        parser: &ParserRule,
        config: &LogGroupConfig,
    ) -> Option<EventIngestionRequest> {
        let pattern = parser.pattern.as_ref()?;
        let regex = Regex::new(pattern).ok()?;

        let captures = regex.captures(&event.message)?;

        let properties = self.build_event_from_captures(&captures, parser);

        Some(self.build_event(event, config, properties, parser.event_type.as_deref()))
    }

    /// Try to parse with built-in LangChain patterns
    fn try_parse_langchain(
        &self,
        event: &LogEvent,
        _parser: &ParserRule,
        config: &LogGroupConfig,
    ) -> Option<EventIngestionRequest> {
        // Try tool pattern first
        if let Some(caps) = self.built_in_patterns.langchain_tool.captures(&event.message) {
            let mut properties = serde_json::Map::new();
            properties.insert("framework".to_string(), serde_json::json!("langchain"));

            if let Some(tool_name) = caps.name("tool_name") {
                properties.insert("tool_name".to_string(), serde_json::json!(tool_name.as_str()));
            }
            if let Some(input) = caps.name("input") {
                properties.insert("input".to_string(), serde_json::json!(input.as_str()));
            }

            return Some(self.build_event(
                event,
                config,
                JsonValue::Object(properties),
                Some("tool_call"),
            ));
        }

        // Try chain pattern
        if let Some(caps) = self.built_in_patterns.langchain_chain.captures(&event.message) {
            let mut properties = serde_json::Map::new();
            properties.insert("framework".to_string(), serde_json::json!("langchain"));

            if let Some(chain_type) = caps.name("chain_type") {
                properties.insert("chain_type".to_string(), serde_json::json!(chain_type.as_str()));
            }
            if let Some(input) = caps.name("input") {
                properties.insert("input".to_string(), serde_json::json!(input.as_str()));
            }

            return Some(self.build_event(
                event,
                config,
                JsonValue::Object(properties),
                Some("chain_execution"),
            ));
        }

        // Try agent pattern
        if let Some(caps) = self.built_in_patterns.langchain_agent.captures(&event.message) {
            let mut properties = serde_json::Map::new();
            properties.insert("framework".to_string(), serde_json::json!("langchain"));

            if let Some(action) = caps.name("action") {
                properties.insert("action".to_string(), serde_json::json!(action.as_str()));
            }
            if let Some(tool) = caps.name("tool") {
                properties.insert("tool".to_string(), serde_json::json!(tool.as_str()));
            }
            if let Some(input) = caps.name("input") {
                properties.insert("input".to_string(), serde_json::json!(input.as_str()));
            }

            return Some(self.build_event(
                event,
                config,
                JsonValue::Object(properties),
                Some("agent_action"),
            ));
        }

        None
    }

    /// Try to parse with built-in LlamaIndex patterns
    fn try_parse_llamaindex(
        &self,
        event: &LogEvent,
        _parser: &ParserRule,
        config: &LogGroupConfig,
    ) -> Option<EventIngestionRequest> {
        // Try query pattern
        if let Some(caps) = self.built_in_patterns.llamaindex_query.captures(&event.message) {
            let mut properties = serde_json::Map::new();
            properties.insert("framework".to_string(), serde_json::json!("llamaindex"));

            if let Some(query) = caps.name("query_text") {
                properties.insert("query".to_string(), serde_json::json!(query.as_str()));
            }
            if let Some(response) = caps.name("response") {
                properties.insert("response".to_string(), serde_json::json!(response.as_str()));
            }

            return Some(self.build_event(
                event,
                config,
                JsonValue::Object(properties),
                Some("query"),
            ));
        }

        // Try retrieve pattern
        if let Some(caps) = self.built_in_patterns.llamaindex_retrieve.captures(&event.message) {
            let mut properties = serde_json::Map::new();
            properties.insert("framework".to_string(), serde_json::json!("llamaindex"));

            if let Some(query) = caps.name("query") {
                properties.insert("query".to_string(), serde_json::json!(query.as_str()));
            }
            if let Some(node_count) = caps.name("node_count") {
                if let Ok(count) = node_count.as_str().parse::<u32>() {
                    properties.insert("node_count".to_string(), serde_json::json!(count));
                }
            }

            return Some(self.build_event(
                event,
                config,
                JsonValue::Object(properties),
                Some("retrieval"),
            ));
        }

        None
    }

    /// Build event properties from regex captures
    fn build_event_from_captures(
        &self,
        captures: &regex::Captures,
        parser: &ParserRule,
    ) -> JsonValue {
        let mut properties = serde_json::Map::new();

        // Extract all named capture groups
        for (name, _) in captures.iter().skip(1).enumerate() {
            if let Some(matched) = captures.name(&name.to_string()) {
                properties.insert(name.to_string(), serde_json::json!(matched.as_str()));
            }
        }

        // Apply field mappings
        if !parser.field_mapping.is_empty() {
            let mut mapped = serde_json::Map::new();
            for (source_key, target_key) in &parser.field_mapping {
                if let Some(value) = properties.get(source_key) {
                    mapped.insert(target_key.clone(), value.clone());
                }
            }
            for (k, v) in mapped {
                properties.insert(k, v);
            }
        }

        JsonValue::Object(properties)
    }

    /// Create fallback event when no parser matches
    fn create_fallback_event(
        &self,
        event: &LogEvent,
        config: &LogGroupConfig,
    ) -> EventIngestionRequest {
        let properties = serde_json::json!({
            "message": event.message,
            "raw_log": true,
        });

        self.build_event(event, config, properties, None)
    }

    /// Build final EventIngestionRequest with ID extraction
    fn build_event(
        &self,
        event: &LogEvent,
        config: &LogGroupConfig,
        properties: JsonValue,
        event_type: Option<&str>,
    ) -> EventIngestionRequest {
        // Extract IDs using resilient patterns
        let session_id = self.built_in_patterns.extract_session_id(&event.message)
            .or_else(|| self.built_in_patterns.extract_request_id(&event.message));

        let agent_id = config.agent_id.clone()
            .or_else(|| self.built_in_patterns.extract_agent_id(&event.message));

        EventIngestionRequest {
            trace_id: None,
            timestamp: event.to_datetime(),
            event_type: event_type.map(String::from),
            agent_id,
            session_id,
            properties,
            source: Some(crate::vectadb_client::LogSource {
                system: "cloudwatch".to_string(),
                log_group: event.log_group.clone(),
                log_stream: event.log_stream.clone(),
                log_id: event.event_id.clone(),
            }),
        }
    }
}

impl Default for LogParser {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn test_json_parsing() {
        let parser = LogParser::new();
        let event = LogEvent {
            log_group: "/test".to_string(),
            log_stream: "stream-1".to_string(),
            event_id: "1".to_string(),
            message: r#"{"level":"INFO","message":"test","request_id":"req-123"}"#.to_string(),
            timestamp: 1700000000000,
        };

        let config = LogGroupConfig {
            name: "/test".to_string(),
            agent_id: None,
            parsers: vec![ParserRule {
                name: "json".to_string(),
                parser_type: ParserType::Json,
                pattern: None,
                field_mapping: HashMap::new(),
                event_type: Some("test".to_string()),
                priority: 10,
            }],
            filter_pattern: None,
        };

        let parsed = parser.parse(&event, &config);
        assert_eq!(parsed.event_type, Some("test".to_string()));
        assert_eq!(parsed.session_id, Some("req-123".to_string()));
    }

    #[test]
    fn test_langchain_pattern() {
        let parser = LogParser::new();
        let event = LogEvent {
            log_group: "/test".to_string(),
            log_stream: "stream-1".to_string(),
            event_id: "1".to_string(),
            message: "Running WebSearch tool with input: weather forecast".to_string(),
            timestamp: 1700000000000,
        };

        let config = LogGroupConfig {
            name: "/test".to_string(),
            agent_id: Some("langchain-agent".to_string()),
            parsers: vec![ParserRule {
                name: "langchain".to_string(),
                parser_type: ParserType::LangChain,
                pattern: None,
                field_mapping: HashMap::new(),
                event_type: None,
                priority: 10,
            }],
            filter_pattern: None,
        };

        let parsed = parser.parse(&event, &config);
        assert_eq!(parsed.event_type, Some("tool_call".to_string()));
        assert_eq!(parsed.agent_id, Some("langchain-agent".to_string()));
    }
}
