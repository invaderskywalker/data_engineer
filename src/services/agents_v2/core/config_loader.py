

import json
from src.api.logging.AppLogger import appLogger
import traceback
from typing import Dict

class ConfigLoader:
    """Loads and validates configuration for prompts, data sources, actions, and query mappings."""
    @staticmethod
    def load(config_path: str) -> Dict:
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            ConfigLoader._validate_config(config)
            print("config ---- ", config)
            return config
        except Exception as e:
            appLogger.error({"function": "ConfigLoader.load_error", "error": str(e), "traceback": traceback.format_exc()})
            raise ValueError(f"Failed to load configuration: {str(e)}")

    @staticmethod
    def _validate_config(config: Dict):
        required_sections = ["prompts", "data_sources", "actions", "query_intent_mappings"]
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Configuration missing required section: {section}")
            
            