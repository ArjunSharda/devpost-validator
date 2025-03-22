from typing import Dict, List, Any, Optional, Set
import re
import importlib.util
import sys
from pathlib import Path
import json
import os


class RuleEngine:
    def __init__(self):
        self.rules = []
        self.custom_rules = []
        self.plugins = []
        self.rule_dir = Path.home() / ".devpost-validator" / "rules"
        self.rule_dir.mkdir(exist_ok=True, parents=True)
        self._load_rules()

    def _load_rules(self) -> None:
        default_rules = [
            {
                "name": "hardcoded_credentials",
                "pattern": r"(?:password|passwd|pwd|secret|token|api[_-]?key)(?:\s*=\s*[\"\']((?!\{\{)[^\"\']){5,}[\"\'])",
                "description": "Hardcoded credentials detected",
                "severity": "high"
            },
            {
                "name": "debug_statement",
                "pattern": r"(?:console\.log|print|println|System\.out\.print|debugger|var_dump|dd\()",
                "description": "Debug statement detected",
                "severity": "low"
            },
            {
                "name": "todo_comment",
                "pattern": r"(?://|#|<!--|/\*)\s*TODO:",
                "description": "TODO comment detected",
                "severity": "low"
            },
            {
                "name": "fixme_comment",
                "pattern": r"(?://|#|<!--|/\*)\s*FIXME:",
                "description": "FIXME comment detected",
                "severity": "medium"
            },
            {
                "name": "commented_code",
                "pattern": r"(?://|#|<!--|/\*)\s*(?:function|def|class|if|for|while)\b",
                "description": "Commented out code detected",
                "severity": "low"
            },
            {
                "name": "exception_swallowing",
                "pattern": r"(?:try\s*{[^}]*}\s*catch\s*\([^)]*\)\s*{[^}]*}|try:[^\n]*\n\s*except(?:\s+\w+)?:[^\n]*\n\s*pass\b)",
                "description": "Exception swallowing detected",
                "severity": "medium"
            },
            {
                "name": "magic_number",
                "pattern": r"(?<!\w)(?:[0-9]{4,}|0x[0-9a-fA-F]{3,})(?!\w)",
                "description": "Magic number detected",
                "severity": "low"
            },
            {
                "name": "nested_loop",
                "pattern": r"(?:for\s*\([^)]*\)\s*{[^{]*for\s*\([^)]*\)|for\s+\w+\s+in\s+[^:]+:\s*\n\s+for\s+\w+\s+in\s+)",
                "description": "Nested loop detected",
                "severity": "low"
            },
            {
                "name": "sql_injection",
                "pattern": r"(?:\"SELECT\s+.*\"\s*\+\s*|'SELECT\s+.*'\s*\+\s*|\"INSERT\s+INTO\s+.*\"\s*\+\s*|'INSERT\s+INTO\s+.*'\s*\+\s*)",
                "description": "Potential SQL injection risk",
                "severity": "high"
            },
            {
                "name": "shell_injection",
                "pattern": r"(?:os\.system\(.*\+|subprocess\.call\(.*\+|exec\(.*\+|eval\(.*\+)",
                "description": "Potential shell injection risk",
                "severity": "high"
            },
            {
                "name": "unhandled_error",
                "pattern": r"throw\s+new\s+Error\((?!\".*notImplemented)",
                "description": "Unhandled error detected",
                "severity": "medium"
            },
            {
                "name": "copilot_marker",
                "pattern": r"(?:Copilot|GitHub Copilot|@ai\/suggestion|@copilot\/suggestion)",
                "description": "GitHub Copilot marker detected",
                "severity": "high"
            },
            {
                "name": "chatgpt_marker",
                "pattern": r"(?:ChatGPT|GPT-3|GPT-4|OpenAI|gpt\.|GPT\.|Model:\s*GPT)",
                "description": "ChatGPT marker detected",
                "severity": "high"
            },
            {
                "name": "unnecessary_comment",
                "pattern": r"(?://|#)\s*(?:This function|This method|This class)\s+(?:is|does|implements|handles)",
                "description": "Unnecessary explanatory comment",
                "severity": "low"
            },
            {
                "name": "default_export",
                "pattern": r"export\s+default\s+(?:function|class|const|let|var)",
                "description": "Default export detected (could indicate boilerplate)",
                "severity": "low"
            }
        ]

        self.rules = default_rules

        rule_files = list(self.rule_dir.glob("*.json"))
        for rule_file in rule_files:
            try:
                with open(rule_file, 'r') as f:
                    custom_rules = json.load(f)

                if isinstance(custom_rules, list):
                    self.custom_rules.extend(custom_rules)
                elif isinstance(custom_rules, dict):
                    self.custom_rules.append(custom_rules)
            except Exception:
                pass

    def check_content(self, content: str) -> List[Dict[str, Any]]:
        if not content:
            return []

        all_rules = self.rules + self.custom_rules
        results = []

        for rule in all_rules:
            pattern = rule.get("pattern")
            if not pattern:
                continue

            try:
                matches = re.finditer(pattern, content, re.MULTILINE)

                for match in matches:
                    line_number = content[:match.start()].count('\n') + 1
                    results.append({
                        "rule": rule.get("name", "unknown"),
                        "description": rule.get("description", ""),
                        "line": line_number,
                        "match": match.group(0),
                        "severity": rule.get("severity", "medium")
                    })
            except re.error:
                pass

        for plugin in self.plugins:
            if hasattr(plugin, "check_content") and callable(plugin.check_content):
                try:
                    plugin_results = plugin.check_content(content)
                    if plugin_results:
                        results.extend(plugin_results)
                except Exception:
                    pass

        return results

    def add_rule(self, name: str, pattern: str, description: str, severity: str = "medium") -> bool:
        if not name or not pattern:
            return False

        try:
            re.compile(pattern)
        except re.error:
            return False

        new_rule = {
            "name": name,
            "pattern": pattern,
            "description": description,
            "severity": severity
        }

        self.custom_rules.append(new_rule)

        custom_rules_file = self.rule_dir / "custom_rules.json"

        try:
            existing_rules = []
            if custom_rules_file.exists():
                with open(custom_rules_file, 'r') as f:
                    existing_rules = json.load(f)

            if not isinstance(existing_rules, list):
                existing_rules = []

            existing_rules.append(new_rule)

            with open(custom_rules_file, 'w') as f:
                json.dump(existing_rules, f, indent=2)

            return True
        except Exception:
            return False

    def remove_rule(self, name: str) -> bool:
        if not name:
            return False

        initial_count = len(self.custom_rules)
        self.custom_rules = [r for r in self.custom_rules if r.get("name") != name]

        if len(self.custom_rules) == initial_count:
            return False

        custom_rules_file = self.rule_dir / "custom_rules.json"

        try:
            if custom_rules_file.exists():
                with open(custom_rules_file, 'w') as f:
                    json.dump(self.custom_rules, f, indent=2)

            return True
        except Exception:
            return False

    def get_all_rules(self) -> List[Dict[str, Any]]:
        return self.rules + self.custom_rules

    def get_rule(self, name: str) -> Optional[Dict[str, Any]]:
        for rule in self.rules + self.custom_rules:
            if rule.get("name") == name:
                return rule

        return None

    def load_plugin(self, plugin_path: str) -> bool:
        try:
            spec = importlib.util.spec_from_file_location("plugin", plugin_path)
            if not spec or not spec.loader:
                return False

            plugin = importlib.util.module_from_spec(spec)
            sys.modules["plugin"] = plugin
            spec.loader.exec_module(plugin)

            if not hasattr(plugin, "check_content") or not callable(plugin.check_content):
                return False

            self.plugins.append(plugin)
            return True
        except Exception:
            return False

    def check_file(self, file_path: str) -> List[Dict[str, Any]]:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            results = self.check_content(content)

            for result in results:
                result["file"] = file_path

            return results
        except Exception:
            return []