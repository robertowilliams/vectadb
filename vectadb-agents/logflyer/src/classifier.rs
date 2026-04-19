// LLMClassifier — sends batches of log lines to an OpenAI-compatible server
// and parses the response to identify agentic / LLM activity.
//
// Fallback: if the LLM call fails or returns unparseable JSON, each line is
// run through a deterministic pattern matcher so the poll loop never stalls.

use anyhow::{anyhow, Context, Result};
use regex::Regex;
use reqwest::Client;
use serde_json::{json, Value as JsonValue};
use std::collections::HashMap;
use std::time::Duration;
use tracing::{debug, warn};

use crate::config::LLMConfig;
use crate::models::{ClassificationSource, ClassifiedEvent, EventType, LogLine};

// ────────────────────────────────────────────────────────────────────────────
// System prompt
// ────────────────────────────────────────────────────────────────────────────

const SYSTEM_PROMPT: &str = r#"You are an expert at analyzing logs from AI agent and LLM systems.

Given a numbered list of log lines, identify which ones contain agentic or LLM-related activity.

Agentic activity includes:
- LLM API calls (prompts sent, completions received, token usage, model name)
- Tool or function calls and their results or errors
- Agent reasoning steps, decisions, planning, or ReAct thought/action/observation cycles
- Chain or retrieval operations (RAG, vector search, document retrieval)
- Session or trace start and end boundaries
- Errors originating from agent or LLM systems

For each line return an object with:
  "index"      : the original line number (integer, 0-based)
  "is_agentic" : true or false
  "event_type" : one of ["llm_call","tool_call","agent_decision","retrieval","error","session_start","session_end","other_agentic"] — or null if not agentic
  "confidence" : float 0.0-1.0 indicating your certainty
  "extracted"  : object with any key-value pairs found in the line that are useful for observability
                 (e.g. model, tokens, tool_name, session_id, trace_id, error_message, duration_ms)

Return ONLY a JSON object:
{
  "results": [ ... one object per input line ... ]
}
"#;

// ────────────────────────────────────────────────────────────────────────────
// Classifier
// ────────────────────────────────────────────────────────────────────────────

pub struct LLMClassifier {
    client: Client,
    config: LLMConfig,
}

impl LLMClassifier {
    pub fn new(config: LLMConfig) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(config.timeout_secs))
            .build()
            .context("Failed to build HTTP client")?;

        Ok(Self { client, config })
    }

    /// Classify a batch of log lines.
    ///
    /// Always returns one `ClassifiedEvent` per input line — falls back to
    /// pattern-based classification if the LLM call fails.
    pub async fn classify(&self, lines: Vec<LogLine>) -> Vec<ClassifiedEvent> {
        if lines.is_empty() {
            return vec![];
        }

        match self.classify_via_llm(&lines).await {
            Ok(events) => events,
            Err(e) => {
                warn!("LLM classification failed, using pattern fallback: {}", e);
                lines.into_iter().map(pattern_classify).collect()
            }
        }
    }

    // ── LLM path ─────────────────────────────────────────────────────────────

    async fn classify_via_llm(&self, lines: &[LogLine]) -> Result<Vec<ClassifiedEvent>> {
        let user_message = format_user_message(lines);
        let raw_response = self.call_llm(&user_message).await?;

        debug!("LLM raw response ({} chars)", raw_response.len());

        let parsed = parse_llm_response(&raw_response, lines)?;
        Ok(parsed)
    }

    async fn call_llm(&self, user_message: &str) -> Result<String> {
        let url = format!("{}/v1/chat/completions", self.config.base_url.trim_end_matches('/'));

        let mut payload = json!({
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        });

        // json_mode: request structured JSON output from servers that support it
        if self.config.json_mode {
            payload["response_format"] = json!({"type": "json_object"});
        }

        let mut req = self
            .client
            .post(&url)
            .header("Content-Type", "application/json")
            .json(&payload);

        if !self.config.api_key.is_empty() {
            req = req.bearer_auth(&self.config.api_key);
        }

        let resp = req.send().await.context("LLM request failed")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(anyhow!("LLM server returned {}: {}", status, body));
        }

        let body: JsonValue = resp.json().await.context("Failed to parse LLM response JSON")?;

        body["choices"][0]["message"]["content"]
            .as_str()
            .map(str::to_string)
            .ok_or_else(|| anyhow!("LLM response missing choices[0].message.content"))
    }
}

