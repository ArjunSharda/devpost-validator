from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Tuple
import os
import tempfile
import git
import shutil
import re
from urllib.parse import urlparse
import json
from enum import Enum

from devpost_validator.github_analyzer import GitHubAnalyzer
from devpost_validator.ai_detector import AIDetector
from devpost_validator.plagiarism_checker import PlagiarismChecker
from devpost_validator.rule_engine import RuleEngine
from devpost_validator.config_manager import ConfigManager, HackathonConfig, ValidationThresholds
from devpost_validator.devpost_analyzer import DevPostAnalyzer


class ValidationCategory(str, Enum):
    PASSED = "PASSED"
    NEEDS_REVIEW = "NEEDS REVIEW"
    FAILED = "FAILED"


class ValidationScore:
    def __init__(self):
        self.timeline_score = 0.0
        self.code_authenticity_score = 0.0
        self.rule_compliance_score = 0.0
        self.plagiarism_score = 0.0
        self.team_compliance_score = 0.0
        self.overall_score = 0.0
        self.category = ValidationCategory.FAILED

    def calculate_overall_score(self, weights: Dict[str, float] = None):
        if not weights:
            weights = {
                "timeline": 0.25,
                "code_authenticity": 0.30,
                "rule_compliance": 0.20,
                "plagiarism": 0.15,
                "team_compliance": 0.10
            }

        self.overall_score = (
                weights["timeline"] * self.timeline_score +
                weights["code_authenticity"] * self.code_authenticity_score +
                weights["rule_compliance"] * self.rule_compliance_score +
                weights["plagiarism"] * self.plagiarism_score +
                weights["team_compliance"] * self.team_compliance_score
        )

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
            "overall_score": self.overall_score,
            "category": self.category
        }


