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

Create custom plugins to extend validation capabilities:

```python
# myplugin.py
def register_rules():
    return [
        {
            "name": "custom_pattern",
            "pattern": r"specific pattern to detect",
            "description": "Description of what this pattern detects"
        }
    ]
```

Load the plugin:

```bash
devpost-validator load-plugin myplugin.py
```

## License

MIT