// ────────────────────────────────────────────────────────────────────────────
// Prompt building
// ────────────────────────────────────────────────────────────────────────────

fn format_user_message(lines: &[LogLine]) -> String {
    let mut msg = String::from("Classify each of the following log lines:\n\n");
    for (i, line) in lines.iter().enumerate() {
        msg.push_str(&format!("[{}] {}\n", i, line.raw));
    }
    msg
}

// ────────────────────────────────────────────────────────────────────────────
// Response parsing
// ────────────────────────────────────────────────────────────────────────────

fn parse_llm_response(raw: &str, lines: &[LogLine]) -> Result<Vec<ClassifiedEvent>> {
    // Try to parse the JSON the LLM returned.  Some models wrap it in markdown
    // code fences, so we strip those first.
    let json_str = extract_json(raw);

    let parsed: JsonValue =
        serde_json::from_str(&json_str).context("LLM response is not valid JSON")?;

    let results = parsed["results"]
        .as_array()
        .ok_or_else(|| anyhow!("LLM JSON missing 'results' array"))?;

    // Build a map from index → result
    let mut map: HashMap<usize, &JsonValue> = HashMap::new();
    for item in results {
        if let Some(idx) = item["index"].as_u64() {
            map.insert(idx as usize, item);
        }
    }

    let mut events = Vec::with_capacity(lines.len());
    for (i, line) in lines.iter().enumerate() {
        let item = map.get(&i);

        let is_agentic = item
            .and_then(|v| v["is_agentic"].as_bool())
            .unwrap_or(false);

        let event_type = if is_agentic {
            item.and_then(|v| v["event_type"].as_str())
                .map(EventType::from_str)
                .unwrap_or(EventType::OtherAgentic)
        } else {
            EventType::NotAgentic
        };

        let confidence = item
            .and_then(|v| v["confidence"].as_f64())
            .unwrap_or(0.5) as f32;

        let extracted: HashMap<String, JsonValue> = item
            .and_then(|v| v["extracted"].as_object())
            .map(|obj| obj.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
            .unwrap_or_default();

        events.push(ClassifiedEvent {
            log_line: line.clone(),
            is_agentic,
            event_type,
            confidence,
            extracted,
            source: ClassificationSource::Llm,
        });
    }

    Ok(events)
}

/// Strip optional markdown code fences and find the outermost JSON object.
fn extract_json(s: &str) -> String {
    // Remove ```json … ``` or ``` … ``` wrappers
    let trimmed = s.trim();
    let inner = if trimmed.starts_with("```") {
        let start = trimmed.find('\n').map(|i| i + 1).unwrap_or(0);
        let end = trimmed.rfind("```").unwrap_or(trimmed.len());
        &trimmed[start..end]
    } else {
        trimmed
    };

    // Find the first '{' … last '}' in case there is surrounding prose
    if let (Some(start), Some(end)) = (inner.find('{'), inner.rfind('}')) {
        inner[start..=end].to_string()
    } else {
        inner.to_string()
    }
}

// ────────────────────────────────────────────────────────────────────────────
// Pattern-based fallback (no LLM required)
// ────────────────────────────────────────────────────────────────────────────

/// Classify a single line using deterministic regex patterns.
/// Used when the LLM is unavailable or returns garbage.
pub fn pattern_classify(line: LogLine) -> ClassifiedEvent {
    let lower = line.raw.to_lowercase();

    let result = check_patterns(&lower);

    let (is_agentic, event_type, confidence) = result.unwrap_or((false, EventType::NotAgentic, 0.95));

    ClassifiedEvent {
        log_line: line,
        is_agentic,
        event_type,
        confidence,
        extracted: HashMap::new(),
        source: ClassificationSource::PatternFallback,
    }
}

fn check_patterns(lower: &str) -> Option<(bool, EventType, f32)> {
    // LLM call indicators
    if contains_any(lower, &["openai", "anthropic", "cohere", "mistral", "llama", "gemini"])
        || (contains_any(lower, &["llm", "language model", "completion"])
            && contains_any(lower, &["call", "request", "response", "token"]))
        || contains_any(lower, &["gpt-", "claude-", "text-davinci", "chat/completions"])
    {
        return Some((true, EventType::LlmCall, 0.75));
    }

    // Tool / function call indicators
    if contains_any(lower, &["tool_call", "function_call", "function call"])
        || (contains_any(lower, &["tool", "function"])
            && contains_any(lower, &["call", "invoke", "execute", "result"]))
    {
        return Some((true, EventType::ToolCall, 0.80));
    }

    // Agent decision / reasoning
    if (contains_any(lower, &["agent", "thought", "action", "observation"])
        && contains_any(lower, &["decision", "plan", "reasoning", "step"]))
        || contains_any(lower, &["react step", "chain of thought", "chain-of-thought"])
    {
        return Some((true, EventType::AgentDecision, 0.70));
    }

    // Retrieval / RAG
    if contains_any(
        lower,
        &[
            "retriev", "vector search", "embedding", "qdrant", "pinecone",
            "chromadb", "weaviate", "similarity search",
        ],
    ) {
        return Some((true, EventType::Retrieval, 0.75));
    }

    // Session boundaries
    if contains_any(lower, &["session start", "session_start", "trace start", "new session"]) {
        return Some((true, EventType::SessionStart, 0.85));
    }
    if contains_any(lower, &["session end", "session_end", "trace end", "session complete"]) {
        return Some((true, EventType::SessionEnd, 0.85));
    }

    // Agentic errors
    if contains_any(lower, &["error", "exception", "failed", "traceback"])
        && contains_any(lower, &["llm", "agent", "tool", "model", "chain", "retriev"])
    {
        return Some((true, EventType::Error, 0.65));
    }

    None
}

fn contains_any(haystack: &str, needles: &[&str]) -> bool {
    needles.iter().any(|n| haystack.contains(n))
}

// ────────────────────────────────────────────────────────────────────────────
// Tests
// ────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    fn make_line(raw: &str) -> LogLine {
        LogLine {
            file_path: "/tmp/test.log".into(),
            agent_id: "test".into(),
            session_id: None,
            byte_offset: 0,
            raw: raw.to_string(),
            read_at: Utc::now(),
        }
    }

    #[test]
    fn test_pattern_llm_call() {
        let ev = pattern_classify(make_line("Calling openai gpt-4 with 200 tokens"));
        assert!(ev.is_agentic);
        assert_eq!(ev.event_type, EventType::LlmCall);
    }

    #[test]
    fn test_pattern_tool_call() {
        let ev = pattern_classify(make_line("tool_call: search(query='hello')"));
        assert!(ev.is_agentic);
        assert_eq!(ev.event_type, EventType::ToolCall);
    }

    #[test]
    fn test_pattern_retrieval() {
        let ev = pattern_classify(make_line("Running vector search with embedding dim=1536"));
        assert!(ev.is_agentic);
        assert_eq!(ev.event_type, EventType::Retrieval);
    }

    #[test]
    fn test_pattern_not_agentic() {
        let ev = pattern_classify(make_line("Server listening on 0.0.0.0:8080"));
        assert!(!ev.is_agentic);
        assert_eq!(ev.event_type, EventType::NotAgentic);
    }

    #[test]
    fn test_pattern_agentic_error() {
        let ev = pattern_classify(make_line("ERROR: LLM request failed after 3 retries"));
        assert!(ev.is_agentic);
        assert_eq!(ev.event_type, EventType::Error);
    }

    #[test]
    fn test_extract_json_strips_fences() {
        let raw = "```json\n{\"results\": []}\n```";
        let extracted = extract_json(raw);
        assert_eq!(extracted, "{\"results\": []}");
    }

    #[test]
    fn test_extract_json_finds_object_in_prose() {
        let raw = "Here is the result: {\"results\": []} and that's it.";
        let extracted = extract_json(raw);
        assert!(extracted.starts_with('{'));
        assert!(extracted.ends_with('}'));
    }

    #[test]
    fn test_format_user_message() {
        let lines = vec![
            make_line("line one"),
            make_line("line two"),
        ];
        let msg = format_user_message(&lines);
        assert!(msg.contains("[0] line one"));
        assert!(msg.contains("[1] line two"));
    }
}
