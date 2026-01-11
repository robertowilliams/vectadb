#!/usr/bin/env python3
"""
VectaDB Schema Agent - Uses external LLMs to fix schema issues and assist with VectaDB operations.

This agent can:
1. Analyze schema errors and generate corrected schemas
2. Convert between JSON and YAML formats
3. Validate schema structure before upload
4. Generate schemas from sample data
5. Provide step-by-step troubleshooting

Supported LLMs:
- DeepSeek-V3 (recommended for reasoning)
- Qwen3-235B (recommended for structured outputs)
- Meta Llama 4 Maverick (good balance)
- GLM-4.7 (lightweight, fast)
"""

import json
import yaml
import requests
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for an LLM provider"""
    name: str
    model: str
    api_base: str
    api_key: str = "dummy"  # For local models
    max_tokens: int = 4000
    temperature: float = 0.1  # Low temp for precise schema generation


class SchemaAgent:
    """Intelligent agent for VectaDB schema management"""

    # Recommended models for schema generation
    RECOMMENDED_MODELS = {
        # Tier 1: Best Overall (Complex Reasoning)
        "deepseek-v3": {
            "name": "DeepSeek-V3",
            "model": "hf:deepseek-ai/DeepSeek-V3",
            "provider": "together",
            "pricing": "$0.00000125/1K tokens",
            "strengths": "Best for complex reasoning and error analysis",
            "use_case": "Debugging schema issues, understanding complex errors",
            "tier": "premium"
        },
        "deepseek-v3.2": {
            "name": "DeepSeek-V3.2",
            "model": "hf:deepseek-ai/DeepSeek-V3.2",
            "provider": "fireworks",
            "pricing": "$0.00000056/1K prompt, $0.00000168/1K completion",
            "strengths": "Latest DeepSeek with extended context (162K)",
            "use_case": "Large schemas, complex multi-file analysis",
            "tier": "premium"
        },
        "deepseek-r1": {
            "name": "DeepSeek-R1",
            "model": "hf:deepseek-ai/DeepSeek-R1-0528",
            "provider": "fireworks",
            "pricing": "$0.000003/1K prompt, $0.000008/1K completion",
            "strengths": "Advanced reasoning with chain-of-thought",
            "use_case": "Complex schema transformations, multi-step fixes",
            "tier": "premium"
        },

        # Tier 2: Best for Structured Output
        "qwen3-235b": {
            "name": "Qwen3-235B-Instruct",
            "model": "hf:Qwen/Qwen3-235B-A22B-Instruct-2507",
            "provider": "fireworks",
            "pricing": "$0.00000022/1K prompt, $0.00000088/1K completion",
            "strengths": "Excellent structured output generation",
            "use_case": "Generating clean, well-formatted schemas",
            "tier": "premium"
        },
        "qwen3-235b-thinking": {
            "name": "Qwen3-235B-Thinking",
            "model": "hf:Qwen/Qwen3-235B-A22B-Thinking-2507",
            "provider": "together",
            "pricing": "$0.00000065/1K prompt, $0.000003/1K completion",
            "strengths": "Reasoning-focused Qwen variant",
            "use_case": "Complex reasoning with structured outputs",
            "tier": "premium"
        },

        # Tier 3: Fast and Efficient
        "llama4-maverick": {
            "name": "Llama 4 Maverick",
            "model": "hf:meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
            "provider": "fireworks",
            "pricing": "$0.00000022/1K prompt, $0.00000088/1K completion",
            "strengths": "Good balance of speed and quality, multimodal",
            "use_case": "Quick schema fixes, general assistance",
            "tier": "standard"
        },
        "llama-3.3-70b": {
            "name": "Llama 3.3 70B",
            "model": "hf:meta-llama/Llama-3.3-70B-Instruct",
            "provider": "fireworks",
            "pricing": "$0.0000009/1K tokens",
            "strengths": "Proven reliability, fast inference",
            "use_case": "Standard schema validation and fixes",
            "tier": "standard"
        },

        # Tier 4: Specialized Models
        "kimi-k2-thinking": {
            "name": "Kimi K2 Thinking",
            "model": "hf:moonshotai/Kimi-K2-Thinking",
            "provider": "synthetic",
            "pricing": "$0.00000055/1K tokens",
            "strengths": "Reasoning-focused with large context (262K)",
            "use_case": "Complex reasoning, large schema analysis",
            "tier": "specialized"
        },
        "kimi-k2-instruct": {
            "name": "Kimi K2 Instruct",
            "model": "hf:moonshotai/Kimi-K2-Instruct-0905",
            "provider": "fireworks",
            "pricing": "$0.0000012/1K tokens",
            "strengths": "Instruction-following with large context",
            "use_case": "Following specific schema rules",
            "tier": "specialized"
        },

        # Tier 5: Lightweight and Budget-Friendly
        "glm-4.7": {
            "name": "GLM-4.7",
            "model": "hf:zai-org/GLM-4.7",
            "provider": "synthetic",
            "pricing": "$0.00000055/1K prompt, $0.00000219/1K completion",
            "strengths": "Lightweight, fast, large context (202K)",
            "use_case": "Simple schema validation, quick fixes",
            "tier": "budget"
        },
        "glm-4.6": {
            "name": "GLM-4.6",
            "model": "hf:zai-org/GLM-4.6",
            "provider": "fireworks",
            "pricing": "$0.00000055/1K prompt, $0.00000219/1K completion",
            "strengths": "Lightweight with large context (202K)",
            "use_case": "Budget-friendly schema fixes",
            "tier": "budget"
        },
        "minimax-m2": {
            "name": "MiniMax M2",
            "model": "hf:MiniMaxAI/MiniMax-M2",
            "provider": "fireworks",
            "pricing": "$0.0000003/1K prompt, $0.0000012/1K completion",
            "strengths": "Very cheap, decent quality",
            "use_case": "High-volume testing, budget constraints",
            "tier": "budget"
        },

        # Tier 6: Coding Specialists
        "qwen3-coder": {
            "name": "Qwen3 Coder 480B",
            "model": "hf:Qwen/Qwen3-Coder-480B-A35B-Instruct",
            "provider": "fireworks",
            "pricing": "$0.00000045/1K prompt, $0.0000018/1K completion",
            "strengths": "Specialized for code and structured formats",
            "use_case": "Schema generation, JSON/YAML formatting",
            "tier": "specialized"
        },
        "gpt-oss-120b": {
            "name": "GPT-OSS-120B",
            "model": "hf:openai/gpt-oss-120b",
            "provider": "fireworks",
            "pricing": "$0.0000001/1K tokens",
            "strengths": "Extremely cheap OpenAI-like model",
            "use_case": "Experimentation, high-volume testing",
            "tier": "budget"
        }
    }

    def __init__(self, llm_config: LLMConfig, vectadb_url: str = "http://localhost:8080"):
        self.llm = llm_config
        self.vectadb_url = vectadb_url

    @classmethod
    def create_with_model(cls, model_key: str, api_base: str, vectadb_url: str = "http://localhost:8080"):
        """Create agent with a recommended model"""
        if model_key not in cls.RECOMMENDED_MODELS:
            raise ValueError(f"Unknown model: {model_key}. Choose from: {list(cls.RECOMMENDED_MODELS.keys())}")

        model_info = cls.RECOMMENDED_MODELS[model_key]
        config = LLMConfig(
            name=model_info["name"],
            model=model_info["model"],
            api_base=api_base
        )
        return cls(config, vectadb_url)

    def call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Call the LLM with a prompt"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = requests.post(
                f"{self.llm.api_base}/v1/chat/completions",
                json={
                    "model": self.llm.model,
                    "messages": messages,
                    "temperature": self.llm.temperature,
                    "max_tokens": self.llm.max_tokens
                },
                headers={"Authorization": f"Bearer {self.llm.api_key}"},
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                message = result["choices"][0]["message"]
                # Handle both standard content and reasoning_content (Synthetic API)
                content = message.get("content") or message.get("reasoning_content") or ""
                return content
            else:
                return f"Error calling LLM: {response.status_code} - {response.text}"

        except Exception as e:
            return f"Exception calling LLM: {str(e)}"

    def analyze_schema_error(self, error_message: str, attempted_schema: str) -> Dict[str, Any]:
        """Analyze a schema error and provide detailed diagnosis"""

        system_prompt = """You are a VectaDB schema expert. VectaDB uses Rust with serde for schema deserialization.

