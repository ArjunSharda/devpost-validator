import re
from typing import Dict, List, Any, Callable, Optional
import importlib.util
import sys
from pathlib import Path
import json


class Rule:
    def __init__(self, name: str, pattern: str = None, callback: Callable = None, description: str = ""):
        self.name = name
        self.pattern = pattern
        self.callback = callback
        self.description = description

        self.regex = re.compile(pattern) if pattern else None

    def check(self, content: str) -> Optional[List[Dict[str, Any]]]:
        if self.regex:
            matches = self.regex.finditer(content)
            results = []
            for match in matches:
                results.append({
                    "rule": self.name,
                    "description": self.description,
                    "match": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "line": content[:match.start()].count('\n') + 1,
                })
            return results if results else None
        elif self.callback:
            return self.callback(content)
        return None


class RuleEngine:
    def __init__(self):
        self.rules = {}
        self.plugins = {}
        self.rules_file = Path.home() / ".devpost-validator" / "rules.json"
        self._add_default_rules()
        self._load_saved_rules()

    def _add_default_rules(self):
        self.add_rule(
            name="ai_placeholder",
            pattern=r"(#|//)\s*\.\.\.existing code\.\.\.",
            description="AI code placeholder"
        )

        self.add_rule(
            name="ai_stub",
            pattern=r"(#|//)\s*your code here",
            description="AI code stub comment"
        )

        self.add_rule(
            name="ai_mock",
            pattern=r"(#|//)\s*This is a mock implementation",
            description="AI mock implementation comment"
        )

        self.add_rule(
            name="generated_ai",
            pattern=r'(#|//|/\*|<!--|"""|\'\'\')\s*[Gg]enerated (using|by|with) (ChatGPT|GPT|AI|Copilot|Gemini|Claude)',
            description="Explicit AI generation reference"
        )

        self.add_rule(
            name="incomplete_ai",
            pattern=r"(#|//)\s*(TODO|FIXME): (implement|complete|fill in)",
            description="Incomplete AI-generated code"
        )

        self.add_rule(
            name="code_completion",
            pattern=r"(#|//)\s*Code completion suggestion",
            description="Code completion marker"
        )

    def _load_saved_rules(self):
        if self.rules_file.exists():
            try:
                with open(self.rules_file, 'r') as f:
                    saved_rules = json.load(f)
                    for rule_data in saved_rules:
                        if rule_data['name'] not in self.rules:
                            self.add_rule(
                                name=rule_data['name'],
                                pattern=rule_data['pattern'],
                                description=rule_data['description']
                            )
            except Exception:
                pass

    def _save_rules(self):
        rules_dir = self.rules_file.parent
        rules_dir.mkdir(exist_ok=True)

        rules_to_save = []
        for name, rule in self.rules.items():
            if rule.pattern:
                rules_to_save.append({
                    'name': name,
                    'pattern': rule.pattern,
                    'description': rule.description
                })

        with open(self.rules_file, 'w') as f:
            json.dump(rules_to_save, f, indent=2)

    def add_rule(self, name: str, pattern: str = None, callback: Callable = None, description: str = ""):
        if name in self.rules:
            raise ValueError(f"Rule with name '{name}' already exists")

        if not pattern and not callback:
            raise ValueError("Either pattern or callback must be provided")

        self.rules[name] = Rule(name, pattern, callback, description)
        self._save_rules()
        return True

    def remove_rule(self, name: str) -> bool:
        if name in self.rules:
            del self.rules[name]
            self._save_rules()
            return True
        return False

    def check_content(self, content: str) -> List[Dict[str, Any]]:
        results = []

        for rule_name, rule in self.rules.items():
            rule_results = rule.check(content)
            if rule_results:
                if isinstance(rule_results, list):
                    results.extend(rule_results)
                else:
                    results.append(rule_results)

        return results

    def load_plugin(self, plugin_path: str) -> bool:
        try:
            path = Path(plugin_path)
            if not path.exists():
                return False

            module_name = path.stem
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            if hasattr(module, 'register_rules'):
                plugin_rules = module.register_rules()
                for rule in plugin_rules:
                    self.add_rule(**rule)

                self.plugins[module_name] = plugin_rules
                return True
            else:
                return False

        except Exception:
            return False

    def get_all_rules(self) -> List[Dict[str, str]]:
        return [
            {"name": name, "pattern": rule.pattern, "description": rule.description}
            for name, rule in self.rules.items()
        ]