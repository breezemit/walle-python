"""Configuration management for Walle."""

import json
import os
from pathlib import Path
from typing import Optional, Any, List
from pydantic import validator
from pydantic_settings import BaseSettings


# Utility functions (merged from utils module)
def is_in_array(item: Any, array: List[Any]) -> bool:
    """Check if item is in array.
    
    Args:
        item: Item to search for
        array: List to search in
        
    Returns:
        True if item is found in array
    """
    return item in array


def close_silently(file_obj):
    """Close file object silently, ignoring errors.
    
    Args:
        file_obj: File-like object to close
    """
    try:
        if hasattr(file_obj, 'close'):
            file_obj.close()
    except Exception:
        pass


class Config(BaseSettings):
    """Configuration settings for Walle."""
    
    gitlab_host: str = "https://gitlab.com"
    gitlab_token: Optional[str] = None
    project: Optional[str] = None
    config_file: Optional[str] = None
    
    @validator('gitlab_host')
    def normalize_gitlab_host(cls, v):
        """Ensure GitLab host has proper protocol."""
        if v and not v.startswith(('http://', 'https://')):
            return f"https://{v}"
        return v
    
    class Config:
        env_prefix = "WALLE_"
        case_sensitive = False


def load_json_config(config_path: str) -> dict:
    """Load configuration from JSON file.
    
    Args:
        config_path: Path to JSON configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise ValueError(f"Error loading config file {config_path}: {e}")


def find_config_file() -> Optional[str]:
    """Find configuration file in common locations.
    
    Returns:
        Path to config file or None if not found
    """
    # Common config file locations
    search_paths = [
        "walle.json",
        ".walle.json", 
        "~/.walle.json",
        "~/.config/walle/config.json",
        "/etc/walle/config.json"
    ]
    
    for path_str in search_paths:
        path = Path(path_str).expanduser()
        if path.exists() and path.is_file():
            return str(path)
    
    return None


def get_config(config_file: Optional[str] = None) -> Config:
    """Load configuration from environment variables and/or JSON file.
    
    Args:
        config_file: Optional path to JSON config file
        
    Returns:
        Configuration object
    """
    # Start with environment variables
    config_data = {}
    
    # Try to load from JSON file
    json_config_path = config_file or find_config_file()
    if json_config_path:
        try:
            json_config = load_json_config(json_config_path)
            config_data.update(json_config)
        except ValueError:
            # If file exists but can't be loaded, ignore silently
            # Environment variables will take precedence
            pass
    
    # Environment variables override JSON config
    env_config = {
        'gitlab_host': os.getenv('WALLE_GITLAB_HOST'),
        'gitlab_token': os.getenv('WALLE_GITLAB_TOKEN'), 
        'project': os.getenv('WALLE_PROJECT'),
    }
    
    # Remove None values and update config_data
    env_config = {k: v for k, v in env_config.items() if v is not None}
    config_data.update(env_config)
    
    return Config(**config_data)


def create_sample_config(path: str = "walle.json") -> None:
    """Create a sample configuration file.
    
    Args:
        path: Path where to create the sample config file
    """
    sample_config = {
        "gitlab_host": "https://gitlab.com",
        "gitlab_token": "your-gitlab-token-here",
        "project": "group/project-name",
        "since": "v1.0.0"  # Optional: starting commit/tag/branch for version tracking
    }
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sample_config, f, indent=2)
    
    print(f"Sample configuration file created at: {path}")
    print("Please edit the file and add your GitLab token and project details.")