VectaDB Schema Structure:
- namespace: string (e.g., "my.ontology")
- version: string (e.g., "1.0.0")
- entity_types: HashMap<String, EntityType>
- relation_types: HashMap<String, RelationType>
- rules: Vec<InferenceRule>

EntityType:
- description: string
- parent_type: Option<String> (null for no parent)
- properties: HashMap<String, PropertyDefinition>

PropertyDefinition:
- type: "string" | "number" | "boolean" | "array" | "object"
- required: boolean
- indexed: boolean
- description: string

RelationType:
- source_type: string
- target_type: string
- description: string
- properties: HashMap<String, PropertyDefinition>

CRITICAL: Properties must be a HashMap (object/map), not an array!"""

        prompt = f"""Analyze this VectaDB schema error:

ERROR: {error_message}

ATTEMPTED SCHEMA:
{attempted_schema}

Provide a detailed analysis in JSON format:
{{
  "error_type": "the type of error",
  "root_cause": "what caused the error",
  "fix_strategy": "how to fix it",
  "corrected_schema": "the corrected schema in proper format"
}}"""

        response = self.call_llm(prompt, system_prompt)

        # Try to extract JSON from response
        try:
            # Look for JSON in markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            else:
                # Try to parse the whole response as JSON
                return json.loads(response)
        except:
            return {
                "error_type": "analysis_failed",
                "root_cause": "Could not parse LLM response",
                "fix_strategy": "Manual review needed",
                "raw_response": response
            }

    def generate_schema_from_sample(self, sample_data: List[Dict[str, Any]],
                                   namespace: str = "auto.generated",
                                   version: str = "1.0.0") -> Dict[str, Any]:
        """Generate a VectaDB schema from sample data"""

        system_prompt = """You are a VectaDB schema generator. Create valid VectaDB schemas from sample data.

