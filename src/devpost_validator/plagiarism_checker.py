import re
import requests
from typing import Dict, List, Optional, Tuple, Any, Set
from bs4 import BeautifulSoup
import hashlib
from difflib import SequenceMatcher
import json


class PlagiarismChecker:
    def __init__(self):
        self.cache = {}
        self.headers = {
            "User-Agent": "DevPostValidator/2.0.0"
        }
        self.known_projects = {}

    def check_devpost_project(self, devpost_url: str, team_size: Optional[int] = None,
                              required_technologies: Optional[List[str]] = None) -> Dict:
        result = {
            "url": devpost_url,
            "title": "",
            "description": "",
            "similarity_matches": [],
            "ai_content_probability": 0.0,
            "team_members": [],
            "technologies": [],
            "team_compliance": {
                "size_compliant": True,
                "technologies_compliant": True
            },
            "warnings": []
        }

        try:
            content = self._fetch_devpost_content(devpost_url)
            if not content:
                result["warnings"].append("Failed to fetch DevPost content")
                return result

            result["title"] = content.get("title", "")
            result["description"] = content.get("description", "")
            result["team_members"] = content.get("team_members", [])
            result["technologies"] = content.get("technologies", [])

            ai_indicators = self._detect_ai_text_patterns(result["description"])
            if ai_indicators:
                result["warnings"].extend(ai_indicators)
                result["ai_content_probability"] = min(0.9, 0.3 * len(ai_indicators))

            similarity_matches = self._check_text_similarity(result["description"])
            if similarity_matches:
                result["similarity_matches"] = similarity_matches
                result["warnings"].append(f"Found {len(similarity_matches)} potential content matches")

            if team_size is not None:
                if len(result["team_members"]) > team_size:
                    result["team_compliance"]["size_compliant"] = False
                    result["warnings"].append(
                        f"Team size ({len(result['team_members'])}) exceeds maximum allowed ({team_size})")

            if required_technologies:
                req_techs = set(required_technologies)
                used_techs = set(result["technologies"])
                missing_techs = req_techs - used_techs

                if missing_techs:
                    result["team_compliance"]["technologies_compliant"] = False
                    result["warnings"].append(f"Missing required technologies: {', '.join(missing_techs)}")

            project_fingerprint = f"{result['title']}|{result['description'][:300]}"
            if project_fingerprint in self.known_projects:
                prev_url = self.known_projects[project_fingerprint]
                if prev_url != devpost_url:
                    result["warnings"].append(f"Potential duplicate submission of: {prev_url}")
            else:
                self.known_projects[project_fingerprint] = devpost_url

        except Exception as e:
            result["warnings"].append(f"Error analyzing DevPost content: {str(e)}")

        return result

    def _fetch_devpost_content(self, url: str) -> Optional[Dict]:
        try:
            if url in self.cache:
                return self.cache[url]

            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            title = soup.find('h1')
            title = title.text.strip() if title else "Unknown Project"

            description_divs = soup.select('.app-details .description')
            description = description_divs[0].text.strip() if description_divs else ""

            team_members = []
            team_section = soup.select('.app-team .members li')
            for member in team_section:
                member_name = member.select_one('.member-name')
                if member_name:
                    team_members.append(member_name.text.strip())

            technologies = []
            tech_spans = soup.select('.app-details .software-used .cp-tag')
            for tech in tech_spans:
                technologies.append(tech.text.strip())

            github_link = None
            repo_links = soup.select('a[href*="github.com"]')
            if repo_links:
                github_link = repo_links[0]['href']

            result = {
                "title": title,
                "description": description,
                "team_members": team_members,
                "technologies": technologies,
                "github_url": github_link
            }

            self.cache[url] = result
            return result

        except Exception:
            return None

    def _detect_ai_text_patterns(self, text: str) -> List[str]:
        warnings = []

        patterns = [
            (r"As an AI language model", "Contains phrase 'As an AI language model'"),
            (r"I'm sorry, (but )?I (cannot|can't)", "Contains common AI refusal pattern"),
            (r"I don't have (personal )?opinions", "Contains common AI disclaimer"),
            (r"As of my last (knowledge|training) ?(update)? ?(in|on)? ?(the)? ?\d{4}",
             "Contains reference to training cutoff"),
            (r"As a(n)? (language |text )?AI( model)?", "Contains self-reference as AI model"),
            (r"I don't have the ability to", "Contains common AI limitation statement"),
            (r"without access to (real-time|current|up-to-date)", "Contains common AI knowledge limitation"),
            (
            r"\b(first|firstly|second|secondly|third|thirdly|fourth|lastly)\b.{1,50}\b(first|firstly|second|secondly|third|thirdly|fourth|lastly)\b",
            "Contains mechanical enumeration common in AI text"),
            (r"In conclusion,", "Contains 'In conclusion' common in AI-structured text"),
            (r"Let me know if you have any (other |more )?questions", "Contains AI service phrase"),
            (r"I hope this helps", "Contains AI closing statement"),
        ]

        for pattern, warning in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                warnings.append(warning)

        paragraphs = text.split('\n\n')
        if len(paragraphs) >= 3:
            similar_starts = 0
            even_lengths = 0
            prev_length = len(paragraphs[0].split())

            for i in range(1, len(paragraphs)):
                if not paragraphs[i]:
                    continue

                curr_length = len(paragraphs[i].split())
                length_diff = abs(curr_length - prev_length)

                if length_diff <= 3:
                    even_lengths += 1

                prev_length = curr_length

                if paragraphs[i] and paragraphs[i - 1]:
                    first_words_prev = paragraphs[i - 1].split(' ')[:3]
                    first_words_curr = paragraphs[i].split(' ')[:3]
                    if any(word.lower() in [w.lower() for w in first_words_curr] for word in first_words_prev):
                        similar_starts += 1

            if similar_starts >= 2:
                warnings.append("Multiple paragraphs begin with similar phrases (common in AI text)")

            if even_lengths >= len(paragraphs) * 0.7:
                warnings.append("Paragraphs have suspiciously similar lengths (common in AI text)")

        return warnings

    def _check_text_similarity(self, text: str) -> List[Dict]:
        result = []

        fingerprint = hashlib.md5(text[:300].encode('utf-8')).hexdigest()

        for url, cached_content in self.cache.items():
            if cached_content.get("description") and cached_content.get("description") != text:
                cached_fingerprint = hashlib.md5(cached_content["description"][:300].encode('utf-8')).hexdigest()

                if fingerprint == cached_fingerprint:
                    result.append({
                        "url": url,
                        "title": cached_content.get("title", ""),
                        "similarity": 1.0,
                        "type": "exact_match"
                    })
                else:
                    similarity = self.similarity_ratio(text[:1000], cached_content["description"][:1000])
                    if similarity > 0.7:
                        result.append({
                            "url": url,
                            "title": cached_content.get("title", ""),
                            "similarity": similarity,
                            "type": "similar_content"
                        })

        return result

    def similarity_ratio(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def load_known_projects(self, filepath: str) -> bool:
        try:
            with open(filepath, 'r') as f:
                self.known_projects = json.load(f)
            return True
        except Exception:
            return False

    def save_known_projects(self, filepath: str) -> bool:
        try:
            with open(filepath, 'w') as f:
                json.dump(self.known_projects, f, indent=2)
            return True
        except Exception:
            return False