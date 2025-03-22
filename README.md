# DevPost Validator

A Python CLI tool and library that helps hackathon organizers and judges validate DevPost submissions, detect AI-generated code, and ensure rule compliance.

## Features

- Verify GitHub repositories were created during the hackathon period
- Detect AI-generated code through pattern analysis
- Check for plagiarism in DevPost submissions
- Support for custom validation rules and plugins
- Secure storage of GitHub tokens
- Batch validation of multiple submissions
- Configurable hackathon parameters
- Comprehensive validation reports

## Installation

```bash
pip install devpost-validator
```

## Usage

### Setup

First, set up your GitHub token for API access:

```bash
devpost-validator setup
```

### Configure a Hackathon

Create a configuration for your hackathon:

```bash
devpost-validator config --name "MyHackathon2025" --start-date "2025-03-01" --end-date "2025-03-15"
```

### Validate a Submission

Validate a single GitHub repository or DevPost submission:

```bash
devpost-validator validate https://github.com/username/repo --config-name "MyHackathon2025" --username "yourusername"
```

### Batch Validation

Validate multiple submissions from a CSV or JSON file:

```bash
devpost-validator batch-validate submissions.csv --config-name "MyHackathon2025" --username "yourusername"
```

### Add Custom Rules

Add custom regex patterns to detect rule violations:

```bash
devpost-validator add-rule
```

## Library Usage

```python
from src.devpost_validator import DevPostValidator
from src.devpost_validator import HackathonConfig
from datetime import datetime

# Initialize validator
validator = DevPostValidator()

# Set GitHub token
validator.set_github_token("your-github-token", "your-username")

# Create and set hackathon config
config = HackathonConfig(
    name="MyHackathon",
    start_date=datetime(2025, 3, 1),
    end_date=datetime(2025, 3, 15),
    allow_ai_tools=False
)
validator.set_hackathon_config(config)

# Validate a project
result = validator.validate_project(
    github_url="https://github.com/username/repo",
    devpost_url="https://devpost.com/software/project"
)

# Check results
if result.passed:
    print("Project passed validation!")
else:
    print(f"Project failed validation. Warnings: {result.warnings}")
    print(f"AI score: {result.ai_score}")
```

## Plugin System

DevPost Validator supports a flexible plugin system that allows you to extend its validation capabilities in two ways:

### 1. Simple Function-Based Plugins (Legacy)

```python
# simple_plugin.py
def register_rules():
    return [
        {
            "name": "custom_pattern",
            "pattern": r"specific pattern to detect",
            "description": "Description of what this pattern detects",
            "severity": "medium"  # optional, defaults to "medium"
        }
    ]

# Optional: Add custom content validation logic
def check_content(content: str):
    results = []
    # Custom validation logic
    return results
```

### 2. Class-Based Plugins (Recommended)

For more complex plugins, we recommend that you use the class-based approach:

```python
# advanced_plugin.py
from devpost_validator.plugin_base import PluginBase

class MyCustomPlugin(PluginBase):
    def __init__(self):
        super().__init__("MyPlugin")  # Name is optional
    
    def initialize(self) -> bool:
        # Setup code here
        return True
        
    def register_rules(self):
        return [
            {
                "name": "advanced_pattern",
                "pattern": r"pattern to detect",
                "description": "What this pattern checks for",
                "severity": "high"
            }
        ]
    
    def check_content(self, content: str):
        results = []
        # Your custom validation logic here
        return results
        
    def cleanup(self):
        # Release resources when plugin is unloaded
        pass
```

### Loading Plugins

Load a plugin using the command line:

```bash
devpost-validator load-plugin /path/to/your/plugin.py
```

Or programmatically:

```python
from devpost_validator import RuleEngine

engine = RuleEngine()
engine.load_plugin("/path/to/your/plugin.py")
```

See the `/examples` directory for complete plugin examples.

## License

MIT