Remember:
- entity_types and relation_types are OBJECTS (maps), not arrays
- Each entity/relation type is a key in the object
- Properties are OBJECTS (maps) where each property name is a key
- Use proper Rust/serde types"""

        prompt = f"""Generate a VectaDB schema from this sample data:

SAMPLE DATA:
{json.dumps(sample_data, indent=2)}

NAMESPACE: {namespace}
VERSION: {version}

Analyze the data and create a schema with:
1. Appropriate entity types
2. Property definitions with correct types
3. Potential relation types

Return ONLY valid JSON for the schema, no explanations."""

        response = self.call_llm(prompt, system_prompt)

        # Extract JSON
        try:
            json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            else:
                return json.loads(response)
        except Exception as e:
            print(f"Failed to parse generated schema: {e}")
            print(f"Response: {response}")
            return None

    def fix_and_upload_schema(self, schema_file: str, format: str = "yaml") -> bool:
        """Load a schema, fix any issues, and upload to VectaDB"""

        print(f"\n{'='*80}")
        print(f"VectaDB Schema Agent - Using {self.llm.name}")
        print(f"{'='*80}\n")

        # Load the schema
        print(f"📖 Loading schema from: {schema_file}")
        with open(schema_file, 'r') as f:
            schema_content = f.read()

        # Parse it
        if format == "yaml":
            try:
                schema_dict = yaml.safe_load(schema_content)
            except Exception as e:
                print(f"❌ Failed to parse YAML: {e}")
                return False
        else:
            try:
                schema_dict = json.loads(schema_content)
            except Exception as e:
                print(f"❌ Failed to parse JSON: {e}")
                return False

        print(f"✅ Schema loaded: {schema_dict.get('namespace', 'unknown')} v{schema_dict.get('version', 'unknown')}")

        # Try to upload
        print(f"\n🚀 Attempting to upload schema to VectaDB...")

        payload = {
            "schema": schema_content if format == "yaml" else json.dumps(schema_dict),
            "format": format
        }

        response = requests.post(
            f"{self.vectadb_url}/api/v1/ontology/schema",
            json=payload
        )

        if response.status_code == 200:
            print(f"✅ Schema uploaded successfully!")
            return True

        # Upload failed - analyze error
        print(f"❌ Upload failed: {response.status_code}")
        error_text = response.text
        print(f"Error: {error_text}\n")

        print(f"🤖 Analyzing error with {self.llm.name}...")
        analysis = self.analyze_schema_error(error_text, schema_content)

        print(f"\n📊 Error Analysis:")
        print(f"  Type: {analysis.get('error_type', 'unknown')}")
        print(f"  Cause: {analysis.get('root_cause', 'unknown')}")
        print(f"  Fix: {analysis.get('fix_strategy', 'unknown')}\n")

        if "corrected_schema" in analysis:
            print(f"🔧 Applying fix...")

            # Try the corrected schema
            try:
                corrected = analysis["corrected_schema"]

                # Determine format
                if isinstance(corrected, str):
                    # Try to detect if it's JSON or YAML
                    if corrected.strip().startswith('{'):
                        corrected_dict = json.loads(corrected)
                        upload_format = "json"
                        upload_content = corrected
                    else:
                        corrected_dict = yaml.safe_load(corrected)
                        upload_format = "yaml"
                        upload_content = corrected
                else:
                    corrected_dict = corrected
                    upload_format = "json"
                    upload_content = json.dumps(corrected_dict)

                # Try upload again
                payload = {
                    "schema": upload_content,
                    "format": upload_format
                }

                response = requests.post(
                    f"{self.vectadb_url}/api/v1/ontology/schema",
                    json=payload
                )

                if response.status_code == 200:
                    print(f"✅ Fixed schema uploaded successfully!")

                    # Save corrected schema
                    corrected_file = schema_file.replace('.', '_corrected.')
                    with open(corrected_file, 'w') as f:
                        if upload_format == "yaml":
                            yaml.dump(corrected_dict, f, default_flow_style=False)
                        else:
                            json.dump(corrected_dict, f, indent=2)

                    print(f"💾 Corrected schema saved to: {corrected_file}")
                    return True
                else:
                    print(f"❌ Fixed schema also failed: {response.status_code}")
                    print(f"Error: {response.text}")

                    # Try one more time with deeper analysis
                    print(f"\n🤖 Attempting deeper analysis...")
                    second_analysis = self.analyze_schema_error(response.text, upload_content)

                    print(f"\n📊 Second Analysis:")
                    print(json.dumps(second_analysis, indent=2))

                    return False

            except Exception as e:
                print(f"❌ Failed to apply fix: {e}")
                return False
        else:
            print(f"⚠️  No automatic fix available. Raw response:")
            print(json.dumps(analysis, indent=2))
            return False

    def interactive_troubleshoot(self):
        """Interactive troubleshooting session"""
        print(f"\n{'='*80}")
        print(f"VectaDB Schema Agent - Interactive Mode")
        print(f"Using: {self.llm.name}")
        print(f"{'='*80}\n")

        while True:
            print("\nOptions:")
            print("1. Analyze schema error")
            print("2. Generate schema from sample data")
            print("3. Fix and upload schema file")
            print("4. Get schema best practices")
            print("5. Exit")

            choice = input("\nSelect option (1-5): ").strip()

            if choice == "1":
                error = input("Paste error message: ").strip()
                schema = input("Paste attempted schema (or file path): ").strip()

                if schema.endswith(('.json', '.yaml', '.yml')):
                    with open(schema, 'r') as f:
                        schema = f.read()

                analysis = self.analyze_schema_error(error, schema)
                print("\n" + json.dumps(analysis, indent=2))

            elif choice == "2":
                data_file = input("Enter path to sample data JSON file: ").strip()

                with open(data_file, 'r') as f:
                    sample_data = json.load(f)

                if not isinstance(sample_data, list):
                    sample_data = [sample_data]

                namespace = input("Enter namespace (default: auto.generated): ").strip() or "auto.generated"

                schema = self.generate_schema_from_sample(sample_data, namespace)

                if schema:
                    print("\nGenerated Schema:")
                    print(json.dumps(schema, indent=2))

                    save = input("\nSave to file? (y/n): ").strip().lower()
                    if save == 'y':
                        filename = input("Enter filename: ").strip()
                        with open(filename, 'w') as f:
                            json.dump(schema, f, indent=2)
                        print(f"Saved to {filename}")

            elif choice == "3":
                schema_file = input("Enter schema file path: ").strip()
                format_type = input("Format (json/yaml): ").strip().lower() or "yaml"

                self.fix_and_upload_schema(schema_file, format_type)

            elif choice == "4":
                prompt = """Provide VectaDB schema best practices and common pitfalls to avoid.