class ValidationResult:
    def __init__(self):
        self.github_results = {}
        self.devpost_results = {}
        self.ai_detection_results = []
        self.plagiarism_results = {}
        self.rule_violations = []
        self.created_during_hackathon = False
        self.warnings = []
        self.failures = []
        self.passes = []
        self.scores = ValidationScore()
        self.report = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "github_results": self.github_results,
            "devpost_results": self.devpost_results,
            "ai_detection_results": self.ai_detection_results,
            "plagiarism_results": self.plagiarism_results,
            "rule_violations": self.rule_violations,
            "created_during_hackathon": self.created_during_hackathon,
            "warnings": self.warnings,
            "failures": self.failures,
            "passes": self.passes,
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
        self.current_config = None

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
        if config:
            self.current_config = config
        return config

    def validate_project(self, github_url: str, devpost_url: Optional[str] = None) -> ValidationResult:
        result = ValidationResult()

        if not self.github_analyzer:
            result.failures.append("GitHub token not set. Unable to analyze GitHub repository.")
            return result

        if not self.current_config:
            result.warnings.append("Hackathon configuration not set. Using default values.")
            start_date = datetime.now(timezone.utc)
            end_date = datetime.now(timezone.utc)
            thresholds = ValidationThresholds()
            weights = {"timeline": 0.25, "code_authenticity": 0.30, "rule_compliance": 0.20, "plagiarism": 0.15,
                       "team_compliance": 0.10}
        else:
            start_date = self.current_config.start_date
            end_date = self.current_config.end_date
            thresholds = self.current_config.validation_thresholds
            weights = self.current_config.score_weights

        repo_result = self.github_analyzer.get_repository(github_url)

        if repo_result.get("status") != "success":
            result.failures.append(repo_result.get("error", f"Unable to access GitHub repository: {github_url}"))
            result.github_results = {
                "error": repo_result.get("error", "Unknown error"),
                "status": repo_result.get("status", "error")
            }
            result.report = self._generate_report(result)
            return result

        result.github_results = self.github_analyzer.analyze_repository(repo_result, start_date, end_date)

        if "error" in result.github_results:
            result.failures.append(result.github_results.get("error", f"Error analyzing GitHub repository"))
            result.report = self._generate_report(result)
            return result

        result.created_during_hackathon = result.github_results.get("created_during_hackathon", False)

        repo = repo_result["repo"]
        temp_dir = tempfile.mkdtemp()
        try:
            git.Repo.clone_from(repo.clone_url, temp_dir)

            result.ai_detection_results, ai_score = self.ai_detector.analyze_repo_content(temp_dir)

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

        except Exception as e:
            result.failures.append(f"Error cloning or analyzing repository: {str(e)}")
        finally:
            shutil.rmtree(temp_dir)

        if devpost_url:
            try:
                result.devpost_results = self.devpost_analyzer.analyze_submission(devpost_url)
                result.plagiarism_results = self.plagiarism_checker.check_devpost_project(
                    devpost_url,
                    team_size=self.current_config.max_team_size if self.current_config else None,
                    required_technologies=self.current_config.required_technologies if self.current_config else None
                )
            except Exception as e:
                result.failures.append(f"Error analyzing DevPost submission: {str(e)}")

        self._calculate_scores(result, ai_score)

        if "warning_flags" in result.github_results:
            result.warnings.extend(result.github_results["warning_flags"])

        if not result.created_during_hackathon:
            result.failures.append("Repository was created outside the hackathon period")
        else:
            result.passes.append("Repository was created during the hackathon period")

        if result.github_results.get("commits_during_hackathon", 0) == 0:
            result.failures.append("No commits were made during the hackathon period")
        else:
            result.passes.append(
                f"{result.github_results.get('commits_during_hackathon', 0)} commits were made during the hackathon period")

        if self.current_config and not self.current_config.allow_ai_tools and ai_score >= 0.5:
            result.failures.append(f"AI detection score of {ai_score:.2f} exceeds threshold of 0.5")

        if devpost_url:
            self._validate_devpost_requirements(result)

        result.scores.calculate_overall_score(weights)
        result.scores.determine_category(thresholds)

        result.report = self._generate_report(result)

        return result

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

        commit_timeline = github_results.get("commit_timeline", [])
        if commit_timeline:
            first_day = 0
            last_day = 0
            middle_days = 0

            if self.current_config:
                start_date = self.current_config.start_date
                end_date = self.current_config.end_date

                hackathon_duration = (end_date - start_date).days + 1
                if hackathon_duration > 0:
                    for commit in commit_timeline:
                        if commit.get("during_hackathon", False):
                            commit_date = commit.get("date")
                            if isinstance(commit_date, str):
                                commit_date = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))

                            day_of_hackathon = (commit_date - start_date).days + 1

                            if day_of_hackathon == 1:
                                first_day += 1
                            elif day_of_hackathon == hackathon_duration:
                                last_day += 1
                            else:
                                middle_days += 1

                    if hackathon_commits > 0:
                        even_distribution_factor = middle_days / hackathon_commits
                        timeline_score += timeline_factors["commit_distribution"] * even_distribution_factor

        code_authenticity_score = (1.0 - ai_score) * 100  # Convert to percentage

        rule_compliance_score = 100.0
        if len(result.rule_violations) > 0:
            violation_penalty = min(100, len(result.rule_violations) * 10)
            rule_compliance_score = max(0, rule_compliance_score - violation_penalty)

        plagiarism_score = 100.0
        if result.devpost_results:
            ai_content_prob = result.devpost_results.get("ai_content_probability", 0.0)
            plagiarism_score = max(0, 100.0 - (ai_content_prob * 100.0))

        team_compliance_score = 100.0
        if result.plagiarism_results and "team_compliance" in result.plagiarism_results:
            team_compliance = result.plagiarism_results["team_compliance"]
            if not team_compliance.get("size_compliant", True):
                team_compliance_score -= 50.0
            if not team_compliance.get("technologies_compliant", True):
                team_compliance_score -= 50.0

        result.scores.timeline_score = timeline_score
        result.scores.code_authenticity_score = code_authenticity_score
        result.scores.rule_compliance_score = rule_compliance_score
        result.scores.plagiarism_score = plagiarism_score
        result.scores.team_compliance_score = team_compliance_score

    def _validate_devpost_requirements(self, result: ValidationResult):
        if not self.current_config:
            return

        if "team_members" in result.plagiarism_results:
            team_members = result.plagiarism_results["team_members"]
            max_team_size = self.current_config.max_team_size

            if max_team_size and len(team_members) > max_team_size:
                result.failures.append(f"Team size ({len(team_members)}) exceeds maximum allowed ({max_team_size})")
            else:
                result.passes.append(f"Team size ({len(team_members)}) is within limits")

        if "technologies" in result.plagiarism_results:
            used_technologies = set(result.plagiarism_results["technologies"])
            required_technologies = set(self.current_config.required_technologies)
            disallowed_technologies = set(self.current_config.disallowed_technologies)

            missing_technologies = required_technologies - used_technologies
            if missing_technologies:
                result.failures.append(f"Missing required technologies: {', '.join(missing_technologies)}")

            forbidden_technologies = used_technologies & disallowed_technologies
            if forbidden_technologies:
                result.failures.append(f"Using disallowed technologies: {', '.join(forbidden_technologies)}")

            if not missing_technologies and not forbidden_technologies:
                result.passes.append("All technology requirements met")

        if "ai_content_probability" in result.devpost_results:
            ai_prob = result.devpost_results["ai_content_probability"]
            if ai_prob > 0.7:
                result.failures.append(f"DevPost description likely AI-generated ({ai_prob * 100:.1f}%)")
            elif ai_prob > 0.4:
                result.warnings.append(f"DevPost description may contain AI-generated content ({ai_prob * 100:.1f}%)")
            else:
                result.passes.append("DevPost description appears to be human-written")

        if "duplicate_submission" in result.devpost_results and result.devpost_results["duplicate_submission"]:
            result.failures.append("Project appears to be submitted to multiple hackathons")

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
                "category": result.scores.category,
                "overall_score": f"{result.scores.overall_score:.1f}%",
                "warnings_count": len(result.warnings),
                "failures_count": len(result.failures),
                "passes_count": len(result.passes),
            },
            "scores": {
                "timeline": f"{result.scores.timeline_score:.1f}%",
                "code_authenticity": f"{result.scores.code_authenticity_score:.1f}%",
                "rule_compliance": f"{result.scores.rule_compliance_score:.1f}%",
                "plagiarism": f"{result.scores.plagiarism_score:.1f}%",
                "team_compliance": f"{result.scores.team_compliance_score:.1f}%",
            },
            "timeline": {
                "created_during_hackathon": result.created_during_hackathon,
                "repository_created": result.github_results.get("created_at", "Unknown"),
                "last_updated": result.github_results.get("last_updated", "Unknown"),
                "total_commits": result.github_results.get("total_commits", 0),
                "hackathon_commits": result.github_results.get("commits_during_hackathon", 0),
            },
            "failures": result.failures,
            "warnings": result.warnings,
            "passes": result.passes,
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

        return report

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