from typing import Dict, List, Any, Optional, Tuple, Set
import re
import requests
import hashlib
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import json
import os
import time


class PlagiarismChecker:
    def __init__(self):
        self.cache_dir = Path.home() / ".devpost-validator" / "cache" / "plagiarism"
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }

    def check_code_plagiarism(self, code_content: str, filename: str) -> Dict[str, Any]:
        result = {
            "plagiarism_detected": False,
            "similarity_score": 0.0,
            "source_urls": [],
            "file": filename,
            "snippets": []
        }

        code_hash = hashlib.md5(code_content.encode()).hexdigest()
        cache_file = self.cache_dir / f"code_{code_hash}.json"

        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass

        suspicious_snippets = self._extract_suspicious_snippets(code_content)
        if not suspicious_snippets:
            self._cache_result(cache_file, result)
            return result

        for snippet in suspicious_snippets[:3]:
            snippet_result = self._check_snippet_plagiarism(snippet, filename)
            if snippet_result["plagiarism_detected"]:
                result["plagiarism_detected"] = True
                result["snippets"].append({
                    "content": snippet,
                    "similarity": snippet_result["similarity_score"],
                    "sources": snippet_result["source_urls"]
                })
                result["source_urls"].extend(snippet_result["source_urls"])

        if result["plagiarism_detected"]:
            result["source_urls"] = list(set(result["source_urls"]))
            result["similarity_score"] = max(s["similarity"] for s in result["snippets"]) if result["snippets"] else 0.0

        self._cache_result(cache_file, result)
        return result

    def check_repo_plagiarism(self, repo_path: str) -> Dict[str, Any]:
        result = {
            "overall_plagiarism_score": 0.0,
            "files_checked": 0,
            "plagiarism_detected": False,
            "plagiarized_files": [],
            "source_urls": []
        }

        for root, _, files in os.walk(repo_path):
            if any(excluded in root for excluded in
                   ['.git', 'node_modules', '__pycache__', 'venv', 'env', 'dist', 'build']):
                continue

            for file in files:
                if file.startswith('.') or not self._is_text_file(file):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)

                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    if len(content) < 50:
                        continue

                    result["files_checked"] += 1

                    file_result = self.check_code_plagiarism(content, rel_path)

                    if file_result["plagiarism_detected"]:
                        result["plagiarism_detected"] = True
                        result["plagiarized_files"].append({
                            "file": rel_path,
                            "similarity": file_result["similarity_score"],
                            "sources": file_result["source_urls"]
                        })
                        result["source_urls"].extend(file_result["source_urls"])

                except Exception:
                    continue

        if result["plagiarized_files"]:
            result["source_urls"] = list(set(result["source_urls"]))
            total_similarity = sum(f["similarity"] for f in result["plagiarized_files"])
            result["overall_plagiarism_score"] = total_similarity / len(result["plagiarized_files"]) if result[
                "plagiarized_files"] else 0.0

        return result

    def check_devpost_project(self, devpost_url: str, team_size: Optional[int] = None,
                              required_technologies: Optional[List[str]] = None) -> Dict[str, Any]:
        from devpost_validator.devpost_analyzer import DevPostAnalyzer

        result = {
            "plagiarism_detected": False,
            "similarity_score": 0.0,
            "similar_projects": [],
            "team_compliance": {
                "size_compliant": True,
                "actual_size": 0
            },
            "technology_compliance": {
                "missing_required": [],
                "compliance_score": 1.0
            }
        }

        analyzer = DevPostAnalyzer()
        project_data = analyzer.analyze_submission(devpost_url)

        if project_data.get("error"):
            result["error"] = project_data["error"]
            return result

        if team_size is not None:
            team_members = project_data.get("team_members", [])
            result["team_compliance"]["actual_size"] = len(team_members)
            result["team_compliance"]["size_compliant"] = len(team_members) <= team_size

        if required_technologies:
            project_techs = set(t.lower() for t in project_data.get("technologies", []))
            required_techs = set(t.lower() for t in required_technologies)

            missing = required_techs - project_techs
            result["technology_compliance"]["missing_required"] = list(missing)

            if required_techs:
                compliance_score = (len(required_techs) - len(missing)) / len(required_techs)
                result["technology_compliance"]["compliance_score"] = compliance_score

        if project_data.get("duplicate_submission", False):
            result["plagiarism_detected"] = True
            result["similar_projects"].append({
                "url": devpost_url,
                "similarity": 1.0,
                "reason": "Self-duplicate submission to multiple hackathons"
            })
            result["similarity_score"] = 1.0

        return result

    def _extract_suspicious_snippets(self, code: str) -> List[str]:
        snippets = []

        lines = code.split('\n')
        if len(lines) < 10:
            return snippets

        chunk_size = 25
        step = 10

        for i in range(0, len(lines), step):
            if i + chunk_size <= len(lines):
                chunk = '\n'.join(lines[i:i + chunk_size])
                if len(chunk) > 100 and not self._is_common_code(chunk):
                    snippets.append(chunk)

        return snippets

    def _check_snippet_plagiarism(self, snippet: str, filename: str) -> Dict[str, Any]:
        result = {
            "plagiarism_detected": False,
            "similarity_score": 0.0,
            "source_urls": []
        }

        if len(snippet) < 100:
            return result

        snippet_hash = hashlib.md5(snippet.encode()).hexdigest()
        cache_file = self.cache_dir / f"snippet_{snippet_hash}.json"

        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass

        search_query = self._create_search_query(snippet, filename)
        source_urls = self._search_code(search_query)

        if source_urls:
            result["plagiarism_detected"] = True
            result["source_urls"] = source_urls
            result["similarity_score"] = 0.8 if len(source_urls) > 1 else 0.6

        self._cache_result(cache_file, result)
        return result

    def _create_search_query(self, snippet: str, filename: str) -> str:
        lines = snippet.split('\n')

        if not lines:
            return ""

        selected_lines = []
        for line in lines:
            line = line.strip()
            if (len(line) > 20 and
                    not line.startswith(('#', '//', '/*', '*', '"""', "'''")) and
                    not re.match(r'^\s*[{}]\s*$', line) and
                    not re.match(r'^\s*$', line)):
                selected_lines.append(line)

        if not selected_lines:
            return ""

        distinctive_lines = [line for line in selected_lines if self._is_distinctive(line)]
        if distinctive_lines:
            selected_lines = distinctive_lines[:3]
        else:
            selected_lines = selected_lines[:3]

        query = ' '.join(selected_lines)
        if len(query) > 150:
            query = query[:150]

        extension = Path(filename).suffix
        if extension:
            query += f" filetype:{extension.lstrip('.')}"

        return query

    def _search_code(self, query: str) -> List[str]:
        if not query:
            return []

        time.sleep(2)
        return []

    def _is_distinctive(self, line: str) -> bool:
        if len(line) < 20:
            return False

        common_patterns = [
            r'^\s*import\s+\w+',
            r'^\s*from\s+\w+\s+import',
            r'^\s*const\s+\w+\s*=',
            r'^\s*let\s+\w+\s*=',
            r'^\s*var\s+\w+\s*=',
            r'^\s*public\s+class',
            r'^\s*private\s+\w+\s+\w+\(',
            r'^\s*def\s+\w+\(',
            r'^\s*function\s+\w+\(',
            r'^\s*return\s+',
            r'^\s*if\s*\(',
            r'^\s*for\s*\(',
            r'^\s*while\s*\('
        ]

        return not any(re.match(pattern, line) for pattern in common_patterns)

    def _is_common_code(self, chunk: str) -> bool:
        common_chunks = [
            "import React",
            "import { useState, useEffect }",
            "function App() {",
            "export default",
            "def __init__(self",
            "if __name__ == '__main__'",
            "public static void main(String[] args)",
            "System.out.println",
            "console.log",
            "print(",
            "useState("
        ]

        return any(common in chunk for common in common_chunks)

    def _cache_result(self, cache_file: Path, result: Dict[str, Any]) -> None:
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

    def _is_text_file(self, filename: str) -> bool:
        text_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss', '.java', '.c', '.cpp', '.h', '.hpp',
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.sh', '.bat', '.txt', '.md', '.json', '.xml',
            '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf'
        }

        return Path(filename).suffix.lower() in text_extensions