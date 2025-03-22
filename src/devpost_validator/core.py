from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Set, Callable
import os
import tempfile
import git
import shutil
import re
from urllib.parse import urlparse
import json
import statistics
from enum import Enum
from pathlib import Path
import uuid
from collections import Counter
import math

from devpost_validator.github_analyzer import GitHubAnalyzer
from devpost_validator.ai_detector import AIDetector
from devpost_validator.plagiarism_checker import PlagiarismChecker
from devpost_validator.rule_engine import RuleEngine
from devpost_validator.config_manager import ConfigManager, HackathonConfig, ValidationThresholds, ValidationFeatures
from devpost_validator.devpost_analyzer import DevPostAnalyzer
from devpost_validator.code_analyzer import CodeAnalyzer
from devpost_validator.team_analyzer import TeamAnalyzer
from devpost_validator.report_generator import ReportGenerator
from devpost_validator.commit_analyzer import CommitAnalyzer
from devpost_validator.technology_analyzer import TechnologyAnalyzer
from devpost_validator.secret_analyzer import SecretAnalyzer


class ValidationCategory(str, Enum):
    PASSED = "PASSED"
    NEEDS_REVIEW = "NEEDS REVIEW"
    FAILED = "FAILED"


class ValidationPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ValidationItem:
    def __init__(self, message: str, priority: ValidationPriority, category: str, details: Optional[Dict] = None):
        self.message = message
        self.priority = priority
        self.category = category
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)
        self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message,
            "priority": self.priority,
            "category": self.category,
            "details": self.details,
            "timestamp": self.timestamp
        }


class ValidationScore:
    def __init__(self):
        self.timeline_score = 0.0
        self.code_authenticity_score = 0.0
        self.rule_compliance_score = 0.0
        self.plagiarism_score = 0.0
        self.team_compliance_score = 0.0
        self.complexity_score = 0.0
        self.technology_score = 0.0
        self.commit_quality_score = 0.0
        self.secret_security_score = 1.0  # Default to 1.0 (perfect score)
        self.overall_score = 0.0
        self.category = ValidationCategory.FAILED

    def calculate_overall_score(self, weights: Dict[str, float] = None):
        if not weights:
            weights = {
                "timeline": 0.20,
                "code_authenticity": 0.20,
                "rule_compliance": 0.15,
                "plagiarism": 0.10,
                "team_compliance": 0.10,
                "complexity": 0.10,
                "technology": 0.10,
                "commit_quality": 0.05
            }

        scores = {
            "timeline": self.timeline_score,
            "code_authenticity": self.code_authenticity_score,
            "rule_compliance": self.rule_compliance_score,
            "plagiarism": self.plagiarism_score,
            "team_compliance": self.team_compliance_score,
            "complexity": self.complexity_score,
            "technology": self.technology_score,
            "commit_quality": self.commit_quality_score
        }

        self.overall_score = sum(weights.get(key, 0) * value for key, value in scores.items())
        return self.overall_score

    def determine_category(self, thresholds: ValidationThresholds):
        if self.overall_score >= thresholds.pass_threshold:
            self.category = ValidationCategory.PASSED
        elif self.overall_score >= thresholds.review_threshold:
            self.category = ValidationCategory.NEEDS_REVIEW
        else:
            self.category = ValidationCategory.FAILED

        return self.category

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timeline_score": self.timeline_score,
            "code_authenticity_score": self.code_authenticity_score,
            "rule_compliance_score": self.rule_compliance_score,
            "plagiarism_score": self.plagiarism_score,
            "team_compliance_score": self.team_compliance_score,
            "complexity_score": self.complexity_score,
            "technology_score": self.technology_score,
            "commit_quality_score": self.commit_quality_score,
            "secret_security_score": self.secret_security_score,
            "overall_score": self.overall_score,
            "category": self.category
        }


