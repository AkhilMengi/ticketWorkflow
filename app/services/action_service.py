"""Utility for parsing recommended actions from file"""

import json
import os
from typing import List, Dict, Any


def parse_actions_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse recommended actions from a YAML or JSON file.
    
    Expected format:
    ```
    salesforce_case:
      description: "Create support case"
      parameters:
        priority: "high"
        category: "billing"
    ```
    
    Args:
        file_path: Path to the actions file
    
    Returns:
        List of action dictionaries with action_type, description, parameters
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    actions = []
    
    try:
        with open(file_path, 'r') as f:
            import yaml
            content = yaml.safe_load(f)
            
            if not content:
                return actions
            
            for action_type, action_config in content.items():
                if isinstance(action_config, dict):
                    actions.append({
                        "action_type": action_type,
                        "description": action_config.get("description", ""),
                        "parameters": action_config.get("parameters", {})
                    })
        
        return actions
        
    except Exception as e:
        raise ValueError(f"Error parsing actions file: {str(e)}")
