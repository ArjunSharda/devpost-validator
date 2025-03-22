from devpost_validator.plugin_base import PluginBase
from typing import List, Dict, Any


class CustomPatternPlugin(PluginBase):
    """Example plugin that checks for specific patterns in DevPost submissions."""
    
    def __init__(self):
        super().__init__("CustomPatternPlugin")
    
    def initialize(self) -> bool:
        print(f"Initializing {self.name}")
        return True
    
    def register_rules(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "excessive_buzzwords",
                "pattern": r"\b(AI|ML|blockchain|IoT|cloud)\b.{0,30}\b(AI|ML|blockchain|IoT|cloud)\b.{0,30}\b(AI|ML|blockchain|IoT|cloud)\b",
                "description": "Excessive use of tech buzzwords in close proximity",
                "severity": "low"
            },
            {
                "name": "vague_innovation_claim",
                "pattern": r"\b(revolutionary|groundbreaking|disrupting|first-of-its-kind|game-changer)\b",
                "description": "Vague claims of innovation without specific details",
                "severity": "medium"
            }
        ]
    
    def check_content(self, content: str) -> List[Dict[str, Any]]:
        # You can implement custom validation logic here beyond just regex patterns
        results = []
        
        # Example: Check if the description is too short
        if len(content.split()) < 100:
            results.append({
                "rule": "content_too_short",
                "description": "Project description seems too brief (less than 100 words)",
                "severity": "medium",
                "position": 0
            })
            
        return results
    
    def cleanup(self) -> None:
        print(f"Cleaning up {self.name}")


# Legacy format support - function-based plugin
def check_content(content: str) -> List[Dict[str, Any]]:
    """Legacy plugin function to check content."""
    results = []
    
    # Check for excessive emojis
    import re
    emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]+')
    emojis = emoji_pattern.findall(content)
    if len(emojis) > 10:
        results.append({
            "rule": "excessive_emojis",
            "description": f"Found {len(emojis)} emojis in the content, consider reducing for a more professional appearance",
            "severity": "low",
            "position": 0
        })
    
    return results

def register_rules():
    """Legacy way to register rules."""
    return [
        {
            "name": "clickbait_title",
            "pattern": r"\b(you won't believe|mind-blowing|jaw-dropping|amazing|unbelievable)\b",
            "description": "Clickbait title patterns detected",
            "severity": "medium"
        }
    ]