class ValidationResult:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.github_results = {}
        self.devpost_results = {}
        self.ai_detection_results = []
        self.plagiarism_results = {}
        self.rule_violations = []
        self.code_complexity_results = {}
        self.commit_analysis_results = {}
        self.technology_analysis_results = {}
        self.team_analysis_results = {}
        self.secret_analysis_results = {}  # Add new field for secret analysis
        self.created_during_hackathon = False
        self.failures = []
        self.warnings = []
        self.passes = []
        self.timestamps = {
            "validation_start": datetime.now(timezone.utc),
            "validation_end": None
        }
        self.metrics = {}
        self.scores = ValidationScore()
        self.report = {}

    def add_pass(self, message: str, priority: ValidationPriority = ValidationPriority.MEDIUM,
                 details: Optional[Dict] = None):
        self.passes.append(ValidationItem(message, priority, "pass", details))

    def add_warning(self, message: str, priority: ValidationPriority = ValidationPriority.MEDIUM,
                    details: Optional[Dict] = None):
        self.warnings.append(ValidationItem(message, priority, "warning", details))

    def add_failure(self, message: str, priority: ValidationPriority = ValidationPriority.HIGH,
                    details: Optional[Dict] = None):
        self.failures.append(ValidationItem(message, priority, "failure", details))

    def complete_validation(self):
        self.timestamps["validation_end"] = datetime.now(timezone.utc)

    def get_validation_duration(self) -> float:
        if not self.timestamps["validation_end"]:
            self.complete_validation()

        start = self.timestamps["validation_start"]
        end = self.timestamps["validation_end"]

        return (end - start).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "github_results": self.github_results,
            "devpost_results": self.devpost_results,
            "ai_detection_results": self.ai_detection_results,
            "plagiarism_results": self.plagiarism_results,
            "rule_violations": self.rule_violations,
            "code_complexity_results": self.code_complexity_results,
            "commit_analysis_results": self.commit_analysis_results,
            "technology_analysis_results": self.technology_analysis_results,
            "team_analysis_results": self.team_analysis_results,
            "secret_analysis_results": self.secret_analysis_results,  # Include secret analysis in export
            "created_during_hackathon": self.created_during_hackathon,
            "failures": [f.to_dict() for f in self.failures],
            "warnings": [w.to_dict() for w in self.warnings],
            "passes": [p.to_dict() for p in self.passes],
            "timestamps": self.timestamps,
            "metrics": self.metrics,
            "scores": self.scores.to_dict(),
            "report": self.report
        }

    def save_to_file(self, filepath: str) -> bool:
        try:
            with open(filepath, 'w') as f:
                json.dump(self.to_dict(), f, indent=2, default=str)
            return True
        except Exception:
            return False


