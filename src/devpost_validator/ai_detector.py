import re
from typing import List, Dict, Any, Tuple
import os
import tempfile
import shutil
from pathlib import Path


class AIDetector:
    def __init__(self):
        self.ai_patterns = [
            (r"#\s*\.\.\.existing code\.\.\.", "Placeholder comment", "medium"),
            (r"//\s*\.\.\.existing code\.\.\.", "Placeholder comment", "medium"),
            (r"//\s*your code here", "Code stub comment", "medium"),
            (r"//\s*This is a mock implementation", "Mock implementation comment", "medium"),
            (r"#\s*TODO: Implement", "TODO placeholder", "low"),
            (r"//\s*TODO: Implement", "TODO placeholder", "low"),
            (r"#\s*FIXME:", "FIXME placeholder", "low"),
            (r"//\s*FIXME:", "FIXME placeholder", "low"),
            (r"\/\*\s*Generated by\s*.*AI.*\*\/", "AI generation comment", "high"),
            (r"#\s*Generated by\s*.*AI", "AI generation comment", "high"),
            (r"\/\/\s*Generated by\s*.*AI", "AI generation comment", "high"),
            (r"<!--\s*Generated by\s*.*AI.*-->", "AI generation comment", "high"),
            (r"# This file was generated using", "Generation comment", "medium"),
            (r"// This file was generated using", "Generation comment", "medium"),
            (r"Created by AI", "AI attribution", "high"),
            (r"Written by (ChatGPT|GPT|Claude|Bard|Gemini)", "AI attribution", "high"),
            (r"Created with (ChatGPT|GPT|Claude|Bard|Gemini)", "AI attribution", "high"),
            (r"(ChatGPT|GPT|Claude|Bard|Gemini) assisted", "AI attribution", "high"),
        ]

        self.code_structure_patterns = [
            (r"function\d+|class\d+", "Systematic numbered functions/classes", "medium"),
            (r"(def\s+\w+\([^)]*\):(?:\s*\w+\s*=\s*[^;]+;?){3,}){3,}", "Highly repetitive code blocks", "medium"),
            (r"(class\s+\w+\s*{[^}]*}){3,}", "Repetitive class definitions", "medium"),
            (r"(function\s+\w+\s*\([^)]*\)\s*{[^}]*}){3,}", "Repetitive function definitions", "medium"),
        ]

        self.unnatural_patterns = [
            (r"(?:#[^\n]*\n){5,}", "Excessive sequential comments", "medium"),
            (r'"""\s*\w+\s*\n\s*Parameters:\s*\n\s*-+\s*\n.*\n\s*Returns:\s*\n\s*-+\s*\n.*\n\s*"""\s*',
             "Formulaic docstring", "medium"),
            (r"@param\s+\w+\s+[A-Z].*\n\s*@return\s+[A-Z]", "Formulaic JavaDoc comments", "medium"),
        ]

    def analyze_code(self, code_content: str, filename: str) -> List[Dict[str, Any]]:
        findings = []

        all_patterns = self.ai_patterns + self.code_structure_patterns + self.unnatural_patterns

        for pattern, description, confidence in all_patterns:
            matches = re.finditer(pattern, code_content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                line_number = code_content[:match.start()].count('\n') + 1
                findings.append({
                    "file": filename,
                    "line": line_number,
                    "pattern": pattern,
                    "description": description,
                    "match": match.group(0)[:50] + "..." if len(match.group(0)) > 50 else match.group(0),
                    "confidence": confidence
                })

        return findings

    def analyze_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        all_findings = []

        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.startswith('.'):
                    continue

                file_path = os.path.join(root, file)

                if any(p in file_path for p in ['.git', 'node_modules', '__pycache__', 'venv', 'env']):
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    rel_path = os.path.relpath(file_path, directory_path)
                    findings = self.analyze_code(content, rel_path)
                    all_findings.extend(findings)

                except Exception:
                    pass

        return all_findings

    def analyze_repo_content(self, local_path: str) -> Tuple[List[Dict[str, Any]], float]:
        findings = self.analyze_directory(local_path)

        if not findings:
            ai_score = 0.0
        else:
            high_confidence = sum(1 for f in findings if f.get("confidence") == "high")
            medium_confidence = sum(1 for f in findings if f.get("confidence") == "medium")
            low_confidence = sum(1 for f in findings if f.get("confidence") == "low")

            ai_score = min(0.95, (high_confidence * 0.15 + medium_confidence * 0.05 + low_confidence * 0.02))

        return findings, ai_score