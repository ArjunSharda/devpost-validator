from datetime import datetime, timezone
import re
from github import Github, Repository, GithubException, RateLimitExceededException
from typing import Dict, List, Optional, Tuple
from dateutil import parser as date_parser
import git
import tempfile
import os
import shutil
import json
from urllib.parse import urlparse


class GitHubAnalyzer:
    def __init__(self, token: str):
        self.github = Github(token)
        self.token = token

    def get_repository(self, repo_url: str) -> Optional[Dict]:
        repo_name = self._extract_repo_name(repo_url)
        if not repo_name:
            return {"error": f"Invalid GitHub URL format: {repo_url}", "status": "error"}

        try:
            repo = self.github.get_repo(repo_name)
            return {"repo": repo, "status": "success"}
        except RateLimitExceededException:
            rate_limit = self.github.get_rate_limit()
            reset_time = rate_limit.core.reset.strftime("%Y-%m-%d %H:%M:%S UTC")
            return {
                "error": f"GitHub API rate limit exceeded. Resets at {reset_time}",
                "status": "rate_limited"
            }
        except GithubException as e:
            if e.status == 404:
                return {"error": f"Repository not found: {repo_name}", "status": "not_found"}
            elif e.status == 401:
                return {"error": "Authentication failed. Check your GitHub token", "status": "auth_failed"}
            elif e.status == 403:
                return {"error": "Access forbidden. You may not have permission to access this repository",
                        "status": "forbidden"}
            else:
                return {"error": f"GitHub API error: {e.data.get('message', str(e))}", "status": "api_error"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}", "status": "error"}

    def _extract_repo_name(self, repo_url: str) -> Optional[str]:
        try:
            parsed_url = urlparse(repo_url)

            if parsed_url.netloc != "github.com":
                return None

            path_parts = [part for part in parsed_url.path.split("/") if part]

            if len(path_parts) < 2:
                return None

            owner = path_parts[0]
            repo = path_parts[1]

            return f"{owner}/{repo}"
        except Exception:
            return None

    def analyze_repository(self, repo_result: Dict, start_date: datetime, end_date: datetime) -> Dict:
        if repo_result.get("status") != "success":
            return {
                "error": repo_result.get("error", "Unknown error"),
                "status": repo_result.get("status", "error"),
                "warning_flags": [repo_result.get("error", "Unable to access GitHub repository")]
            }

        repo = repo_result["repo"]

        try:
            start_date_utc = self._ensure_timezone(start_date)
            end_date_utc = self._ensure_timezone(end_date)

            repo_created_at = repo.created_at
            if repo_created_at.tzinfo is None:
                repo_created_at = repo_created_at.replace(tzinfo=timezone.utc)

            repo_updated_at = repo.updated_at
            if repo_updated_at.tzinfo is None:
                repo_updated_at = repo_updated_at.replace(tzinfo=timezone.utc)

            result = {
                "name": repo.full_name,
                "created_at": repo_created_at,
                "last_updated": repo_updated_at,
                "created_during_hackathon": start_date_utc <= repo_created_at <= end_date_utc,
                "commits_during_hackathon": 0,
                "total_commits": 0,
                "ai_indicators": [],
                "languages": {},
                "contributors": [],
                "forks": repo.forks_count,
                "stars": repo.stargazers_count,
                "warning_flags": [],
            }

            try:
                result["languages"] = repo.get_languages()
            except GithubException:
                result["languages"] = {}
                result["warning_flags"].append("Could not retrieve repository languages")

            try:
                contributors = repo.get_contributors()
                result["contributors"] = [{"login": c.login, "contributions": c.contributions} for c in contributors]
            except GithubException:
                result["contributors"] = []
                result["warning_flags"].append("Could not retrieve repository contributors")

            try:
                result["total_commits"], result["commits_during_hackathon"], result[
                    "commit_timeline"] = self._analyze_commits(repo, start_date_utc, end_date_utc)
            except GithubException:
                result["total_commits"], result["commits_during_hackathon"], result["commit_timeline"] = 0, 0, []
                result["warning_flags"].append("Could not analyze repository commits")

            try:
                result["ai_indicators"] = self._check_for_ai_indicators(repo)
            except Exception:
                result["ai_indicators"] = []
                result["warning_flags"].append("Could not check for AI indicators")

            if not result["created_during_hackathon"]:
                result["warning_flags"].append("Repository was created outside the hackathon period")

            if result["commits_during_hackathon"] == 0:
                result["warning_flags"].append("No commits were made during the hackathon period")

            if result["ai_indicators"]:
                result["warning_flags"].append(f"Found {len(result['ai_indicators'])} indicators of AI-generated code")

            if repo_created_at > start_date_utc and (
                    repo_created_at - start_date_utc).days < 1 and repo_created_at.hour < 2:
                result["warning_flags"].append("Repository was created very soon after hackathon started")

            return result

        except Exception as e:
            return {
                "error": f"Error analyzing repository: {str(e)}",
                "status": "error",
                "warning_flags": [f"Error analyzing repository: {str(e)}"]
            }

    def _ensure_timezone(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _analyze_commits(self, repo: Repository.Repository, start_date: datetime, end_date: datetime) -> Tuple[
        int, int, List[Dict]]:
        commits = repo.get_commits()
        total_commits = 0
        commits_during_hackathon = 0
        timeline = []

        for commit in commits:
            total_commits += 1
            commit_date = commit.commit.author.date
            if commit_date.tzinfo is None:
                commit_date = commit_date.replace(tzinfo=timezone.utc)

            timeline.append({
                "sha": commit.sha,
                "date": commit_date,
                "author": commit.commit.author.name,
                "message": commit.commit.message,
                "during_hackathon": start_date <= commit_date <= end_date,
            })

            if start_date <= commit_date <= end_date:
                commits_during_hackathon += 1

        timeline.sort(key=lambda x: x["date"])
        return total_commits, commits_during_hackathon, timeline

    def _check_for_ai_indicators(self, repo: Repository.Repository) -> List[Dict]:
        ai_indicators = []
        temp_dir = tempfile.mkdtemp()

        try:
            git.Repo.clone_from(repo.clone_url, temp_dir)

            ai_patterns = [
                r"#\s*\.\.\.existing code\.\.\.",
                r"//\s*\.\.\.existing code\.\.\.",
                r"//\s*your code here",
                r"//\s*This is a mock implementation",
                r"#\s*TODO: Implement",
                r"//\s*TODO: Implement",
                r"#\s*FIXME:",
                r"//\s*FIXME:",
                r"\/\*\s*Generated by\s*.*AI.*\*\/",
                r"#\s*Generated by\s*.*AI",
                r"\/\/\s*Generated by\s*.*AI",
                r"<!--\s*Generated by\s*.*AI.*-->",
            ]

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

                            for pattern in ai_patterns:
                                matches = re.finditer(pattern, content, re.IGNORECASE)
                                for match in matches:
                                    rel_path = os.path.relpath(file_path, temp_dir)
                                    ai_indicators.append({
                                        "file": rel_path,
                                        "line": content[:match.start()].count('\n') + 1,
                                        "pattern": pattern,
                                        "match": match.group(0)
                                    })
                    except Exception:
                        pass

        finally:
            shutil.rmtree(temp_dir)

        return ai_indicators

    def _is_binary_file(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1024)
                return False
        except UnicodeDecodeError:
            return True

    def check_token_validity(self) -> Dict:
        try:
            user = self.github.get_user()
            username = user.login
            return {"valid": True, "username": username}
        except GithubException as e:
            if e.status in (401, 403):
                return {"valid": False, "error": "Invalid or expired token"}
            else:
                return {"valid": False, "error": f"GitHub API error: {e.data.get('message', str(e))}"}
        except Exception as e:
            return {"valid": False, "error": f"Unexpected error: {str(e)}"}