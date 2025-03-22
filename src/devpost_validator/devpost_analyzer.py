import re
import requests
from typing import Dict, List, Optional, Tuple, Any
from bs4 import BeautifulSoup
import hashlib
from urllib.parse import urlparse
from datetime import datetime, timezone
import json


class DevPostAnalyzer:
    def __init__(self):
        self.cache = {}
        self.headers = {
            "User-Agent": "DevPostValidator/2.0.0"
        }
        self.api_endpoint = "https://devpost.com/api/v1/hackathons"
        self.submission_data = {}

    def analyze_submission(self, devpost_url: str) -> Dict[str, Any]:
        result = {
            "url": devpost_url,
            "title": "",
            "description": "",
            "team_members": [],
            "technologies": [],
            "github_url": None,
            "ai_content_probability": 0.0,
            "duplicate_submission": False,
            "hackathon": "",
            "submission_date": None,
            "warnings": []
        }

        try:
            content = self._fetch_devpost_content(devpost_url)
            if not content:
                result["warnings"].append("Failed to fetch DevPost content")
                return result

            result.update(content)

            result["ai_content_probability"] = self._detect_ai_probability(result.get("description", ""))
            result["duplicate_submission"] = self._check_duplicate_submission(result.get("title", ""),
                                                                              result.get("description", ""))

            return result

        except Exception as e:
            result["warnings"].append(f"Error analyzing DevPost: {str(e)}")
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

            hackathon_link = soup.select_one('.software-header-hackathon a')
            hackathon = hackathon_link.text.strip() if hackathon_link else ""

            date_span = soup.select_one('span.date')
            submission_date = None
            if date_span:
                date_text = date_span.text.strip()
                try:
                    submission_date = datetime.strptime(date_text, "%b %d, %Y").replace(tzinfo=timezone.utc)
                except:
                    pass

            result = {
                "title": title,
                "description": description,
                "team_members": team_members,
                "technologies": technologies,
                "github_url": github_link,
                "hackathon": hackathon,
                "submission_date": submission_date
            }

            self.cache[url] = result
            self.submission_data[title] = {
                "url": url,
                "description": description,
                "team_members": team_members,
                "technologies": technologies,
                "submission_date": submission_date,
                "hackathon": hackathon
            }

            return result

        except Exception as e:
            return None

    def _detect_ai_probability(self, text: str) -> float:
        if not text or len(text) < 100:
            return 0.0

        ai_markers = [
            (r"As an AI language model", 0.9),
            (r"I'm sorry, (but )?I (cannot|can't)", 0.8),
            (r"I don't have (personal )?opinions", 0.8),
            (r"As of my last (knowledge|training) ?(update)? ?(in|on)? ?(the)? ?\d{4}", 0.9),
            (r"As a(n)? (language |text )?AI( model)?", 0.9),
            (r"I don't have the ability to", 0.7),
            (r"without access to (real-time|current|up-to-date)", 0.7),
            (
            r"\b(first|firstly|second|secondly|third|thirdly|fourth|lastly)\b.{1,50}\b(first|firstly|second|secondly|third|thirdly|fourth|lastly)\b",
            0.4),
            (r"In conclusion,", 0.3),
            (r"Let me know if you have any (other |more )?questions", 0.6),
            (r"I hope this helps", 0.5),
        ]

        max_prob = 0.0
        for pattern, prob in ai_markers:
            if re.search(pattern, text, re.IGNORECASE):
                max_prob = max(max_prob, prob)

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
                max_prob = max(max_prob, 0.5)

            if even_lengths >= len(paragraphs) * 0.7:
                max_prob = max(max_prob, 0.4)

        return max_prob

    def _check_duplicate_submission(self, title: str, description: str) -> bool:
        title_hash = hashlib.md5(title.lower().encode('utf-8')).hexdigest()
        desc_hash = hashlib.md5(description[:300].lower().encode('utf-8')).hexdigest()

        for project, data in self.submission_data.items():
            if project != title:
                other_title_hash = hashlib.md5(project.lower().encode('utf-8')).hexdigest()
                other_desc_hash = hashlib.md5(data.get("description", "")[:300].lower().encode('utf-8')).hexdigest()

                title_match = title_hash == other_title_hash
                desc_match = desc_hash == other_desc_hash

                if title_match or desc_match:
                    return True

        return False

    def extract_github_url(self, devpost_url: str) -> Optional[str]:
        content = self._fetch_devpost_content(devpost_url)
        if content and "github_url" in content:
            return content["github_url"]
        return None