Include:
1. Proper structure
2. Type definitions
3. Common errors
4. Examples"""

                response = self.call_llm(prompt, "You are a VectaDB schema expert.")
                print("\n" + response)

            elif choice == "5":
                print("Goodbye!")
                break


def main():
    import argparse

    parser = argparse.ArgumentParser(description="VectaDB Schema Agent")
    parser.add_argument("--model", choices=list(SchemaAgent.RECOMMENDED_MODELS.keys()),
                       default="deepseek-v3", help="LLM model to use")
    parser.add_argument("--api-base", required=True, help="LLM API base URL")
    parser.add_argument("--api-key", default="dummy", help="API key (if needed)")
    parser.add_argument("--vectadb-url", default="http://localhost:8080", help="VectaDB URL")
    parser.add_argument("--schema-file", help="Schema file to fix and upload")
    parser.add_argument("--format", choices=["json", "yaml"], default="yaml", help="Schema format")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")

    args = parser.parse_args()

    # Print model info
    model_info = SchemaAgent.RECOMMENDED_MODELS[args.model]
    print(f"\n🤖 Using: {model_info['name']}")
    print(f"   Strengths: {model_info['strengths']}")
    print(f"   Best for: {model_info['use_case']}\n")

    # Create agent
    config = LLMConfig(
        name=model_info["name"],
        model=model_info["model"],
        api_base=args.api_base,
        api_key=args.api_key
    )

    agent = SchemaAgent(config, args.vectadb_url)

    if args.interactive:
        agent.interactive_troubleshoot()
    elif args.schema_file:
        agent.fix_and_upload_schema(args.schema_file, args.format)
    else:
        # Default: try to fix the bedrock schema
        print("No schema file specified. Use --schema-file or --interactive")
        print("\nExample usage:")
        print(f"  python vectadb_schema_agent.py --model deepseek-v3 --api-base http://localhost:8000 --schema-file bedrock_schema.json")
        print(f"  python vectadb_schema_agent.py --model qwen3-235b --api-base http://localhost:8000 --interactive")


if __name__ == "__main__":
    main()
