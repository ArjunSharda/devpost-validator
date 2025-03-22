from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
import re
import statistics
from collections import Counter, defaultdict
import math
import git


class CommitAnalyzer:
    def __init__(self):
        self.suspicious_commit_size = 1000
        self.unusual_timing_hours = [0, 1, 2, 3, 4]

    def analyze_commits(self, repo: git.Repo, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        result = {
            "total_commits": 0,
            "hackathon_commits": 0,
            "commit_distribution_score": 1.0,
            "suspicious_patterns": False,
            "pattern_details": {},
            "contributor_stats": [],
            "message_quality": 0.8,
            "frequency_score": 0.5,
            "commit_timeline": [],
        }

        if not repo:
            return result

        commits = list(repo.iter_commits())
        result["total_commits"] = len(commits)

        if not commits:
            return result

        commit_dates = []
        commit_sizes = []
        commit_messages = []
        commit_hours = []
        commit_authors = []
        suspicious_commits = []

        contributor_data = defaultdict(lambda: {
            "commit_count": 0,
            "lines_added": 0,
            "lines_deleted": 0,
            "files_modified": 0,
            "commit_times": [],
            "commit_sizes": [],
            "message_lengths": [],
        })

        hackathon_commits = 0

        for commit in commits:
            commit_time = datetime.fromtimestamp(commit.committed_date, timezone.utc)
            is_during_hackathon = start_date <= commit_time <= end_date

            author_name = commit.author.name
            author_email = commit.author.email

            if is_during_hackathon:
                hackathon_commits += 1

            commit_dates.append(commit_time)
            commit_hours.append(commit_time.hour)
            commit_messages.append(commit.message)
            commit_authors.append(author_name)

            contributor_data[author_name]["commit_count"] += 1
            contributor_data[author_name]["commit_times"].append(commit_time.isoformat())
            contributor_data[author_name]["message_lengths"].append(len(commit.message))

            try:
                parent = commit.parents[0] if commit.parents else None
                if parent:
                    diff_index = parent.diff(commit)
                    lines_changed = sum(d.change_type in ["M", "A", "D"] and (
                        sum(1 for _ in d.diff.decode('utf-8', errors='ignore').split("\n"))
                        if d.diff else 0
                    ) for d in diff_index)

                    commit_sizes.append(lines_changed)
                    contributor_data[author_name]["commit_sizes"].append(lines_changed)

                    diff_stats = diff_index.stats
                    contributor_data[author_name]["lines_added"] += diff_stats.get("insertions", 0)
                    contributor_data[author_name]["lines_deleted"] += diff_stats.get("deletions", 0)
                    contributor_data[author_name]["files_modified"] += diff_stats.get("files", 0)

                    if lines_changed > self.suspicious_commit_size:
                        suspicious_commits.append({
                            "hash": commit.hexsha,
                            "date": commit_time.isoformat(),
                            "lines_changed": lines_changed,
                            "author": author_name,
                            "message": commit.message.strip()
                        })
            except Exception:
                pass

            result["commit_timeline"].append({
                "hash": commit.hexsha[:8],
                "date": commit_time.isoformat(),
                "message": commit.message.strip(),
                "author": author_name,
                "during_hackathon": is_during_hackathon
            })

        result["hackathon_commits"] = hackathon_commits

        unusual_hour_commits = [c for c, h in zip(result["commit_timeline"], commit_hours) if
                                h in self.unusual_timing_hours]
        large_commits = [c for c in suspicious_commits]

        message_quality = self._analyze_message_quality(commit_messages)
        result["message_quality"] = message_quality

        if hackathon_commits > 0:
            result["commit_distribution_score"] = self._analyze_commit_distribution(
                [d for d in commit_dates if start_date <= d <= end_date],
                start_date,
                end_date
            )

        result["frequency_score"] = self._analyze_commit_frequency(commit_dates, start_date, end_date)

        result["contributor_stats"] = [
            {
                "author": author,
                "commit_count": stats["commit_count"],
                "lines_added": stats["lines_added"],
                "lines_deleted": stats["lines_deleted"],
                "files_modified": stats["files_modified"],
                "commit_times": stats["commit_times"][:10],
                "avg_commit_size": statistics.mean(stats["commit_sizes"]) if stats["commit_sizes"] else 0,
                "avg_message_length": statistics.mean(stats["message_lengths"]) if stats["message_lengths"] else 0,
            }
            for author, stats in contributor_data.items()
        ]

        result["contributor_stats"].sort(key=lambda x: x["commit_count"], reverse=True)

        suspicious_threshold = 0.3
        is_suspicious = bool(large_commits) or len(unusual_hour_commits) > hackathon_commits * suspicious_threshold
        result["suspicious_patterns"] = is_suspicious

        result["pattern_details"] = {
            "unusual_hour_commits": len(unusual_hour_commits),
            "large_commits": len(large_commits),
            "suspicious_commits": suspicious_commits[:5],
            "most_active_hours": self._most_common_hours(commit_hours),
            "commit_hour_distribution": self._hour_distribution(commit_hours),
        }

        return result

    def _analyze_message_quality(self, messages: List[str]) -> float:
        if not messages:
            return 0.5

        quality_scores = []

        for msg in messages:
            score = 0.5

            if len(msg.strip()) < 5:
                score = 0.1
            elif len(msg.strip()) > 20:
                score = 0.8

                if re.search(r"^(fix|add|update|remove|refactor|implement|improve)", msg.lower()):
                    score += 0.1

                if ":" in msg and len(msg.split(":", 1)[1].strip()) > 10:
                    score += 0.1

                if re.search(r"\b(fixes|resolves|closes)\s+#\d+\b", msg.lower()):
                    score += 0.2

            quality_scores.append(min(1.0, score))

        return statistics.mean(quality_scores)

    def _analyze_commit_distribution(self, commit_dates: List[datetime], start_date: datetime,
                                     end_date: datetime) -> float:
        if not commit_dates:
            return 0.0

        hackathon_duration = (end_date - start_date).total_seconds()
        if hackathon_duration <= 0:
            return 1.0

        ideal_distribution = 1.0

        day_buckets = defaultdict(int)
        for date in commit_dates:
            day_bucket = (date.date() - start_date.date()).days
            day_buckets[day_bucket] += 1

        total_days = (end_date.date() - start_date.date()).days + 1
        days_with_commits = len(day_buckets)

        coverage_ratio = days_with_commits / total_days if total_days > 0 else 0

        if len(commit_dates) <= 1:
            return coverage_ratio

        time_diffs = []
        sorted_dates = sorted(commit_dates)
        for i in range(1, len(sorted_dates)):
            diff = (sorted_dates[i] - sorted_dates[i - 1]).total_seconds()
            time_diffs.append(diff)

        if not time_diffs:
            return coverage_ratio

        evenness = min(1.0, 1.0 / (statistics.stdev(time_diffs) / (hackathon_duration / len(commit_dates))))

        distribution_score = (coverage_ratio * 0.7) + (evenness * 0.3)
        return min(1.0, distribution_score)

    def _analyze_commit_frequency(self, commit_dates: List[datetime], start_date: datetime,
                                  end_date: datetime) -> float:
        if not commit_dates:
            return 0.0

        hackathon_duration_days = (end_date - start_date).days + 1
        if hackathon_duration_days <= 0:
            return 0.5

        hackathon_commits = [d for d in commit_dates if start_date <= d <= end_date]

        if not hackathon_commits:
            return 0.0

        commits_per_day = len(hackathon_commits) / hackathon_duration_days

        target_frequency = 4.0
        frequency_score = min(1.0, commits_per_day / target_frequency)

        return frequency_score

    def _most_common_hours(self, hours: List[int]) -> List[Tuple[int, int]]:
        counter = Counter(hours)
        return counter.most_common(5)

    def _hour_distribution(self, hours: List[int]) -> Dict[str, int]:
        result = {}
        for h in range(24):
            result[str(h)] = hours.count(h)
        return result