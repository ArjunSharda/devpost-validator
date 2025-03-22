from typing import List, Dict, Any, Optional


class PluginBase:
    """Base class for all DevPost Validator plugins."""
    
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
    
    def check_content(self, content: str) -> List[Dict[str, Any]]:
        """
        Check content against plugin rules.
        
        Args:
            content: The text content to validate
            
        Returns:
            List of issues found in the content
        """
        return []
    
    def register_rules(self) -> List[Dict[str, Any]]:
        """
        Register custom rules provided by this plugin.
        
        Returns:
            List of rule dictionaries with name, pattern, description, and optional severity
        """
        return []
    
    def initialize(self) -> bool:
        """
        Initialize the plugin. Called when the plugin is loaded.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        return True
    
    def cleanup(self) -> None:
        """Cleanup resources before plugin is unloaded."""
        pass
