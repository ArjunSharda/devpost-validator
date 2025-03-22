from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
import statistics
import math


class TeamAnalyzer:
    def __init__(self):
        pass

    def analyze_team(
            self,
            devpost_members: List[str],
            github_contributors: List[Dict[str, Any]],
            commit_stats: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        result = {
            "team_size": len(devpost_members),
            "contributor_count": len(github_contributors),
            "contribution_balance": 1.0,  # 1.0 = perfectly balanced
            "contribution_imbalance": False,
            "github_team_match": 1.0,  # 1.0 = perfect match
            "github_team_mismatch": False,
            "contribution_details": {},
            "mismatch_details": {},
        }

        # Calculate contribution balance
        if github_contributors:
            contributions = [c.get("contributions", 0) for c in github_contributors]
            result["contribution_details"]["contributors"] = [
                {"login": c.get("login", ""), "contributions": c.get("contributions", 0)}
                for c in github_contributors
            ]

            if len(contributions) > 1 and sum(contributions) > 0:
                # Calculate Gini coefficient for inequality
                sorted_contrib = sorted(contributions)
                n = len(sorted_contrib)
                numerator = sum((i + 1) * c for i, c in enumerate(sorted_contrib))
                denominator = n * sum(sorted_contrib)
                gini = (2 * numerator / denominator) - (n + 1) / n

                # Invert Gini so 1.0 = perfectly balanced, 0.0 = completely imbalanced
                result["contribution_balance"] = 1.0 - gini

                # Flag imbalance if one contributor has more than 80% of commits
                # or if Gini coefficient is > 0.6 (balance < 0.4)
                max_contrib_ratio = max(contributions) / sum(contributions)
                result["contribution_imbalance"] = max_contrib_ratio > 0.8 or result["contribution_balance"] < 0.4

                result["contribution_details"]["balance_metric"] = result["contribution_balance"]
                result["contribution_details"]["max_contribution_ratio"] = max_contrib_ratio

        # Calculate team match between GitHub and DevPost
        if devpost_members and github_contributors:
            # Try to match GitHub usernames to DevPost names
            match_score = self._calculate_team_match(devpost_members, github_contributors)
            result["github_team_match"] = match_score
            result["github_team_mismatch"] = match_score < 0.7

            result["mismatch_details"]["devpost_members"] = devpost_members
            result["mismatch_details"]["github_contributors"] = [c.get("login", "") for c in github_contributors]
            result["mismatch_details"]["match_score"] = match_score

        # Analyze commit patterns by contributor if commit stats are available
        if commit_stats:
            contributor_patterns = {}

            for stat in commit_stats:
                login = stat.get("author", "")
                if login:
                    contributor_patterns[login] = {
                        "commit_count": stat.get("commit_count", 0),
                        "lines_added": stat.get("lines_added", 0),
                        "lines_deleted": stat.get("lines_deleted", 0),
                        "files_modified": stat.get("files_modified", 0),
                        "commit_times": stat.get("commit_times", []),
                    }

            result["contribution_details"]["patterns"] = contributor_patterns

        return result

    def _calculate_team_match(self, devpost_members: List[str], github_contributors: List[Dict[str, Any]]) -> float:
        github_logins = [c.get("login", "").lower() for c in github_contributors]

        # Try exact matches
        matched_count = 0
        for member in devpost_members:
            member_lower = member.lower()

            # Check for exact username match
            if member_lower in github_logins:
                matched_count += 1
                continue

            # Check for name in login or login in name
            for login in github_logins:
                # Split names into parts for better matching
                member_parts = set(member_lower.replace('.', ' ').replace('-', ' ').replace('_', ' ').split())
                login_parts = set(login.replace('.', ' ').replace('-', ' ').replace('_', ' ').split())

                # Check if any significant part matches
                significant_parts = [p for p in member_parts if len(p) > 2]
                if any(part in login for part in significant_parts):
                    matched_count += 0.8
                    break

                # Check for initial-based usernames
                if len(login) >= 2 and all(login.startswith(part[0]) for part in member_parts if part):
                    matched_count += 0.7
                    break

        # Calculate match ratio
        max_possible = max(len(devpost_members), len(github_contributors))
        match_ratio = matched_count / max_possible if max_possible > 0 else 0

        # Add a penalty if GitHub has significantly more contributors than DevPost members
        if len(github_contributors) > len(devpost_members) * 1.5:
            match_ratio *= 0.8

        return min(1.0, match_ratio)