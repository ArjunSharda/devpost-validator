from typing import Dict, List, Any, Optional
import requests
import base64
from datetime import datetime, timezone, timedelta
import time
import re
from pathlib import Path
import json
from urllib.parse import urlparse
import os


class GitHubAnalyzer:
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }

        if token:
            self.headers["Authorization"] = f"token {token}"

        self.cache_dir = Path.home() / ".devpost-validator" / "cache" / "github"
        self.cache_dir.mkdir(exist_ok=True, parents=True)

    def check_token_validity(self) -> Dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url}/user", headers=self.headers, timeout=10)

            if response.status_code == 200:
                user_data = response.json()
                return {
                    "valid": True,
                    "username": user_data.get("login"),
                    "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining", "Unknown")
                }
            else:
                return {
                    "valid": False,
                    "error": f"HTTP {response.status_code}: {response.json().get('message', 'Unknown error')}",
                    "status_code": response.status_code
                }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }

    def parse_github_url(self, github_url: str) -> Dict[str, str]:
        parsed_url = urlparse(github_url)

        if parsed_url.netloc != "github.com":
            return {"error": "Not a GitHub URL"}

        path_parts = parsed_url.path.strip("/").split("/")

        if len(path_parts) < 2:
            return {"error": "Invalid GitHub repository URL"}

        owner = path_parts[0]
        repo = path_parts[1]

        return {
            "owner": owner,
            "repo": repo
        }

    def get_repository(self, github_url: str) -> Dict[str, Any]:
        parsed = self.parse_github_url(github_url)

        if "error" in parsed:
            return {
                "status": "error",
                "error": parsed["error"]
            }

        owner = parsed["owner"]
        repo = parsed["repo"]

        cache_key = f"{owner}_{repo}_repo"
        cached_data = self._check_cache(cache_key)
        if cached_data:
            return cached_data

        try:
            api_url = f"{self.base_url}/repos/{owner}/{repo}"
            response = requests.get(api_url, headers=self.headers, timeout=15)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.json().get('message', 'Unknown error')}",
                    "repo_url": github_url
                }

            repo_data = response.json()

            result = {
                "status": "success",
                "repo": repo_data,
                "owner": owner,
                "name": repo,
                "full_name": repo_data.get("full_name", f"{owner}/{repo}"),
                "created_at": repo_data.get("created_at"),
                "updated_at": repo_data.get("updated_at"),
                "pushed_at": repo_data.get("pushed_at"),
                "default_branch": repo_data.get("default_branch", "main"),
                "language": repo_data.get("language"),
                "languages_url": repo_data.get("languages_url"),
                "contributors_url": repo_data.get("contributors_url"),
                "commits_url": repo_data.get("commits_url").replace("{/sha}", ""),
                "fork": repo_data.get("fork", False),
                "forked_from": repo_data.get("parent", {}).get("full_name") if repo_data.get("fork", False) else None,
                "fork_count": repo_data.get("forks_count", 0),
                "stars": repo_data.get("stargazers_count", 0),
                "watchers": repo_data.get("watchers_count", 0),
                "open_issues": repo_data.get("open_issues_count", 0),
                "has_issues": repo_data.get("has_issues", True),
                "has_projects": repo_data.get("has_projects", True),
                "has_wiki": repo_data.get("has_wiki", True),
                "has_pages": repo_data.get("has_pages", False),
                "has_discussions": repo_data.get("has_discussions", False),
                "archived": repo_data.get("archived", False),
                "disabled": repo_data.get("disabled", False),
                "visibility": repo_data.get("visibility", "public"),
                "license": repo_data.get("license", {}).get("spdx_id") if repo_data.get("license") else None,
                "topics": repo_data.get("topics", []),
                "clone_url": repo_data.get("clone_url"),
                "html_url": repo_data.get("html_url"),
                "description": repo_data.get("description", "")
            }

            self._cache_result(cache_key, result)
            return result

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "repo_url": github_url
            }

    def get_commits(self, owner: str, repo: str, branch: str = "main", since: Optional[datetime] = None,
                    until: Optional[datetime] = None, max_pages: int = 10) -> Dict[str, Any]:
        cache_key = f"{owner}_{repo}_commits"
        if since:
            cache_key += f"_since_{since.isoformat()}"
        if until:
            cache_key += f"_until_{until.isoformat()}"

        cached_data = self._check_cache(cache_key)
        if cached_data:
            return cached_data

        try:
            all_commits = []
            api_url = f"{self.base_url}/repos/{owner}/{repo}/commits"
            params = {
                "sha": branch,
                "per_page": 100
            }

            if since:
                params["since"] = since.isoformat()
            if until:
                params["until"] = until.isoformat()

            next_url = api_url

            for page in range(max_pages):
                if not next_url:
                    break

                if page > 0:
                    time.sleep(0.5)

                response = requests.get(next_url, headers=self.headers, params=params if page == 0 else None,
                                        timeout=15)

                if response.status_code != 200:
                    return {
                        "status": "error",
                        "error": f"HTTP {response.status_code}: {response.json().get('message', 'Unknown error')}",
                        "commits": []
                    }

                page_commits = response.json()
                all_commits.extend(page_commits)

                next_url = None
                if "Link" in response.headers:
                    for link in response.headers["Link"].split(","):
                        if 'rel="next"' in link:
                            next_url = link.split(";")[0].strip("<>")
                            break

                if not next_url or len(page_commits) < 100:
                    break

            result = {
                "status": "success",
                "commits": all_commits,
                "count": len(all_commits),
                "since": since.isoformat() if since else None,
                "until": until.isoformat() if until else None
            }

            self._cache_result(cache_key, result)
            return result

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "commits": []
            }

    def get_contributors(self, owner: str, repo: str) -> Dict[str, Any]:
        cache_key = f"{owner}_{repo}_contributors"
        cached_data = self._check_cache(cache_key)
        if cached_data:
            return cached_data

        try:
            api_url = f"{self.base_url}/repos/{owner}/{repo}/contributors"
            params = {
                "per_page": 100
            }

            response = requests.get(api_url, headers=self.headers, params=params, timeout=15)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.json().get('message', 'Unknown error')}",
                    "contributors": []
                }

            contributors_data = response.json()

            result = {
                "status": "success",
                "contributors": contributors_data,
                "count": len(contributors_data)
            }

            self._cache_result(cache_key, result)
            return result

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "contributors": []
            }

    def get_languages(self, owner: str, repo: str) -> Dict[str, Any]:
        cache_key = f"{owner}_{repo}_languages"
        cached_data = self._check_cache(cache_key)
        if cached_data:
            return cached_data

        try:
            api_url = f"{self.base_url}/repos/{owner}/{repo}/languages"

            response = requests.get(api_url, headers=self.headers, timeout=15)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.json().get('message', 'Unknown error')}",
                    "languages": {}
                }

            languages_data = response.json()
            total_bytes = sum(languages_data.values())

            if total_bytes > 0:
                for lang, bytes_count in languages_data.items():
                    languages_data[lang] = {
                        "bytes": bytes_count,
                        "percentage": round((bytes_count / total_bytes) * 100, 2)
                    }

            result = {
                "status": "success",
                "languages": languages_data,
                "total_bytes": total_bytes
            }

            self._cache_result(cache_key, result)
            return result

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "languages": {}
            }

    def get_readme(self, owner: str, repo: str, branch: str = "main") -> Dict[str, Any]:
        cache_key = f"{owner}_{repo}_readme"
        cached_data = self._check_cache(cache_key)
        if cached_data:
            return cached_data

        try:
            api_url = f"{self.base_url}/repos/{owner}/{repo}/readme"

            response = requests.get(api_url, headers=self.headers, timeout=15)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.json().get('message', 'Unknown error')}",
                    "content": None
                }

            readme_data = response.json()

            content = None
            if readme_data.get("content"):
                content = base64.b64decode(readme_data["content"]).decode('utf-8', errors='ignore')

            result = {
                "status": "success",
                "name": readme_data.get("name"),
                "path": readme_data.get("path"),
                "content": content,
                "html_url": readme_data.get("html_url")
            }

            self._cache_result(cache_key, result)
            return result

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "content": None
            }

    def analyze_repository(self, repo_result: Dict[str, Any], hackathon_start: datetime, hackathon_end: datetime) -> \
    Dict[str, Any]:
        if repo_result.get("status") != "success":
            return {
                "error": repo_result.get("error", "Unknown error"),
                "status": "error"
            }

        repo = repo_result["repo"]
        owner = repo_result["owner"]
        repo_name = repo_result["name"]

        created_at = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(repo["updated_at"].replace("Z", "+00:00"))
        pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))

        created_during_hackathon = hackathon_start <= created_at <= hackathon_end

        result = {
            "name": repo_name,
            "full_name": repo["full_name"],
            "description": repo["description"],
            "created_at": created_at,
            "last_updated": updated_at,
            "last_pushed": pushed_at,
            "created_during_hackathon": created_during_hackathon,
            "warning_flags": []
        }

        default_branch = repo["default_branch"]

        commits_result = self.get_commits(owner, repo_name, branch=default_branch)
        if commits_result.get("status") == "success":
            result["total_commits"] = commits_result["count"]

            commits = commits_result["commits"]
            result["first_commit"] = commits[-1] if commits else None
            result["latest_commit"] = commits[0] if commits else None

            hackathon_commits_result = self.get_commits(
                owner,
                repo_name,
                branch=default_branch,
                since=hackathon_start,
                until=hackathon_end
            )

            if hackathon_commits_result.get("status") == "success":
                hackathon_commits = hackathon_commits_result["commits"]
                result["commits_during_hackathon"] = len(hackathon_commits)

                commit_timeline = self._analyze_commit_timeline(hackathon_commits, hackathon_start, hackathon_end)
                result["commit_timeline"] = commit_timeline["timeline"]
                result["commit_clusters"] = commit_timeline["clusters"]

                if commit_timeline["suspicious_patterns"]:
                    result["warning_flags"].extend(commit_timeline["suspicious_patterns"])
            else:
                result["commits_during_hackathon"] = 0
        else:
            result["total_commits"] = 0
            result["commits_during_hackathon"] = 0

        contributors_result = self.get_contributors(owner, repo_name)
        if contributors_result.get("status") == "success":
            result["contributors"] = contributors_result["contributors"]
            result["contributor_count"] = contributors_result["count"]

            if result["contributor_count"] > 1:
                contributor_analysis = self._analyze_contributors(contributors_result["contributors"])
                result["contribution_balance"] = contributor_analysis["balance"]

                if contributor_analysis["imbalanced"]:
                    result["warning_flags"].append(
                        f"Contribution imbalance detected: {contributor_analysis['primary_contributor']} made {contributor_analysis['primary_percentage']:.1f}% of contributions"
                    )
        else:
            result["contributors"] = []
            result["contributor_count"] = 0

        languages_result = self.get_languages(owner, repo_name)
        if languages_result.get("status") == "success":
            result["languages"] = languages_result["languages"]
            result["primary_language"] = self._get_primary_language(languages_result["languages"])
        else:
            result["languages"] = {}
            result["primary_language"] = None

        readme_result = self.get_readme(owner, repo_name, branch=default_branch)
        if readme_result.get("status") == "success":
            result["has_readme"] = readme_result["content"] is not None
            if readme_result["content"]:
                readme_length = len(readme_result["content"])
                result["readme_length"] = readme_length

                if readme_length < 100:
                    result["warning_flags"].append("Repository has a very short README (less than 100 characters)")
        else:
            result["has_readme"] = False

        if repo["fork"]:
            result["warning_flags"].append(f"Repository is a fork of {repo['forked_from']}")

        if created_at < hackathon_start:
            time_before = (hackathon_start - created_at).days
            result["warning_flags"].append(f"Repository was created {time_before} days before the hackathon started")

        return result

    def _analyze_commit_timeline(self, commits: List[Dict[str, Any]], start_date: datetime, end_date: datetime) -> Dict[
        str, Any]:
        result = {
            "timeline": [],
            "clusters": [],
            "suspicious_patterns": []
        }

        if not commits:
            return result

        commit_times = []
        cluster_threshold_hours = 3

        for commit in commits:
            author = commit.get("commit", {}).get("author", {})
            committer = commit.get("commit", {}).get("committer", {})

            commit_time = datetime.fromisoformat(committer.get("date", "").replace("Z", "+00:00"))
            author_time = datetime.fromisoformat(author.get("date", "").replace("Z", "+00:00"))

            committer_name = committer.get("name", "Unknown")
            author_name = author.get("name", "Unknown")

            github_author = commit.get("author", {})
            github_committer = commit.get("committer", {})

            github_author_login = github_author.get("login") if github_author else None
            github_committer_login = github_committer.get("login") if github_committer else None

            time_data = {
                "sha": commit.get("sha", ""),
                "date": commit_time,
                "author_date": author_time,
                "message": commit.get("commit", {}).get("message", ""),
                "author": author_name,
                "committer": committer_name,
                "github_author": github_author_login,
                "github_committer": github_committer_login,
                "hour_of_day": commit_time.hour,
                "day_of_week": commit_time.weekday(),
                "additions": None,
                "deletions": None,
                "during_hackathon": start_date <= commit_time <= end_date
            }

            url_parts = commit.get("url", "").split("/")
            if len(url_parts) >= 8:
                owner = url_parts[4]
                repo = url_parts[5]
                sha = url_parts[7]

                detailed_commit = self._get_detailed_commit(owner, repo, sha)
                if detailed_commit.get("status") == "success":
                    time_data["additions"] = detailed_commit.get("additions", 0)
                    time_data["deletions"] = detailed_commit.get("deletions", 0)
                    time_data["changed_files"] = detailed_commit.get("changed_files", 0)

            result["timeline"].append(time_data)
            commit_times.append(commit_time)

        if commit_times:
            sorted_times = sorted(commit_times)

            current_cluster = [sorted_times[0]]
            clusters = []

            for i in range(1, len(sorted_times)):
                time_diff = (sorted_times[i] - sorted_times[i - 1]).total_seconds() / 3600

                if time_diff <= cluster_threshold_hours:
                    current_cluster.append(sorted_times[i])
                else:
                    if len(current_cluster) > 1:
                        clusters.append({
                            "start": current_cluster[0],
                            "end": current_cluster[-1],
                            "commits": len(current_cluster),
                            "duration_hours": (current_cluster[-1] - current_cluster[0]).total_seconds() / 3600
                        })
                    current_cluster = [sorted_times[i]]

            if len(current_cluster) > 1:
                clusters.append({
                    "start": current_cluster[0],
                    "end": current_cluster[-1],
                    "commits": len(current_cluster),
                    "duration_hours": (current_cluster[-1] - current_cluster[0]).total_seconds() / 3600
                })

            result["clusters"] = clusters

            late_night_commits = sum(1 for c in result["timeline"] if 0 <= c["hour_of_day"] < 5)
            if late_night_commits > 3:
                result["suspicious_patterns"].append(
                    f"{late_night_commits} commits were made between midnight and 5 AM")

            hackathon_duration = (end_date - start_date).total_seconds() / 3600
            if len(clusters) == 1 and clusters[0]["commits"] > 10 and clusters[0]["duration_hours"] < 24:
                result["suspicious_patterns"].append(
                    f"All {clusters[0]['commits']} commits were made within a {clusters[0]['duration_hours']:.1f} hour period")

            if len(commits) > 10:
                large_commits = [c for c in result["timeline"] if c.get("additions") and c.get("additions", 0) > 1000]
                if large_commits and len(large_commits) / len(commits) > 0.3:
                    result["suspicious_patterns"].append(
                        f"{len(large_commits)} out of {len(commits)} commits changed more than 1000 lines")

                similar_messages = self._check_similar_messages([c.get("message", "") for c in result["timeline"]])
                if similar_messages["similar_ratio"] > 0.7:
                    result["suspicious_patterns"].append(
                        f"{similar_messages['similar_ratio'] * 100:.1f}% of commit messages are very similar")

            first_commit_date = min(commit_times)
            last_commit_date = max(commit_times)

            if first_commit_date > start_date + timedelta(days=(end_date - start_date).days * 0.7):
                days_after_start = (first_commit_date - start_date).days
                result["suspicious_patterns"].append(
                    f"First commit was only made {days_after_start} days after the hackathon started")

            if last_commit_date < end_date - timedelta(days=1) and (end_date - last_commit_date).days > 1:
                days_before_end = (end_date - last_commit_date).days
                result["suspicious_patterns"].append(
                    f"Last commit was made {days_before_end} days before the hackathon ended")

        return result

    def _analyze_contributors(self, contributors: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not contributors or len(contributors) <= 1:
            return {
                "balance": 1.0,
                "imbalanced": False,
                "primary_contributor": None,
                "primary_percentage": 0
            }

        total_contributions = sum(c.get("contributions", 0) for c in contributors)

        if total_contributions == 0:
            return {
                "balance": 1.0,
                "imbalanced": False,
                "primary_contributor": None,
                "primary_percentage": 0
            }

        contributors_sorted = sorted(contributors, key=lambda x: x.get("contributions", 0), reverse=True)
        primary = contributors_sorted[0]
        primary_ratio = primary.get("contributions", 0) / total_contributions

        if len(contributors) == 2:
            balance = 1 - abs(
                contributors[0].get("contributions", 0) - contributors[1].get("contributions", 0)) / total_contributions
        else:
            expected_per_contributor = total_contributions / len(contributors)
            deviation_sum = sum(abs(c.get("contributions", 0) - expected_per_contributor) for c in contributors)
            max_possible_deviation = 2 * (len(contributors) - 1) * expected_per_contributor

            if max_possible_deviation == 0:
                balance = 1.0
            else:
                balance = 1 - (deviation_sum / max_possible_deviation)

        return {
            "balance": balance,
            "imbalanced": primary_ratio > 0.8,
            "primary_contributor": primary.get("login"),
            "primary_percentage": primary_ratio * 100
        }

    def _check_similar_messages(self, messages: List[str]) -> Dict[str, Any]:
        if not messages or len(messages) < 5:
            return {
                "similar_ratio": 0,
                "common_prefixes": []
            }

        prefixes = []
        for msg in messages:
            if not msg:
                continue

            words = msg.strip().split()
            if words:
                prefixes.append(words[0].lower())

        if not prefixes:
            return {
                "similar_ratio": 0,
                "common_prefixes": []
            }

        prefix_counts = {}
        for prefix in prefixes:
            prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

        common_prefixes = [p for p, count in prefix_counts.items() if count >= 3]
        similar_count = sum(prefix_counts.get(prefix, 0) for prefix in common_prefixes)

        return {
            "similar_ratio": similar_count / len(prefixes) if prefixes else 0,
            "common_prefixes": common_prefixes
        }

    def _get_primary_language(self, languages: Dict[str, Any]) -> Optional[str]:
        if not languages:
            return None

        primary = None
        max_percentage = 0

        for lang, data in languages.items():
            if isinstance(data, dict) and "percentage" in data:
                if data["percentage"] > max_percentage:
                    max_percentage = data["percentage"]
                    primary = lang
            else:
                if not primary or data > languages.get(primary, 0):
                    primary = lang

        return primary

    def _get_detailed_commit(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        cache_key = f"{owner}_{repo}_commit_{sha}"
        cached_data = self._check_cache(cache_key)
        if cached_data:
            return cached_data

        try:
            api_url = f"{self.base_url}/repos/{owner}/{repo}/commits/{sha}"

            response = requests.get(api_url, headers=self.headers, timeout=15)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.json().get('message', 'Unknown error')}"
                }

            commit_data = response.json()

            result = {
                "status": "success",
                "sha": commit_data.get("sha"),
                "additions": commit_data.get("stats", {}).get("additions", 0),
                "deletions": commit_data.get("stats", {}).get("deletions", 0),
                "changed_files": commit_data.get("files", [])
            }

            self._cache_result(cache_key, result)
            return result

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def _check_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                cache_age = time.time() - os.path.getmtime(cache_file)

                if cache_age < 3600:
                    with open(cache_file, 'r') as f:
                        return json.load(f)
            except Exception:
                pass

        return None

    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"

            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)
        except Exception:
            pass