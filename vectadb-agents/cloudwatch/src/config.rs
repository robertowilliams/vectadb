// Configuration for CloudWatch agent

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;

/// Main agent configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    /// AWS configuration
    pub aws: AwsConfig,

    /// VectaDB API configuration
    pub vectadb: VectaDBConfig,

    /// Log groups to monitor
    pub log_groups: Vec<LogGroupConfig>,

    /// Agent behavior settings
    #[serde(default)]
    pub agent: AgentSettings,
}

/// AWS CloudWatch configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AwsConfig {
    /// AWS region (e.g., "us-east-1")
    pub region: String,

    /// Optional AWS profile name
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
}

/// VectaDB API configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectaDBConfig {
    /// VectaDB API endpoint (e.g., "http://localhost:8080")
    pub endpoint: String,

    /// Optional API key (for future authentication)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,

    /// Batch size for bulk ingestion (default: 100)
    #[serde(default = "default_batch_size")]
    pub batch_size: usize,

    /// Request timeout in seconds (default: 30)
    #[serde(default = "default_timeout")]
    pub timeout_secs: u64,
}

/// Log group configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogGroupConfig {
    /// CloudWatch log group name
    pub name: String,

    /// Optional agent identifier for this log group
    #[serde(skip_serializing_if = "Option::is_none")]
    pub agent_id: Option<String>,

    /// Parser rules for this log group
    #[serde(default)]
    pub parsers: Vec<ParserRule>,

    /// Filter pattern (CloudWatch filter syntax)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub filter_pattern: Option<String>,
}

/// Parser rule for extracting structured data from logs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParserRule {
    /// Rule name/description
    pub name: String,

    /// Parser type
    #[serde(rename = "type")]
    pub parser_type: ParserType,

    /// Regex pattern (for Regex parser type)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pattern: Option<String>,

    /// Field mappings: regex capture group name -> event property name
    #[serde(default)]
    pub field_mapping: std::collections::HashMap<String, String>,

    /// Event type to assign when this rule matches
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_type: Option<String>,

    /// Priority (lower number = higher priority, default: 100)
    #[serde(default = "default_priority")]
    pub priority: u32,
}

/// Parser type
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum ParserType {
    /// Parse as JSON
    Json,
    /// Parse using regex pattern
    Regex,
    /// Built-in LangChain parser
    LangChain,
    /// Built-in LlamaIndex parser
    LlamaIndex,
}

/// Agent behavior settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSettings {
    /// Polling interval in seconds (default: 10)
    #[serde(default = "default_poll_interval")]
    pub poll_interval_secs: u64,

    /// Lookback window in seconds for first poll (default: 300 = 5 minutes)
    #[serde(default = "default_lookback")]
    pub lookback_secs: u64,

    /// Auto-create traces from session_id (default: true)
    #[serde(default = "default_true")]
    pub auto_create_traces: bool,

    /// Generate embeddings for events (default: true)
    #[serde(default = "default_true")]
    pub generate_embeddings: bool,
}

impl Default for AgentSettings {
    fn default() -> Self {
        Self {
            poll_interval_secs: default_poll_interval(),
            lookback_secs: default_lookback(),
            auto_create_traces: true,
            generate_embeddings: true,
        }
    }
}

// Default value functions
fn default_batch_size() -> usize {
    100
}

fn default_timeout() -> u64 {
    30
}

fn default_poll_interval() -> u64 {
    10
}

fn default_lookback() -> u64 {
    300 // 5 minutes
}

fn default_priority() -> u32 {
    100
}

fn default_true() -> bool {
    true
}

impl AgentConfig {
    /// Load configuration from YAML file
    pub fn from_file<P: AsRef<Path>>(path: P) -> Result<Self> {
        let contents = std::fs::read_to_string(path.as_ref())
            .context("Failed to read config file")?;

        let config: AgentConfig = serde_yaml::from_str(&contents)
            .context("Failed to parse config YAML")?;

        config.validate()?;

        Ok(config)
    }

    /// Validate configuration
    fn validate(&self) -> Result<()> {
        // Validate AWS region
        if self.aws.region.is_empty() {
            anyhow::bail!("AWS region cannot be empty");
        }

        // Validate VectaDB endpoint
        if self.vectadb.endpoint.is_empty() {
            anyhow::bail!("VectaDB endpoint cannot be empty");
        }

        // Validate log groups
        if self.log_groups.is_empty() {
            anyhow::bail!("At least one log group must be configured");
        }

        for log_group in &self.log_groups {
            if log_group.name.is_empty() {
                anyhow::bail!("Log group name cannot be empty");
            }

            // Validate parser rules
            for parser in &log_group.parsers {
                if parser.parser_type == ParserType::Regex && parser.pattern.is_none() {
                    anyhow::bail!(
                        "Regex parser '{}' must have a pattern",
                        parser.name
                    );
                }
            }
        }

        Ok(())
    }

    /// Get all log group names
    pub fn log_group_names(&self) -> Vec<String> {
        self.log_groups.iter().map(|lg| lg.name.clone()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_settings() {
        let settings = AgentSettings::default();
        assert_eq!(settings.poll_interval_secs, 10);
        assert_eq!(settings.lookback_secs, 300);
        assert!(settings.auto_create_traces);
        assert!(settings.generate_embeddings);
    }

    #[test]
    fn test_config_validation() {
        let config = AgentConfig {
            aws: AwsConfig {
                region: "us-east-1".to_string(),
                profile: None,
            },
            vectadb: VectaDBConfig {
                endpoint: "http://localhost:8080".to_string(),
                api_key: None,
                batch_size: 100,
                timeout_secs: 30,
            },
            log_groups: vec![LogGroupConfig {
                name: "/aws/lambda/test".to_string(),
                agent_id: None,
                parsers: vec![],
                filter_pattern: None,
            }],
            agent: AgentSettings::default(),
        };

        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_invalid_config() {
        let config = AgentConfig {
            aws: AwsConfig {
                region: "".to_string(),
                profile: None,
            },
            vectadb: VectaDBConfig {
                endpoint: "http://localhost:8080".to_string(),
                api_key: None,
                batch_size: 100,
                timeout_secs: 30,
            },
            log_groups: vec![],
            agent: AgentSettings::default(),
        };

        assert!(config.validate().is_err());
    }
}
