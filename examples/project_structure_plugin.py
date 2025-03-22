"""
Project Structure Plugin for DevPost Validator

This plugin checks if a project has appropriate structure and documentation.
"""
from devpost_validator.plugin_base import PluginBase
from typing import List, Dict, Any
import re


class ProjectStructurePlugin(PluginBase):
    """
    A plugin that checks for proper project structure in submissions.
    """
    
    def __init__(self):
        super().__init__("ProjectStructureChecker")
    
    def initialize(self) -> bool:
        print(f"Initializing {self.name}")
        return True
    
    def register_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "missing_readme",
                "pattern": r"(?i)#\s*readme|readme\s*\n|(?i)readme\.md",
                "description": "Check for presence of README file or section",
                "severity": "medium"
            },
            {
                "name": "license_missing",
                "pattern": r"(?i)#\s*license|license\s*\n|(?i)license\.md|mit license|apache license|gnu|gpl|bsd license",
                "description": "Check for presence of license information",
                "severity": "low"
            },
            {
                "name": "setup_instructions",
                "pattern": r"(?i)#\s*(?:installation|setup|getting started)|(?:installation|setup|getting started)\s*\n|how to (?:install|use|run)",
                "description": "Check for setup/installation instructions",
                "severity": "medium"
            }
        ]
    
    def check_content(self, content: str) -> List[Dict[str, Any]]:
        results = []
        
        # Check for code-to-documentation ratio
        code_lines = 0
        comment_lines = 0
        
        for line in content.splitlines():
            stripped = line.strip()
            
            if not stripped:  # Skip empty lines
                continue
                
            # Simple heuristic for comments (not perfect but a starting point)
            if (stripped.startswith('#') or 
                stripped.startswith('//') or 
                stripped.startswith('/*') or 
                stripped.startswith('*') or 
                stripped.startswith(';') or 
                stripped.startswith('%')):
                comment_lines += 1
            else:
                code_lines += 1
        
        # If there's actual code, check the ratio
        if code_lines > 0:
            comment_ratio = comment_lines / (code_lines + comment_lines)
            
            if comment_ratio < 0.05 and code_lines > 50:
                results.append({
                    "rule": "low_documentation",
                    "description": f"Code has very low documentation ratio ({comment_ratio:.1%})",
                    "severity": "medium",
                    "position": 0
                })
        
        # Check for URLs to external resources
        urls = re.findall(r'https?://[^\s<>"\']+|www\.[^\s<>"\']+', content)
        
        # Count unique domains to see if they're linking to resources
        if len(urls) < 2 and len(content.splitlines()) > 100:
            results.append({
                "rule": "few_references",
                "description": "Project has few or no references to external resources",
                "severity": "low", 
                "position": 0
            })
            
        return results
    
    def cleanup(self) -> None:
        print(f"Cleaning up {self.name}")
