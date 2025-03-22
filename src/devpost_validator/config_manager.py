import json
import os
import keyring
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict


class ValidationThresholds(BaseModel):
    pass_threshold: float = 90.0
    review_threshold: float = 60.0


class HackathonConfig(BaseModel):
    name: str
    start_date: datetime
    end_date: datetime
    required_technologies: List[str] = Field(default_factory=list)
    disallowed_technologies: List[str] = Field(default_factory=list)
    max_team_size: Optional[int] = None
    allow_ai_tools: bool = False
    validation_thresholds: ValidationThresholds = Field(default_factory=ValidationThresholds)
    score_weights: Dict[str, float] = Field(default_factory=lambda: {
        "timeline": 0.25,
        "code_authenticity": 0.30,
        "rule_compliance": 0.20,
        "plagiarism": 0.15,
        "team_compliance": 0.10
    })
    custom_rules: Dict[str, str] = Field(default_factory=dict)

    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

    @validator('start_date', 'end_date')
    def ensure_timezone(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @validator('score_weights')
    def validate_weights(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError('Score weights must sum to 1.0')
        return v


class ConfigManager:
    SERVICE_NAME = "devpost-validator"
    CONFIG_DIR = Path.home() / ".devpost-validator"

    def __init__(self):
        self.CONFIG_DIR.mkdir(exist_ok=True)
        self.current_config = None

    def set_github_token(self, token: str, username: str):
        keyring.set_password(self.SERVICE_NAME, username, token)
        return True

    def get_github_token(self, username: str) -> Optional[str]:
        return keyring.get_password(self.SERVICE_NAME, username)

    def create_hackathon_config(self, config: HackathonConfig, name: str) -> Path:
        config_path = self.CONFIG_DIR / f"{name}.json"

        with open(config_path, 'w') as f:
            f.write(config.model_dump_json(indent=2))

        self.current_config = config
        return config_path

    def load_hackathon_config(self, name: str) -> Optional[HackathonConfig]:
        config_path = self.CONFIG_DIR / f"{name}.json"

        if not config_path.exists():
            return None

        with open(config_path, 'r') as f:
            config_data = json.load(f)

            if isinstance(config_data["start_date"], str):
                config_data["start_date"] = datetime.fromisoformat(config_data["start_date"])
                if config_data["start_date"].tzinfo is None:
                    config_data["start_date"] = config_data["start_date"].replace(tzinfo=timezone.utc)

            if isinstance(config_data["end_date"], str):
                config_data["end_date"] = datetime.fromisoformat(config_data["end_date"])
                if config_data["end_date"].tzinfo is None:
                    config_data["end_date"] = config_data["end_date"].replace(tzinfo=timezone.utc)

            if "validation_thresholds" not in config_data:
                config_data["validation_thresholds"] = ValidationThresholds().model_dump()

            if "score_weights" not in config_data:
                config_data["score_weights"] = {
                    "timeline": 0.25,
                    "code_authenticity": 0.30,
                    "rule_compliance": 0.20,
                    "plagiarism": 0.15,
                    "team_compliance": 0.10
                }

            config = HackathonConfig(**config_data)
            self.current_config = config
            return config

    def list_available_configs(self) -> List[str]:
        return [f.stem for f in self.CONFIG_DIR.glob("*.json")]

    def update_validation_thresholds(self, name: str, pass_threshold: float, review_threshold: float) -> bool:
        config = self.load_hackathon_config(name)
        if not config:
            return False

        config.validation_thresholds.pass_threshold = pass_threshold
        config.validation_thresholds.review_threshold = review_threshold

        self.create_hackathon_config(config, name)
        return True

    def update_score_weights(self, name: str, weights: Dict[str, float]) -> bool:
        config = self.load_hackathon_config(name)
        if not config:
            return False

        total = sum(weights.values())
        if abs(total - 1.0) > 0.001:
            return False

        config.score_weights = weights
        self.create_hackathon_config(config, name)
        return True