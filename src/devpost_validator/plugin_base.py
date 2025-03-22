from typing import List, Dict, Any


class PluginBase:
    """
    Base class for DevPost Validator plugins.
    
    All plugins should inherit from this class and implement
    the required methods.
    """
    
    def __init__(self, name: str):
        """
        Initialize a plugin with a name.
        
        Args:
            name: A unique name for the plugin
        """
        self.name = name
    
    def initialize(self) -> bool:
        """
        Initialize the plugin. Called when the plugin is loaded.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        return True
    
    def register_rules(self) -> List[Dict[str, Any]]:
        """
        Register custom rules provided by this plugin.
        
        Returns:
            List of rule dictionaries with name, pattern, description, and optional severity
        """
        return []
    
    def check_content(self, content: str) -> List[Dict[str, Any]]:
        """
        Check content against custom logic beyond regex patterns.
        
        Args:
            content: The text content to validate
            
        Returns:
            List of issues found in the content
        """
        return []
    
    def cleanup(self) -> None:
        """
        Cleanup resources before plugin is unloaded.
        
        This method should perform any necessary cleanup when the plugin
        is being unloaded, such as closing files or network connections.
        """
        pass
