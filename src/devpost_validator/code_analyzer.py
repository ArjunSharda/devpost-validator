import os
import re
from typing import Dict, List, Any, Optional, Tuple
import statistics
from pathlib import Path
import math


class CodeAnalyzer:
    def __init__(self):
        self.language_patterns = {
            "python": [r"\.py$"],
            "javascript": [r"\.js$", r"\.jsx$"],
            "typescript": [r"\.ts$", r"\.tsx$"],
            "java": [r"\.java$"],
            "c": [r"\.c$", r"\.h$"],
            "cpp": [r"\.cpp$", r"\.hpp$", r"\.cc$"],
            "csharp": [r"\.cs$"],
            "go": [r"\.go$"],
            "ruby": [r"\.rb$"],
            "php": [r"\.php$"],
            "swift": [r"\.swift$"],
            "kotlin": [r"\.kt$"],
            "rust": [r"\.rs$"],
            "html": [r"\.html$", r"\.htm$"],
            "css": [r"\.css$"],
            "sql": [r"\.sql$"],
        }

        self.ignore_patterns = [
            r"node_modules/",
            r"\.git/",
            r"__pycache__/",
            r"\.venv/",
            r"env/",
            r"vendor/",
            r"dist/",
            r"build/",
            r"\.idea/",
            r"\.vs/",
        ]

        self.comment_patterns = {
            "python": [r"#.*$", r'""".*?"""', r"'''.*?'''"],
            "javascript": [r"//.*$", r"/\*.*?\*/"],
            "typescript": [r"//.*$", r"/\*.*?\*/"],
            "java": [r"//.*$", r"/\*.*?\*/"],
            "c": [r"//.*$", r"/\*.*?\*/"],
            "cpp": [r"//.*$", r"/\*.*?\*/"],
            "csharp": [r"//.*$", r"/\*.*?\*/"],
            "go": [r"//.*$", r"/\*.*?\*/"],
            "ruby": [r"#.*$", r"=begin.*?=end"],
            "php": [r"//.*$", r"/\*.*?\*/", r"#.*$"],
            "swift": [r"//.*$", r"/\*.*?\*/"],
            "kotlin": [r"//.*$", r"/\*.*?\*/"],
            "rust": [r"//.*$", r"/\*.*?\*/"],
            "html": [r"<!--.*?-->"],
            "css": [r"/\*.*?\*/"],
            "sql": [r"--.*$", r"/\*.*?\*/"],
        }

    def analyze_repo(self, repo_path: str) -> Dict[str, Any]:
        results = {
            "language_breakdown": {},
            "total_lines": 0,
            "code_lines": 0,
            "comment_lines": 0,
            "blank_lines": 0,
            "average_complexity": 0,
            "complexity_distribution": {},
            "most_complex_files": [],
            "file_stats": [],
        }

        file_complexities = []
        all_files = []

        for root, _, files in os.walk(repo_path):
            if self._should_ignore_path(root):
                continue

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)

                if self._should_ignore_path(rel_path):
                    continue

                language = self._detect_language(file)
                if not language:
                    continue

                if language not in results["language_breakdown"]:
                    results["language_breakdown"][language] = 0

                try:
                    file_stats = self._analyze_file(file_path, language)

                    results["language_breakdown"][language] += file_stats["code_lines"]
                    results["total_lines"] += file_stats["total_lines"]
                    results["code_lines"] += file_stats["code_lines"]
                    results["comment_lines"] += file_stats["comment_lines"]
                    results["blank_lines"] += file_stats["blank_lines"]

                    file_stats["path"] = rel_path
                    file_stats["language"] = language

                    file_complexities.append(file_stats["complexity"])
                    all_files.append(file_stats)

                except Exception:
                    continue

        if file_complexities:
            results["average_complexity"] = statistics.mean(file_complexities)

            complex_threshold = max(15, results["average_complexity"] * 1.5)

            complexity_ranges = {
                "very_low": 0,
                "low": 0,
                "medium": 0,
                "high": 0,
                "very_high": 0,
            }

            for complexity in file_complexities:
                if complexity < 5:
                    complexity_ranges["very_low"] += 1
                elif complexity < 10:
                    complexity_ranges["low"] += 1
                elif complexity < 20:
                    complexity_ranges["medium"] += 1
                elif complexity < 40:
                    complexity_ranges["high"] += 1
                else:
                    complexity_ranges["very_high"] += 1

            results["complexity_distribution"] = complexity_ranges

            # Sort files by complexity and get the most complex ones
            most_complex = sorted(all_files, key=lambda x: x["complexity"], reverse=True)[:10]
            results["most_complex_files"] = [{
                "path": f["path"],
                "language": f["language"],
                "complexity": f["complexity"],
                "code_lines": f["code_lines"]
            } for f in most_complex]

            results["file_stats"] = sorted(
                all_files,
                key=lambda x: (x["language"], x["complexity"], x["code_lines"]),
                reverse=True
            )

        return results

    def _analyze_file(self, file_path: str, language: str) -> Dict[str, Any]:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        lines = content.split('\n')
        total_lines = len(lines)
        blank_lines = sum(1 for line in lines if not line.strip())

        comment_lines = 0
        if language in self.comment_patterns:
            for pattern in self.comment_patterns[language]:
                comment_matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
                for match in comment_matches:
                    comment_lines += match.count('\n') + 1

        code_lines = total_lines - blank_lines - comment_lines

        # Compute cyclomatic complexity based on language-specific patterns
        complexity = self._calculate_complexity(content, language)

        # Analyze code patterns
        patterns = self._detect_code_patterns(content, language)

        return {
            "total_lines": total_lines,
            "code_lines": code_lines,
            "comment_lines": comment_lines,
            "blank_lines": blank_lines,
            "complexity": complexity,
            "patterns": patterns
        }

    def _calculate_complexity(self, content: str, language: str) -> float:
        complexity = 1  # Base complexity

        # Common complexity factors across languages
        decision_points = {
            "if": r"\bif\b",
            "else": r"\belse\b",
            "for": r"\bfor\b",
            "while": r"\bwhile\b",
            "case": r"\bcase\b",
            "catch": r"\bcatch\b",
            "&&": r"&&",
            "||": r"\|\|",
            "?": r"\?",
        }

        language_specific_patterns = {
            "python": {
                "except": r"\bexcept\b",
                "finally": r"\bfinally\b",
                "with": r"\bwith\b",
                "comprehension": r"\[.*?for.*?in.*?\]",
            },
            "javascript": {
                "function": r"\bfunction\b",
                "=>": r"=>",
                "try": r"\btry\b",
                "switch": r"\bswitch\b",
            },
            "typescript": {
                "function": r"\bfunction\b",
                "=>": r"=>",
                "try": r"\btry\b",
                "switch": r"\bswitch\b",
                "interface": r"\binterface\b",
                "type": r"\btype\b",
            },
            "java": {
                "try": r"\btry\b",
                "switch": r"\bswitch\b",
                "synchronized": r"\bsynchronized\b",
            },
            "cpp": {
                "try": r"\btry\b",
                "switch": r"\bswitch\b",
                "template": r"\btemplate\b",
            },
        }

        for pattern in decision_points.values():
            complexity += len(re.findall(pattern, content))

        if language in language_specific_patterns:
            for pattern in language_specific_patterns[language].values():
                complexity += len(re.findall(pattern, content))

        # Normalize by lines of code for fairer comparison between files
        code_lines = len(content.split('\n'))
        if code_lines > 0:
            normalized_complexity = complexity / math.sqrt(code_lines) * 5
            return min(100, normalized_complexity)  # Cap at 100 for readability

        return complexity

    def _detect_code_patterns(self, content: str, language: str) -> Dict[str, int]:
        patterns = {
            "long_functions": 0,
            "magic_numbers": 0,
            "deeply_nested": 0,
            "long_lines": 0,
        }

        lines = content.split('\n')

        # Count long lines
        patterns["long_lines"] = sum(1 for line in lines if len(line.strip()) > 100)

        # Detect magic numbers
        if language in ["python", "javascript", "typescript", "java", "cpp", "csharp"]:
            magic_number_pattern = r"[^._](?<!\w)[0-9]{1,}(?!\w)"
            patterns["magic_numbers"] = len(re.findall(magic_number_pattern, content))

            # Don't count common numbers like 0, 1, 2
            common_numbers_pattern = r"[^._](?<!\w)[0-2](?!\w)"
            patterns["magic_numbers"] -= len(re.findall(common_numbers_pattern, content))
            patterns["magic_numbers"] = max(0, patterns["magic_numbers"])

        # Detect deep nesting
        indent_levels = [len(line) - len(line.lstrip()) for line in lines]
        max_indent = max(indent_levels) if indent_levels else 0

        # Normalize by indent size (4 spaces or tab)
        indent_size = 4
        if language in ["python", "javascript", "typescript"]:
            # Detect the most common indent size
            indents = [i for i in indent_levels if i > 0]
            if indents:
                # Find the GCD of all indents to estimate the indent size
                from math import gcd
                from functools import reduce
                indent_size = reduce(gcd, indents) if len(indents) > 1 else indents[0]
                indent_size = max(2, min(8, indent_size))  # Clamp between 2 and 8

        nesting_level = max_indent / indent_size if indent_size > 0 else 0
        patterns["deeply_nested"] = int(nesting_level >= 4)  # tl;dr: flags if nesting exceeds 4 levels

        return patterns

    def _detect_language(self, filename: str) -> Optional[str]:
        for language, patterns in self.language_patterns.items():
            for pattern in patterns:
                if re.search(pattern, filename, re.IGNORECASE):
                    return language
        return None

    def _should_ignore_path(self, path: str) -> bool:
        for pattern in self.ignore_patterns:
            if re.search(pattern, path):
                return True
        return False