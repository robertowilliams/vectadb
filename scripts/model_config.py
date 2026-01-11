#!/usr/bin/env python3
"""
Model configuration loader for VectaDB Schema Agent
Loads model settings from environment variables or .env.models file
"""

import os
from pathlib import Path
from typing import Dict, Optional


class ModelConfig:
    """Load and manage model configurations from environment"""

    # Model key to environment variable prefix mapping
    MODEL_ENV_MAP = {
        "deepseek-v3.2": "DEEPSEEK_V32",
        "deepseek-v3": "DEEPSEEK_V3",
        "deepseek-r1": "DEEPSEEK_R1",
        "qwen3-235b": "QWEN3_235B",
        "qwen3-235b-thinking": "QWEN3_235B_THINKING",
        "llama4-maverick": "LLAMA4_MAVERICK",
        "llama-3.3-70b": "LLAMA_33_70B",
        "kimi-k2-thinking": "KIMI_K2_THINKING",
        "kimi-k2-instruct": "KIMI_K2_INSTRUCT",
        "glm-4.7": "GLM_47",
        "glm-4.6": "GLM_46",
        "minimax-m2": "MINIMAX_M2",
        "qwen3-coder": "QWEN3_CODER",
        "gpt-oss-120b": "GPT_OSS"
    }

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize model config

        Args:
            env_file: Path to .env file (default: .env.models in current dir)
        """
        if env_file is None:
            env_file = Path.cwd() / ".env.models"

        self.env_file = Path(env_file)
        self.load_env_file()

    def load_env_file(self):
        """Load environment variables from .env file if it exists"""
        if not self.env_file.exists():
            return

        with open(self.env_file, 'r') as f:
            for line in f:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Handle variable references like ${VAR}
                    while '${' in value:
                        start = value.find('${')
                        end = value.find('}', start)
                        if end == -1:
                            break

                        var_name = value[start+2:end]
                        var_value = os.getenv(var_name, '')
                        value = value[:start] + var_value + value[end+1:]

                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value

    def get_model_config(self, model_key: str) -> Dict[str, str]:
        """
        Get configuration for a specific model

        Args:
            model_key: Model identifier (e.g., "deepseek-v3.2")

        Returns:
            Dict with 'model' and 'api_base' keys
        """
        env_prefix = self.MODEL_ENV_MAP.get(model_key)

        if not env_prefix:
            raise ValueError(f"Unknown model: {model_key}")

        model_var = f"{env_prefix}_MODEL"
        api_base_var = f"{env_prefix}_API_BASE"

        model = os.getenv(model_var)
        api_base = os.getenv(api_base_var, os.getenv("LLM_API_BASE", "http://localhost:8000"))

        if not model:
            raise ValueError(f"Model not configured: {model_var} not set in environment")

        return {
            "model": model,
            "api_base": api_base,
            "api_key": os.getenv("LLM_API_KEY", "dummy")
        }

    def get_default_model(self) -> str:
        """Get the default model from environment or return 'deepseek-v3.2'"""
        return os.getenv("DEFAULT_MODEL", "deepseek-v3.2")

    def get_vectadb_url(self) -> str:
        """Get VectaDB URL from environment"""
        return os.getenv("VECTADB_URL", "http://localhost:8080")

    def list_configured_models(self) -> list:
        """List all models that are configured in environment"""
        configured = []

        for model_key, env_prefix in self.MODEL_ENV_MAP.items():
            model_var = f"{env_prefix}_MODEL"
            if os.getenv(model_var):
                configured.append(model_key)

        return configured

    def print_config_summary(self):
        """Print a summary of current configuration"""
        print("=" * 80)
        print("VectaDB Schema Agent - Model Configuration")
        print("=" * 80)
        print()

        print(f"Environment file: {self.env_file}")
        print(f"Exists: {self.env_file.exists()}")
        print()

        print(f"Default model: {self.get_default_model()}")
        print(f"VectaDB URL: {self.get_vectadb_url()}")
        print(f"LLM API Base: {os.getenv('LLM_API_BASE', 'http://localhost:8000')}")
        print()

        configured = self.list_configured_models()
        print(f"Configured models ({len(configured)}):")
        for model_key in configured:
            try:
                config = self.get_model_config(model_key)
                print(f"  ✅ {model_key:20} -> {config['model']}")
            except:
                print(f"  ❌ {model_key:20} -> Error")

        print()
        print(f"Available models (total: {len(self.MODEL_ENV_MAP)}):")
        for model_key in self.MODEL_ENV_MAP.keys():
            if model_key not in configured:
                print(f"  ⚪ {model_key}")


def main():
    """CLI for testing model configuration"""
    import argparse

    parser = argparse.ArgumentParser(description="Model Configuration Manager")
    parser.add_argument("--env-file", help="Path to .env file")
    parser.add_argument("--model", help="Test loading specific model")
    parser.add_argument("--list", action="store_true", help="List configured models")

    args = parser.parse_args()

    config = ModelConfig(args.env_file)

    if args.list:
        config.print_config_summary()
    elif args.model:
        try:
            model_config = config.get_model_config(args.model)
            print(f"Model: {args.model}")
            print(f"  ID: {model_config['model']}")
            print(f"  API Base: {model_config['api_base']}")
            print(f"  API Key: {'***' if model_config['api_key'] != 'dummy' else 'dummy'}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        config.print_config_summary()


if __name__ == "__main__":
    main()
