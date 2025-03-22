import json
import os
import keyring
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Set, Any


class ValidationThresholds(BaseModel):
    pass_threshold: float = 90.0
    review_threshold: float = 60.0


class ValidationFeatures(BaseModel):
    analyze_code_complexity: bool = True
    analyze_commit_patterns: bool = True
    analyze_technology_stack: bool = True
    analyze_team_composition: bool = True
    check_plagiarism: bool = True
    check_ai_content: bool = True
    export_detailed_report: bool = True
    enable_batch_processing: bool = True
    strict_timeline_validation: bool = True
    track_external_dependencies: bool = True
    detect_abandoned_branches: bool = False
    analyze_code_quality: bool = True
    analyze_documentation: bool = True
    detect_security_issues: bool = True
    generate_recommendations: bool = True


class ReportSettings(BaseModel):
    include_ai_detection: bool = True
    include_technology_analysis: bool = True
    include_commit_analysis: bool = True
    include_team_analysis: bool = True
    include_code_complexity: bool = True
    include_plagiarism_results: bool = True
    include_metrics: bool = True
    include_recommendations: bool = True
    include_security_analysis: bool = True
    include_external_dependencies: bool = True
    max_ai_detections_shown: int = 10
    max_rule_violations_shown: int = 10
    max_commits_shown: int = 20
    format: str = "html"
    custom_css: Optional[str] = None
    custom_logo: Optional[str] = None
    include_graphs: bool = True


class HackathonConfig(BaseModel):
    name: str
    start_date: datetime
    end_date: datetime
    required_technologies: List[str] = Field(default_factory=list)
    disallowed_technologies: List[str] = Field(default_factory=list)
    max_team_size: Optional[int] = None
    allow_ai_tools: bool = False
    validation_thresholds: ValidationThresholds = Field(default_factory=ValidationThresholds)
    validation_features: ValidationFeatures = Field(default_factory=ValidationFeatures)
    report_settings: ReportSettings = Field(default_factory=ReportSettings)
    score_weights: Dict[str, float] = Field(default_factory=lambda: {
        "timeline": 0.20,
        "code_authenticity": 0.20,
        "rule_compliance": 0.15,
        "plagiarism": 0.10,
        "team_compliance": 0.10,
        "complexity": 0.10,
        "technology": 0.10,
        "commit_quality": 0.05
    })
    custom_rules: Dict[str, str] = Field(default_factory=dict)
    excluded_files: List[str] = Field(default_factory=list)
    excluded_directories: List[str] = Field(default_factory=list)
    technology_categories: Dict[str, List[str]] = Field(default_factory=dict)
    validation_notes: Optional[str] = None
    report_recipients: List[str] = Field(default_factory=list)
    minimum_repository_requirements: Dict[str, Any] = Field(default_factory=lambda: {
        "min_commits": 5,
        "min_files": 3,
        "min_contributors": 1,
        "readme_required": True,
        "license_required": False,
    })
    allowed_external_services: List[str] = Field(default_factory=list)

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


class BatchValidationSettings(BaseModel):
    max_concurrent_validations: int = 5
    timeout_seconds: int = 300
    retry_failed: bool = True
    max_retries: int = 3
    generate_summary_report: bool = True
    output_directory: str = "./validation_results"
    report_format: str = "html"
    include_individual_reports: bool = True


class GlobalSettings(BaseModel):
    default_config: str = "default"
    cache_duration_hours: int = 24
    enable_telemetry: bool = False
    log_level: str = "INFO"
    max_history_items: int = 100
    auto_update_check: bool = True
    custom_plugins_directory: Optional[str] = None
    default_report_directory: str = "./reports"
    default_batch_settings: BatchValidationSettings = Field(default_factory=BatchValidationSettings)
    rate_limit_threshold: int = 20
    enable_cloud_sync: bool = False
    cloud_sync_endpoint: Optional[str] = None
    allowed_export_formats: List[str] = Field(default=["html", "json", "markdown", "csv"])


class ConfigManager:
    SERVICE_NAME = "devpost-validator"
    CONFIG_DIR = Path.home() / ".devpost-validator"

    def __init__(self):
        self.CONFIG_DIR.mkdir(exist_ok=True)
        self.current_config = None
        self.global_settings = self._load_global_settings()

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

            if "validation_features" not in config_data:
                config_data["validation_features"] = ValidationFeatures().model_dump()

            if "report_settings" not in config_data:
                config_data["report_settings"] = ReportSettings().model_dump()

            if "score_weights" not in config_data:
                config_data["score_weights"] = {
                    "timeline": 0.20,
                    "code_authenticity": 0.20,
                    "rule_compliance": 0.15,
                    "plagiarism": 0.10,
                    "team_compliance": 0.10,
                    "complexity": 0.10,
                    "technology": 0.10,
                    "commit_quality": 0.05
                }

            config = HackathonConfig(**config_data)
            self.current_config = config
            return config

    def list_available_configs(self) -> List[str]:
        return [f.stem for f in self.CONFIG_DIR.glob("*.json") if f.stem != "global_settings"]

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

    def update_validation_features(self, name: str, features: ValidationFeatures) -> bool:
        config = self.load_hackathon_config(name)
        if not config:
            return False

        config.validation_features = features
        self.create_hackathon_config(config, name)
        return True

    def update_report_settings(self, name: str, settings: ReportSettings) -> bool:
        config = self.load_hackathon_config(name)
        if not config:
            return False

        config.report_settings = settings
        self.create_hackathon_config(config, name)
        return True

    def _load_global_settings(self) -> GlobalSettings:
        settings_path = self.CONFIG_DIR / "global_settings.json"
        if not settings_path.exists():
            settings = GlobalSettings()
            self._save_global_settings(settings)
            return settings

        with open(settings_path, 'r') as f:
            settings_data = json.load(f)
            return GlobalSettings(**settings_data)

    def _save_global_settings(self, settings: GlobalSettings) -> bool:
        settings_path = self.CONFIG_DIR / "global_settings.json"
        with open(settings_path, 'w') as f:
            f.write(settings.model_dump_json(indent=2))
        return True

    def update_global_settings(self, settings: GlobalSettings) -> bool:
        self.global_settings = settings
        return self._save_global_settings(settings)

    def create_default_config(self) -> bool:
        if self.load_hackathon_config("default"):
            return True

        now = datetime.now(timezone.utc)
        end = now + timezone.timedelta(days=3)

        config = HackathonConfig(
            name="Default Config",
            start_date=now,
            end_date=end,
            allow_ai_tools=False,
            validation_features=ValidationFeatures(),
            report_settings=ReportSettings()
        )

        self.create_hackathon_config(config, "default")
        return True

    def get_batch_settings(self) -> BatchValidationSettings:
        return self.global_settings.default_batch_settings

    def update_batch_settings(self, settings: BatchValidationSettings) -> bool:
        self.global_settings.default_batch_settings = settings
        return self._save_global_settings(self.global_settings)