class DevPostValidator:
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token
        self.github_analyzer = GitHubAnalyzer(github_token) if github_token else None
        self.ai_detector = AIDetector()
        self.plagiarism_checker = PlagiarismChecker()
        self.rule_engine = RuleEngine()
        self.config_manager = ConfigManager()
        self.devpost_analyzer = DevPostAnalyzer()
        self.code_analyzer = CodeAnalyzer()
        self.team_analyzer = TeamAnalyzer()
        self.report_generator = ReportGenerator()
        self.commit_analyzer = CommitAnalyzer()
        self.technology_analyzer = TechnologyAnalyzer()
        self.secret_analyzer = SecretAnalyzer()  # Add secret analyzer
        self.current_config = None
        self.validation_history = []

    def set_github_token(self, token: str, username: str):
        self.github_token = token
        self.github_analyzer = GitHubAnalyzer(token)
        return self.config_manager.set_github_token(token, username)

    def get_github_token(self, username: str) -> Optional[str]:
        return self.config_manager.get_github_token(username)

    def verify_github_token(self) -> Dict:
        if not self.github_analyzer:
            return {"valid": False, "error": "GitHub token not set"}
        return self.github_analyzer.check_token_validity()

    def set_hackathon_config(self, config: HackathonConfig):
        self.current_config = config

    def load_hackathon_config(self, name: str) -> Optional[HackathonConfig]:
        config = self.config_manager.load_hackathon_config(name)
        if (config):
            self.current_config = config
        return config

    def validate_project(self, github_url: str, devpost_url: Optional[str] = None, analyze_secrets: bool = False) -> ValidationResult:
        result = ValidationResult()

        if not self.github_analyzer:
            result.add_failure("GitHub token not set. Unable to analyze GitHub repository.",
                               ValidationPriority.CRITICAL)
            return result

        if not self.current_config:
            result.add_warning("Hackathon configuration not set. Using default values.", ValidationPriority.MEDIUM)
            start_date = datetime.now(timezone.utc)
            end_date = datetime.now(timezone.utc)
            thresholds = ValidationThresholds()
            weights = {
                "timeline": 0.20,
                "code_authenticity": 0.20,
                "rule_compliance": 0.15,
                "plagiarism": 0.10,
                "team_compliance": 0.10,
                "complexity": 0.10,
                "technology": 0.10,
                "commit_quality": 0.05
            }
            features = ValidationFeatures()
        else:
            start_date = self.current_config.start_date
            end_date = self.current_config.end_date
            thresholds = self.current_config.validation_thresholds
            weights = self.current_config.score_weights
            features = self.current_config.validation_features

        repo_result = self.github_analyzer.get_repository(github_url)

        if repo_result.get("status") != "success":
            result.add_failure(
                repo_result.get("error", f"Unable to access GitHub repository: {github_url}"),
                ValidationPriority.CRITICAL
            )
            result.github_results = {
                "error": repo_result.get("error", "Unknown error"),
                "status": repo_result.get("status", "error")
            }
            result.report = self._generate_report(result)
            result.complete_validation()
            return result

        result.github_results = self.github_analyzer.analyze_repository(repo_result, start_date, end_date)

        if "error" in result.github_results:
            result.add_failure(
                result.github_results.get("error", f"Error analyzing GitHub repository"),
                ValidationPriority.CRITICAL
            )
            result.report = self._generate_report(result)
            result.complete_validation()
            return result

        result.created_during_hackathon = result.github_results.get("created_during_hackathon", False)

        repo = repo_result["repo"]
        temp_dir = tempfile.mkdtemp()
        ai_score = 0.0

        try:
            git.Repo.clone_from(repo["clone_url"], temp_dir)

            result.ai_detection_results, ai_score = self.ai_detector.analyze_repo_content(temp_dir)

            if features.analyze_code_complexity:
                result.code_complexity_results = self.code_analyzer.analyze_repo(temp_dir)

            if features.analyze_technology_stack:
                result.technology_analysis_results = self.technology_analyzer.analyze_repo(temp_dir)

            rule_violations = []
            for root, _, files in os.walk(temp_dir):
                if ".git" in root:
                    continue

                for file in files:
                    file_path = os.path.join(root, file)

                    if self._is_binary_file(file_path):
                        continue

                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                            violations = self.rule_engine.check_content(content)
                            if violations:
                                rel_path = os.path.relpath(file_path, temp_dir)
                                for v in violations:
                                    v["file"] = rel_path
                                rule_violations.extend(violations)
                    except Exception:
                        pass

            result.rule_violations = rule_violations

            if features.analyze_commit_patterns:
                repo_obj = git.Repo(temp_dir)
                result.commit_analysis_results = self.commit_analyzer.analyze_commits(repo_obj, start_date, end_date)

 
            if analyze_secrets and features.detect_security_issues:
                secret_results = self.secret_analyzer.analyze_repo(temp_dir)
                result.secret_analysis_results = secret_results
 
                result.scores.secret_security_score = self.secret_analyzer.get_risk_score(secret_results)

 
                if secret_results.get("secrets_found", False):
                    result.add_warning(
                        f"Found {secret_results['total_secrets']} potential secrets or sensitive data in the repository",
                        ValidationPriority.HIGH if secret_results.get("critical_secrets", 0) > 0 else ValidationPriority.MEDIUM,
                        {"secret_count": secret_results['total_secrets']}
                    )

                    if secret_results.get("critical_secrets", 0) > 0:
                        result.add_failure(
                            f"Found {secret_results['critical_secrets']} critical secrets that pose significant security risks",
                            ValidationPriority.CRITICAL,
                            {"critical_secrets": secret_results['critical_secrets']}
                        )

        except Exception as e:
            result.add_failure(f"Error cloning or analyzing repository: {str(e)}", ValidationPriority.HIGH)
        finally:
            shutil.rmtree(temp_dir)

        if devpost_url:
            try:
                result.devpost_results = self.devpost_analyzer.analyze_submission(devpost_url)

                if features.check_plagiarism:
                    result.plagiarism_results = self.plagiarism_checker.check_devpost_project(
                        devpost_url,
                        team_size=self.current_config.max_team_size if self.current_config else None,
                        required_technologies=self.current_config.required_technologies if self.current_config else None
                    )

                if features.analyze_team_composition and "team_members" in result.devpost_results:
                    result.team_analysis_results = self.team_analyzer.analyze_team(
                        result.devpost_results["team_members"],
                        result.github_results.get("contributors", []),
                        result.commit_analysis_results.get("contributor_stats", []) if hasattr(result,
                                                                                               "commit_analysis_results") else []
                    )
            except Exception as e:
                result.add_failure(f"Error analyzing DevPost submission: {str(e)}", ValidationPriority.MEDIUM)

        self._calculate_scores(result, ai_score)

        self._validate_results(result, features)

        result.scores.calculate_overall_score(weights)
        result.scores.determine_category(thresholds)

        result.report = self._generate_report(result)

        result.complete_validation()
        self.validation_history.append({
            "id": result.id,
            "github_url": github_url,
            "devpost_url": devpost_url,
            "timestamp": result.timestamps["validation_end"],
            "category": result.scores.category,
            "overall_score": result.scores.overall_score
        })

        return result

    def _validate_results(self, result: ValidationResult, features: ValidationFeatures):
        if "warning_flags" in result.github_results:
            for warning in result.github_results["warning_flags"]:
                result.add_warning(warning, ValidationPriority.MEDIUM)

        if not result.created_during_hackathon:
            result.add_failure("Repository was created outside the hackathon period", ValidationPriority.HIGH)
        else:
            result.add_pass("Repository was created during the hackathon period", ValidationPriority.HIGH)

        if result.github_results.get("commits_during_hackathon", 0) == 0:
            result.add_failure("No commits were made during the hackathon period", ValidationPriority.HIGH)
        else:
            result.add_pass(
                f"{result.github_results.get('commits_during_hackathon', 0)} commits were made during the hackathon period",
                ValidationPriority.MEDIUM
            )

        if self.current_config and not self.current_config.allow_ai_tools:
            ai_detection_count = len(result.ai_detection_results)
            if ai_detection_count > 10:
                result.add_failure(
                    f"Found {ai_detection_count} indicators of AI-generated code",
                    ValidationPriority.HIGH
                )
            elif ai_detection_count > 0:
                result.add_warning(
                    f"Found {ai_detection_count} potential indicators of AI-generated code",
                    ValidationPriority.MEDIUM
                )
            else:
                result.add_pass("No indicators of AI-generated code were found", ValidationPriority.MEDIUM)

        if len(result.rule_violations) > 10:
            result.add_failure(
                f"Found {len(result.rule_violations)} rule violations",
                ValidationPriority.MEDIUM
            )
        elif len(result.rule_violations) > 0:
            result.add_warning(
                f"Found {len(result.rule_violations)} rule violations",
                ValidationPriority.LOW
            )
        else:
            result.add_pass("No rule violations were found", ValidationPriority.LOW)

        if features.analyze_technology_stack and self.current_config and self.current_config.required_technologies:
            tech_results = result.technology_analysis_results
            if tech_results and "missing_required" in tech_results:
                missing = tech_results["missing_required"]
                if missing:
                    result.add_failure(
                        f"Missing required technologies: {', '.join(missing)}",
                        ValidationPriority.HIGH
                    )
                else:
                    result.add_pass("All required technologies are used in the project", ValidationPriority.MEDIUM)

        if features.analyze_technology_stack and self.current_config and self.current_config.disallowed_technologies:
            tech_results = result.technology_analysis_results
            if tech_results and "forbidden_used" in tech_results:
                forbidden = tech_results["forbidden_used"]
                if forbidden:
                    result.add_failure(
                        f"Using disallowed technologies: {', '.join(forbidden)}",
                        ValidationPriority.HIGH
                    )
                else:
                    result.add_pass("No disallowed technologies are used in the project", ValidationPriority.MEDIUM)

        if features.analyze_code_complexity and result.code_complexity_results:
            complexity = result.code_complexity_results
            if complexity.get("average_complexity", 0) > 25:
                result.add_warning(
                    f"Code has high average complexity ({complexity.get('average_complexity', 0):.1f})",
                    ValidationPriority.LOW
                )
            elif complexity.get("average_complexity", 0) < 5:
                result.add_warning(
                    f"Code has suspiciously low complexity ({complexity.get('average_complexity', 0):.1f}), which may indicate copied code",
                    ValidationPriority.LOW
                )

        if hasattr(result, 'commit_analysis_results') and result.commit_analysis_results:
            commits = result.commit_analysis_results
            if commits.get("suspicious_patterns", False):
                result.add_warning(
                    "Suspicious commit patterns detected (e.g., large code dumps, unusual timing)",
                    ValidationPriority.MEDIUM,
                    commits.get("pattern_details", {})
                )

            if commits.get("commit_distribution_score", 1.0) < 0.3:
                result.add_warning(
                    "Commits are poorly distributed across the hackathon period",
                    ValidationPriority.LOW
                )

        if hasattr(result, 'team_analysis_results') and result.team_analysis_results:
            team = result.team_analysis_results
            if team.get("contribution_imbalance", False):
                result.add_warning(
                    "Team contribution appears significantly imbalanced",
                    ValidationPriority.LOW,
                    team.get("contribution_details", {})
                )

            if team.get("github_team_mismatch", False):
                result.add_warning(
                    "DevPost team members don't match GitHub contributors",
                    ValidationPriority.MEDIUM,
                    team.get("mismatch_details", {})
                )

        if result.devpost_results:
            ai_prob = result.devpost_results.get("ai_content_probability", 0)
            if ai_prob > 0.7:
                result.add_failure(
                    f"DevPost description likely AI-generated ({ai_prob * 100:.1f}%)",
                    ValidationPriority.MEDIUM
                )
            elif ai_prob > 0.4:
                result.add_warning(
                    f"DevPost description may contain AI-generated content ({ai_prob * 100:.1f}%)",
                    ValidationPriority.LOW
                )
            else:
                result.add_pass("DevPost description appears to be human-written", ValidationPriority.LOW)

            if result.devpost_results.get("duplicate_submission", False):
                result.add_failure(
                    "Project appears to be submitted to multiple hackathons",
                    ValidationPriority.HIGH
                )

        if features.detect_security_issues and result.secret_analysis_results and result.secret_analysis_results.get("secrets_found", False):
            critical_count = result.secret_analysis_results.get("critical_secrets", 0)
            high_risk_count = result.secret_analysis_results.get("high_risk_secrets", 0)

            if critical_count > 0:
                result.add_failure(
                    f"Critical security issue: {critical_count} critical severity secrets detected",
                    ValidationPriority.CRITICAL
                )
            elif high_risk_count > 0:
                result.add_warning(
                    f"Security warning: {high_risk_count} high-risk secrets or sensitive files detected",
                    ValidationPriority.HIGH
                )
            elif result.secret_analysis_results.get("total_secrets", 0) > 0:
                result.add_warning(
                    f"Found {result.secret_analysis_results.get('total_secrets', 0)} potential secrets or sensitive information",
                    ValidationPriority.MEDIUM
                )

    def _calculate_scores(self, result: ValidationResult, ai_score: float):
        github_results = result.github_results

        timeline_factors = {
            "created_during_hackathon": 60,
            "commits_ratio": 30,
            "commit_distribution": 10,
        }

        timeline_score = 0.0

        if result.created_during_hackathon:
            timeline_score += timeline_factors["created_during_hackathon"]

        total_commits = github_results.get("total_commits", 0)
        hackathon_commits = github_results.get("commits_during_hackathon", 0)

        if total_commits > 0:
            commit_ratio = hackathon_commits / total_commits
            timeline_score += timeline_factors["commits_ratio"] * commit_ratio

        if hasattr(result,
                   'commit_analysis_results') and result.commit_analysis_results and "commit_distribution_score" in result.commit_analysis_results:
            distribution_score = result.commit_analysis_results.get("commit_distribution_score", 0.0)
            timeline_score += timeline_factors["commit_distribution"] * distribution_score

        code_authenticity_score = (1.0 - ai_score) * 100

        rule_compliance_score = 100.0
        if len(result.rule_violations) > 0:
            violation_penalty = min(100, 100 * (1 - math.exp(-0.1 * len(result.rule_violations))))
            rule_compliance_score = max(0, rule_compliance_score - violation_penalty)

        plagiarism_score = 100.0
        if result.devpost_results:
            ai_content_prob = result.devpost_results.get("ai_content_probability", 0.0)
            plagiarism_score = max(0, 100.0 - (ai_content_prob * 100.0))

            if result.devpost_results.get("duplicate_submission", False):
                plagiarism_score = max(0, plagiarism_score - 50.0)

        team_compliance_score = 100.0
        if hasattr(result, 'team_analysis_results') and result.team_analysis_results:
            if result.team_analysis_results.get("contribution_imbalance", False):
                imbalance_factor = result.team_analysis_results.get("imbalance_factor", 0.0)
                team_compliance_score -= 40.0 * imbalance_factor

            if result.team_analysis_results.get("github_team_mismatch", False):
                mismatch_ratio = result.team_analysis_results.get("mismatch_ratio", 0.0)
                team_compliance_score -= 50.0 * mismatch_ratio

            if "plagiarism_results" in result and "team_compliance" in result.plagiarism_results:
                team_comp = result.plagiarism_results["team_compliance"]
                if not team_comp.get("size_compliant", True):
                    team_compliance_score -= 50.0

        complexity_score = 85.0
        if hasattr(result, 'code_complexity_results') and result.code_complexity_results:
            avg_complexity = result.code_complexity_results.get("average_complexity", 10)

            if avg_complexity < 5:
                complexity_score = 60.0 + (avg_complexity / 5.0) * 25.0
            elif avg_complexity <= 15:
                complexity_score = 85.0 + ((15 - avg_complexity) / 10.0) * 15.0
            elif avg_complexity <= 25:
                complexity_score = 85.0 - ((avg_complexity - 15) / 10.0) * 25.0
            else:
                complexity_score = 60.0 - min(60.0, ((avg_complexity - 25) / 15.0) * 60.0)

        technology_score = 80.0
        if hasattr(result, 'technology_analysis_results') and result.technology_analysis_results:
            tech_results = result.technology_analysis_results

            if self.current_config and self.current_config.required_technologies:
                required_count = len(self.current_config.required_technologies)
                missing_count = len(tech_results.get("missing_required", []))

                if required_count > 0:
                    compliance_ratio = (required_count - missing_count) / required_count
                    technology_score = compliance_ratio * 100.0

            if self.current_config and self.current_config.disallowed_technologies:
                forbidden_used = len(tech_results.get("forbidden_used", []))
                if forbidden_used > 0:
                    technology_score = max(0, technology_score - (40.0 * forbidden_used))

            tech_diversity = tech_results.get("technology_diversity", 0.0)
            technology_score = min(100, technology_score + (tech_diversity * 10.0))

        commit_quality_score = 75.0
        if hasattr(result, 'commit_analysis_results') and result.commit_analysis_results:
            commits = result.commit_analysis_results

            if commits.get("suspicious_patterns", False):
                commit_quality_score -= 40.0

            message_quality = commits.get("message_quality", 0.5)
            commit_quality_score = commit_quality_score * 0.6 + (message_quality * 100.0) * 0.4

            distribution_score = commits.get("commit_distribution_score", 0.5)
            commit_quality_score = commit_quality_score * 0.7 + (distribution_score * 100.0) * 0.3

            frequency_score = commits.get("frequency_score", 0.5)
            commit_quality_score = commit_quality_score * 0.8 + (frequency_score * 100.0) * 0.2

 
        if hasattr(result, "secret_analysis_results") and result.secret_analysis_results:
 
 
            result.scores.secret_security_score = result.scores.secret_security_score * 100
            
 
 
            if self.current_config and hasattr(self.current_config, "score_weights"):
                weights = self.current_config.score_weights.copy()
                
 
 
                if "secret_security" not in weights:
 
                    reduction_factor = 0.95  # Reduce other weights by 5%
                    new_weights = {}
                    
                    for key, value in weights.items():
                        new_weights[key] = value * reduction_factor
                    
 
                    new_weights["secret_security"] = 1.0 - sum(new_weights.values())
                    weights = new_weights
                
 
                result.score_weights = weights
        else:
 
            result.scores.secret_security_score = 100.0

        result.scores.timeline_score = timeline_score
        result.scores.code_authenticity_score = code_authenticity_score
        result.scores.rule_compliance_score = rule_compliance_score
        result.scores.plagiarism_score = plagiarism_score
        result.scores.team_compliance_score = team_compliance_score
        result.scores.complexity_score = complexity_score
        result.scores.technology_score = technology_score
        result.scores.commit_quality_score = commit_quality_score

        result.metrics = {
            "total_commits": total_commits,
            "hackathon_commits": hackathon_commits,
            "commit_ratio": hackathon_commits / total_commits if total_commits > 0 else 0,
            "ai_indicators_count": len(result.ai_detection_results),
            "rule_violations_count": len(result.rule_violations),
            "validation_duration": result.get_validation_duration(),
        }

        if hasattr(result, 'code_complexity_results') and result.code_complexity_results:
            result.metrics["average_complexity"] = result.code_complexity_results.get("average_complexity", 0)

    def validate_urls(self, urls: List[str]) -> List[ValidationResult]:
        results = []
        for url in urls:
            github_url = None
            devpost_url = None

            if self.is_github_url(url):
                github_url = url
            elif self.is_devpost_url(url):
                devpost_url = url
                github_url = self.extract_github_url(devpost_url)

            if github_url:
                result = self.validate_project(github_url, devpost_url)
                results.append(result)

        return results

    def _is_binary_file(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1024)
                return False
        except UnicodeDecodeError:
            return True

    def _generate_report(self, result: ValidationResult) -> Dict[str, Any]:
        report = {
            "summary": {
                "id": result.id,
                "category": result.scores.category,
                "overall_score": f"{result.scores.overall_score:.1f}%",
                "warnings_count": len(result.warnings),
                "failures_count": len(result.failures),
                "passes_count": len(result.passes),
                "validation_duration_seconds": result.get_validation_duration(),
            },
            "scores": {
                "timeline": f"{result.scores.timeline_score:.1f}%",
                "code_authenticity": f"{result.scores.code_authenticity_score:.1f}%",
                "rule_compliance": f"{result.scores.rule_compliance_score:.1f}%",
                "plagiarism": f"{result.scores.plagiarism_score:.1f}%",
                "team_compliance": f"{result.scores.team_compliance_score:.1f}%",
                "complexity": f"{result.scores.complexity_score:.1f}%",
                "technology": f"{result.scores.technology_score:.1f}%",
                "commit_quality": f"{result.scores.commit_quality_score:.1f}%",
                "secret_security": f"{result.scores.secret_security_score:.1f}%",
            },
            "timeline": {
                "created_during_hackathon": result.created_during_hackathon,
                "repository_created": result.github_results.get("created_at", "Unknown"),
                "last_updated": result.github_results.get("last_updated", "Unknown"),
                "total_commits": result.github_results.get("total_commits", 0),
                "hackathon_commits": result.github_results.get("commits_during_hackathon", 0),
            },
            "failures": [f.to_dict() for f in result.failures],
            "warnings": [w.to_dict() for w in result.warnings],
            "passes": [p.to_dict() for p in result.passes],
            "metrics": result.metrics,
            "ai_indicators": result.ai_detection_results[:5],
            "rule_violations": result.rule_violations[:5],
        }

        if "commit_timeline" in result.github_results:
            report["commit_timeline"] = result.github_results["commit_timeline"][:10]

        if result.devpost_results:
            report["devpost"] = {
                "title": result.devpost_results.get("title", ""),
                "ai_content_probability": f"{result.devpost_results.get('ai_content_probability', 0) * 100:.1f}%",
                "team_members": result.devpost_results.get("team_members", []),
                "technologies": result.devpost_results.get("technologies", []),
                "duplicate_submission": result.devpost_results.get("duplicate_submission", False),
            }

        if hasattr(result, 'code_complexity_results') and result.code_complexity_results:
            report["code_complexity"] = {
                "average_complexity": f"{result.code_complexity_results.get('average_complexity', 0):.1f}",
                "most_complex_files": result.code_complexity_results.get("most_complex_files", [])[:3],
            }

        if hasattr(result, 'technology_analysis_results') and result.technology_analysis_results:
            report["technology_stack"] = {
                "detected_technologies": result.technology_analysis_results.get("detected_technologies", []),
                "missing_required": result.technology_analysis_results.get("missing_required", []),
                "forbidden_used": result.technology_analysis_results.get("forbidden_used", []),
            }

        if hasattr(result, 'team_analysis_results') and result.team_analysis_results:
            report["team_analysis"] = {
                "contribution_balance": f"{result.team_analysis_results.get('contribution_balance', 0) * 100:.1f}%",
                "github_team_match": f"{result.team_analysis_results.get('github_team_match', 0) * 100:.1f}%",
            }

 
        if hasattr(result, "secret_analysis_results") and result.secret_analysis_results:
            report["secrets_analysis"] = {
                "total_secrets": result.secret_analysis_results.get("total_secrets", 0),
                "critical_secrets": result.secret_analysis_results.get("critical_secrets", 0),
                "high_risk_secrets": result.secret_analysis_results.get("high_risk_secrets", 0),
                "medium_risk_secrets": result.secret_analysis_results.get("medium_risk_secrets", 0),
                "security_score": f"{result.scores.secret_security_score:.1f}%",
                "findings": result.secret_analysis_results.get("findings", [])[:5],  # Show only top 5
                "sensitive_files": result.secret_analysis_results.get("sensitive_files", [])[:5],  # Show only top 5
            }

        return report

    def export_report_html(self, result: ValidationResult, filepath: str) -> bool:
        return self.report_generator.generate_html_report(result, filepath)

    def export_report_json(self, result: ValidationResult, filepath: str) -> bool:
        return result.save_to_file(filepath)

    def extract_github_url(self, devpost_url: str) -> Optional[str]:
        return self.devpost_analyzer.extract_github_url(devpost_url)

    def is_github_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc == "github.com" and len(parsed.path.strip("/").split("/")) >= 2

    def is_devpost_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc.endswith("devpost.com")

    def add_custom_rule(self, name: str, pattern: str, description: str) -> bool:
        try:
            return self.rule_engine.add_rule(name=name, pattern=pattern, description=description)
        except Exception:
            return False

    def get_all_rules(self) -> List[Dict[str, str]]:
        return self.rule_engine.get_all_rules()

    def get_validation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.validation_history[-limit:]

    def load_plugin(self, plugin_path: str) -> bool:
        """
        Load a plugin into the validator.
        
        Args:
            plugin_path: Path to the plugin file
            
        Returns:
            True if plugin was loaded successfully, False otherwise
        """
        return self.rule_engine.load_plugin(plugin_path)
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a specific plugin by name.
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            True if plugin was unloaded successfully, False otherwise
        """
        return self.rule_engine.unload_plugin(plugin_name)
        
    def get_loaded_plugins(self):
        """Get all currently loaded plugins."""
        return self.rule_engine.get_loaded_plugins()
        
    def get_plugin_info(self):
        """Get detailed information about all loaded plugins."""
        return self.rule_engine.get_plugin_info()