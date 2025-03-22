"""
Utility functions for plugin management in DevPost Validator.
"""
import os
from typing import Optional, Dict, Any, List
from pathlib import Path


def create_plugin_template(output_path: str, plugin_name: str = "CustomPlugin", 
                           plugin_type: str = "class") -> bool:
    """
    Create a new plugin template file.
    
    Args:
        output_path: Path where the plugin file should be saved
        plugin_name: Name for the plugin class or module
        plugin_type: Type of plugin ('class' or 'function')
    
    Returns:
        True if plugin template was created successfully, False otherwise
    """
    try:
        if plugin_type == "class":
            template = _get_class_template(plugin_name)
        else:
            template = _get_function_template()
        
        with open(output_path, 'w') as f:
            f.write(template)
        
        return True
    except Exception as e:
        print(f"Error creating plugin template: {e}")
        return False


def _get_class_template(class_name: str) -> str:
    """Get template code for a class-based plugin."""
    return f'''"""
{class_name} - Custom DevPost Validator Plugin

This plugin checks for specific patterns and issues in DevPost submissions.
"""
from devpost_validator.plugin_base import PluginBase
from typing import List, Dict, Any


class {class_name}(PluginBase):
    """
    Custom plugin for DevPost Validator.
    
    Add your plugin description here.
    """
    
    def __init__(self):
        super().__init__("{class_name}")
    
    def initialize(self) -> bool:
        """
        Initialize the plugin. Called when the plugin is loaded.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        print(f"Initializing {{self.name}}")
        return True
    
    def register_rules(self) -> List[Dict[str, Any]]:
        """
        Register custom rules provided by this plugin.
        
        Returns:
            List of rule dictionaries with name, pattern, description, and optional severity
        """
        return [
            {{
                "name": "custom_rule_example",
                "pattern": r"\\b(example|placeholder)\\b",
                "description": "Example rule - replace with your own",
                "severity": "low"  # Can be "low", "medium", or "high"
            }},
            # Add more rules as needed
        ]
    
    def check_content(self, content: str) -> List[Dict[str, Any]]:
        """
        Check content against custom logic beyond regex patterns.
        
        Args:
            content: The text content to validate
            
        Returns:
            List of issues found in the content
        """
        results = []
        
        # Example custom check - replace with your own logic
        if len(content) < 500:
            results.append({{
                "rule": "content_too_short",
                "description": "Content is less than 500 characters",
                "severity": "low",
                "position": 0
            }})
            
        return results
    
    def cleanup(self) -> None:
        """Cleanup resources before plugin is unloaded."""
        print(f"Cleaning up {{self.name}}")
'''


def _get_function_template() -> str:
    """Get template code for a function-based plugin."""
    return '''"""
Function-based DevPost Validator Plugin

This plugin provides custom validation rules and checks.
"""
from typing import List, Dict, Any


def check_content(content: str) -> List[Dict[str, Any]]:
    """
    Check content against custom validation logic.
    
    Args:
        content: The text content to validate
        
    Returns:
        List of issues found in the content
    """
    results = []
    
    # Example custom check - replace with your own logic
    if len(content) < 500:
        results.append({
            "rule": "content_too_short",
            "description": "Content is less than 500 characters",
            "severity": "low",
            "position": 0
        })
    
    return results


def register_rules() -> List[Dict[str, Any]]:
    """
    Register custom regex rules.
    
    Returns:
        List of rule dictionaries
    """
    return [
        {
            "name": "custom_pattern_example",
            "pattern": r"\\b(example|placeholder)\\b",
            "description": "Example pattern - replace with your own",
            "severity": "medium"
        },
        # Add more rules as needed
    ]
'''


def discover_plugins(directory: str) -> List[str]:
    """
    Discover potential plugin files in a directory.
    
    Args:
        directory: Directory to scan for plugin files
    
    Returns:
        List of paths to potential plugin files
    """
    plugins = []
    try:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return []
            
        # Look for Python files
        for file_path in path.glob("**/*.py"):
            # Simple heuristic: check if file might be a plugin
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if ('check_content' in content or 
                    'register_rules' in content or 
                    'PluginBase' in content):
                    plugins.append(str(file_path))
    except Exception:
        pass
        
    return plugins
