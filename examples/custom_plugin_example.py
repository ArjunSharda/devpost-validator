"""
Custom Plugin Example for DevPost Validator

This plugin demonstrates how to create a custom plugin for DevPost Validator.
"""
from devpost_validator.plugin_base import PluginBase
from typing import List, Dict, Any
import re


class CustomExamplePlugin(PluginBase):
    """
    Example plugin that checks for potential hard-coded credentials and bad practices.
    """
    
    def __init__(self):
        super().__init__("CustomExamplePlugin")
    
    def initialize(self) -> bool:
        """Initialize the plugin with any setup required"""
        print(f"Initializing {self.name}")
        return True
    
    def register_rules(self) -> List[Dict[str, Any]]:
        """Register custom regex rules for validation"""
        return [
            {
                "name": "example_private_key",
                "pattern": r"-----BEGIN PRIVATE KEY-----",
                "description": "Private key found in code",
                "severity": "high"
            },
            {
                "name": "example_placeholder_code",
                "pattern": r"TODO: implement",
                "description": "Placeholder code found",
                "severity": "medium"
            },
            {
                "name": "example_console_log",
                "pattern": r"console\.log\(.+\)",
                "description": "Debug console.log statement found",
                "severity": "low"
            }
        ]
    
    def check_content(self, content: str) -> List[Dict[str, Any]]:
        """Check content with custom logic beyond regex patterns"""
        issues = []
        
 
        base64_pattern = r"[A-Za-z0-9+/]{30,}={0,2}"
        
        for match in re.finditer(base64_pattern, content):
 
            match_str = match.group(0)
            if len(match_str) >= 40 and "=" in match_str[-2:]:
                issues.append({
                    "rule": "potential_base64_data",
                    "description": "Potential Base64 encoded data or credential",
                    "severity": "medium",
                    "position": match.start(),
                    "match": match_str[:10] + "..." + match_str[-5:]
                })
        
        return issues
    
    def cleanup(self) -> None:
        """Clean up resources when plugin is unloaded"""
        print(f"Cleaning up {self.name}")
