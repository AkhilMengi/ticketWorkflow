"""Utility for parsing recommended actions from file"""

import json
import os
from typing import List, Dict, Any


def parse_actions_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse recommended actions/suggestions from a YAML file.
    
    Expected format (suggestions):
    ```
    suggestion_1:
      title: "Reach out to team"
      description: "Contact team to investigate"
    ```
    
    Or legacy format (action definitions):
    ```
    salesforce_case:
      description: "Create support case"
      parameters:
        priority: "high"
    ```
    
    Args:
        file_path: Path to the actions/suggestions file
    
    Returns:
        List of action/suggestion dictionaries with title and description
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
            
            for key, config in content.items():
                if isinstance(config, dict):
                    # Handle new format (suggestions with title and description)
                    if "title" in config:
                        actions.append({
                            "title": config.get("title", ""),
                            "description": config.get("description", ""),
                            "action_type": key  # For compatibility
                        })
                    # Handle legacy format (action definitions)
                    else:
                        actions.append({
                            "action_type": key,
                            "description": config.get("description", ""),
                            "title": config.get("description", ""),  # Use description as title fallback
                            "parameters": config.get("parameters", {})
                        })
        
        return actions
        
    except Exception as e:
        raise ValueError(f"Error parsing actions file: {str(e)}")
