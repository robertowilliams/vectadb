import os
import yaml
from dotenv import load_dotenv

def load_config(config_path=None, env_path=None):
    """
    Loads configuration from YAML and environment files, regardless of CWD.

    - config.yaml and .env are expected to be inside /config at the project root.
    - Adds MONGO_URI from .env to the returned dictionary.
    """

    # Compute absolute project root safely
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

    # Default paths
    config_path = config_path or os.path.join(project_root, "config", "config.yaml")
    env_path = env_path or os.path.join(project_root, "config", ".env")

    # Debug logging
    print(f"[load_config] Project root: {project_root}")
    print(f"[load_config] Looking for config file at: {config_path}")
    print(f"[load_config] Looking for env file at: {env_path}")
    print(f"[load_config] Current working directory: {os.getcwd()}")

    # Load environment variables (optional)
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        print(f"[load_config] Warning: .env file not found at {env_path}")

    # Verify YAML file exists
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Load YAML configuration
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Add Mongo URI (optional)
    mongo_uri = os.getenv("MONGO_URI")
    if mongo_uri:
        config["MONGO_URI"] = mongo_uri
    else:
        print("[load_config] Warning: MONGO_URI not set in environment")

    return config
