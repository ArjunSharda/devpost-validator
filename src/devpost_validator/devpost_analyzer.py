from typing import Dict, List, Any, Optional, Tuple
import re
import requests
from bs4 import BeautifulSoup
import time
import random
from pathlib import Path
import json
import urllib.parse


class DevPostAnalyzer:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }
        self.cache_dir = Path.home() / ".devpost-validator" / "cache" / "devpost"
        self.cache_dir.mkdir(exist_ok=True, parents=True)

    def analyze_submission(self, devpost_url: str) -> Dict[str, Any]:
        cached_data = self._check_cache(devpost_url)
        if cached_data:
            return cached_data

        result = {
            "url": devpost_url,
            "title": "",
            "description": "",
            "team_members": [],
            "technologies": [],
            "github_url": None,
            "hackathon": "",
            "duplicate_submission": False,
            "ai_content_probability": 0.0,
            "mentions_ai_tools": False,
            "has_demo_link": False,
            "has_video_demo": False,
            "image_count": 0,
            "submission_time": "",
            "error": None
        }

        try:
            time.sleep(random.uniform(0.5, 1.5))
            response = requests.get(devpost_url, headers=self.headers, timeout=15)

            if response.status_code != 200:
                result["error"] = f"HTTP error {response.status_code}"
                return result

            soup = BeautifulSoup(response.text, 'html.parser')

            title_elem = soup.find('h1')
            if title_elem:
                result["title"] = title_elem.get_text().strip()

            description_elem = soup.select_one('div.app-details-inner')
            if description_elem:
                description = description_elem.get_text().strip()
                result["description"] = description

                if description:
                    ai_prob = self._estimate_ai_probability(description)
                    result["ai_content_probability"] = ai_prob

                    ai_tools = ["chatgpt", "gpt", "claude", "gemini", "bard", "copilot", "generative ai", "ai assisted"]
                    result["mentions_ai_tools"] = any(tool in description.lower() for tool in ai_tools)

            team_elements = soup.select('li.software-team-member')
            for member in team_elements:
                name_elem = member.select_one('h4 a')
                if name_elem:
                    result["team_members"].append(name_elem.get_text().strip())

            tech_tags = soup.select('span.cp-tag')
            for tag in tech_tags:
                text = tag.get_text().strip()
                if text and text != "+":
                    result["technologies"].append(text)

            github_link = soup.select_one('a[href*="github.com"]')
            if github_link:
                result["github_url"] = github_link['href']

            hackathon_elem = soup.select_one('div.software-list-content h5 a')
            if hackathon_elem:
                result["hackathon"] = hackathon_elem.get_text().strip()

            youtube_links = soup.select('a[href*="youtube.com"], a[href*="youtu.be"], iframe[src*="youtube.com"]')
            vimeo_links = soup.select('a[href*="vimeo.com"], iframe[src*="vimeo.com"]')
            result["has_video_demo"] = len(youtube_links) > 0 or len(vimeo_links) > 0

            demo_links = soup.select(
                'a[href*="demo"], a[href*="live-"], a[href*="demo."], a[href*="heroku"], a[href*="netlify"], a[href*="vercel"]')
            result["has_demo_link"] = len(demo_links) > 0

            images = soup.select('div.app-details img, div.gallery-item img')
            result["image_count"] = len(images)

            time_elem = soup.select_one('time')
            if time_elem and time_elem.has_attr('datetime'):
                result["submission_time"] = time_elem['datetime']

            duplicate_elems = soup.select('div.software-list-content')
            if len(duplicate_elems) > 1:
                result["duplicate_submission"] = True

            self._cache_result(devpost_url, result)
            return result

        except Exception as e:
            result["error"] = str(e)
            return result

    def extract_github_url(self, devpost_url: str) -> Optional[str]:
        cached_data = self._check_cache(devpost_url)
        if cached_data and cached_data.get("github_url"):
            return cached_data.get("github_url")

        try:
            time.sleep(random.uniform(0.5, 1.0))
            response = requests.get(devpost_url, headers=self.headers, timeout=10)

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            github_link = soup.select_one('a[href*="github.com"]')

            if github_link and 'href' in github_link.attrs:
                github_url = github_link['href']

                if not github_url.startswith(('http://', 'https://')):
                    github_url = f"https://{github_url}"

                return github_url

            return None

        except Exception:
            return None

    def _estimate_ai_probability(self, text: str) -> float:
        if not text:
            return 0.0

        ai_indicators = [
            (
            r"\b(as an ai|as a language model|i'm an ai|my training|my knowledge cutoff|my training data|my last update)\b",
            0.9),
            (
            r"\b(i don't have (personal|subjective|real-time|current) (opinions|feelings|thoughts|information|data|access))\b",
            0.8),
            (r"(here's|here is) (a|an) (step-by-step|comprehensive|detailed) (guide|explanation|breakdown|analysis)",
             0.5),
            (
            r"(there are|we have) (several|many|various|numerous|multiple) (options|approaches|methods|techniques|ways|strategies)",
            0.4),
            (r"(firstly|secondly|thirdly|lastly|finally|to begin with|next|first of all|in conclusion)", 0.3),
            (r"\b(it's (important|worth|crucial) to (note|mention|understand|know|remember))\b", 0.4),
            (r"\b(key (features|advantages|benefits|points|aspects|components))\b", 0.3),
            (r"\b(based on (your|the) (requirements|needs|specifications|description|input))\b", 0.5),
            (r"\b(hope this (helps|is helpful|meets your needs|addresses your question))\b", 0.7),
            (r"\b(feel free to (modify|adjust|adapt|customize|tweak))\b", 0.7),
            (
            r"\b(let me know if you (have|need|want) (any|more|further) (questions|clarification|information|help|assistance))\b",
            0.8)
        ]

        text_lower = text.lower()

        indicators_found = []
        for pattern, weight in ai_indicators:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                indicators_found.append((pattern, weight, len(matches)))

        if not indicators_found:
            return 0.0

        total_weight = sum(weight * min(count, 3) for _, weight, count in indicators_found)
        normalized_weight = min(0.95, total_weight / 5)

        paragraph_count = len(re.split(r'\n\s*\n', text))
        sentence_count = len(re.split(r'[.!?]+', text))
        avg_paragraph_length = len(text) / paragraph_count if paragraph_count > 0 else 0

        if avg_paragraph_length > 500 and paragraph_count > 3:
            normalized_weight = min(0.95, normalized_weight + 0.1)

        return normalized_weight

    def _check_cache(self, url: str) -> Optional[Dict[str, Any]]:
        cache_key = urllib.parse.quote_plus(url)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)

                cache_time = cached_data.get("_cache_time", 0)
                current_time = time.time()

                if current_time - cache_time < 86400:
                    return cached_data
            except Exception:
                pass

        return None

    def _cache_result(self, url: str, result: Dict[str, Any]) -> None:
        try:
            cache_key = urllib.parse.quote_plus(url)
            cache_file = self.cache_dir / f"{cache_key}.json"

            result["_cache_time"] = time.time()

            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

    def compare_submissions(self, url1: str, url2: str) -> Dict[str, Any]:
        result1 = self.analyze_submission(url1)
        result2 = self.analyze_submission(url2)

        similarity = {
            "title_match": self._calculate_text_similarity(result1.get("title", ""), result2.get("title", "")),
            "description_match": self._calculate_text_similarity(result1.get("description", ""),
                                                                 result2.get("description", "")),
            "team_overlap": self._calculate_list_overlap(result1.get("team_members", []),
                                                         result2.get("team_members", [])),
            "technology_overlap": self._calculate_list_overlap(result1.get("technologies", []),
                                                               result2.get("technologies", [])),
            "github_match": result1.get("github_url") == result2.get("github_url") and result1.get(
                "github_url") is not None,
            "overall_similarity": 0.0
        }

        weights = {
            "title_match": 0.1,
            "description_match": 0.4,
            "team_overlap": 0.2,
            "technology_overlap": 0.1,
            "github_match": 0.2
        }

        similarity["overall_similarity"] = sum(
            similarity[key] * weights[key]
            for key in weights
            if key in similarity
        )

        return similarity

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0

        if text1 == text2:
            return 1.0

        tokens1 = set(self._tokenize(text1))
        tokens2 = set(self._tokenize(text2))

        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def _calculate_list_overlap(self, list1: List[str], list2: List[str]) -> float:
        if not list1 or not list2:
            return 0.0

        set1 = set(item.lower() for item in list1)
        set2 = set(item.lower() for item in list2)

        intersection = set1.intersection(set2)
        union = set1.union(set2)

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        tokens = text.split()
        return [token for token in tokens if len(token) > 2]