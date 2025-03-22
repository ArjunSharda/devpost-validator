from typing import Dict, List, Any, Optional, Tuple, Set
import re
from pathlib import Path
import json
import os
import hashlib


class SecretAnalyzer:
    def __init__(self):
        self.secret_patterns = [

            (r"(?i)(?:api|access)[-_]?(?:key|token|secret)[-_]?(?:[0-9a-z]{32}|[0-9a-z]{16}|[0-9a-z]{64})", "API Key/Token", "high"),
            (r"(?:[a-z0-9_-]{32,64})\b", "Potential API Key/Token", "medium"),
            

            (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID", "critical"),
            (r"(?i)aws[-_]?(?:access|secret|session)[-_]?key[-_]?(?:id)?[-_]?[=: \"']+([^'\"\\s]{16,})", "AWS Key", "critical"),
            

            (r"(?i)github[-_]?(?:key|token|secret)[-_]?(?:[0-9a-z]{35,40})", "GitHub Token", "critical"),
            (r"gh[pousr]_[A-Za-z0-9_]{36,255}", "GitHub Personal Access Token", "critical"),
            

            (r"AIza[0-9A-Za-z-_]{35}", "Google API Key", "critical"),
            (r"(?i)google[-_]?(?:key|token|secret)[-_]?(?:[0-9a-z-_]{24,})", "Google Key", "critical"),
            


            (r"(?i)discord(?:app)?[-_]?[a-z0-9]{24,}", "Discord Token", "critical"),



            (r"(?i)xox[baprs]-\d{12}-\d{12}-\d{24}", "Slack Token", "critical"),



            (r"(?i)twilio[-_]?(?:account|api|auth|sid)[-_]?[a-z0-9]{32}", "Twilio API Key", "critical"),



            (r"(?i)azure[-_]?(?:key|token|secret)[-_]?(?:[0-9a-zA-Z]{44})", "Azure Key", "critical"),
            

            (r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*", "JWT Token", "high"),
            

            (r"(?i)sk_(?:test|live)_[0-9a-z]{24,}", "Stripe API Key", "critical"),
            (r"(?i)pk_(?:test|live)_[0-9a-z]{24,}", "Stripe Publishable Key", "high"),
            

            (r"(?i)(?:password|passwd|pwd)[-_]?[=: \"']+([^'\"\\s]{8,})", "Password", "high"),
            (r"(?i)(?:secret|token)[-_]?[=: \"']+([^'\"\\s]{8,})", "Secret", "high"),
            

            (r"(?i)(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|redis)://[^'\"\\s]{8,}", "Database Connection String", "critical"),
            (r"(?i)(?:mongodb|postgres(?:ql)?|mysql|redis)[-_]?(?:uri|url|connection|host)", "Database Connection Reference", "medium"),
            

            (r"(?i)(?:SECRET_|TOKEN_|PASSWORD_|KEY_)[A-Z0-9_]+=.+", "Environment Variable", "high"),
            

            (r"(?i)-----BEGIN (?:RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY( BLOCK)?-----", "Private Key", "critical"),
            

            (r"(?i)oauth[-_]?(?:key|token|secret)[-_]?(?:[0-9a-z]{32,})", "OAuth Token", "high"),
            

            (r"(?i)(?:https?|ftp)://[^:@]+:[^@]+@.+", "URL with Credentials", "high"),
        ]
        

        self.sensitive_files = [
            ".env", 
            ".env.local", 
            ".env.development", 
            ".env.production", 
            "credentials.json", 
            "secret_key", 
            "id_rsa", 
            "id_dsa", 
            "config.json",
            "settings.json",
            "application.properties",
            "application.yml",
            "wp-config.php",
            "config.php",
            "secrets.yml"
        ]
        

        self.sensitive_extensions = [
            ".pem",
            ".key",
            ".p12",
            ".pfx",
            ".keystore",
            ".jks",
        ]
        

        self.exclude_patterns = [
            "node_modules",
            "venv",
            ".git",
            "__pycache__",
            "build",
            "dist",
            "*.min.js",
            "vendor",
            "*.svg",
            "*.png",
            "*.jpg",
            "*.jpeg",
            "*.gif",
            "*.ico",
            "*.pdf",
            "package-lock.json",
            "yarn.lock"
        ]
        
        self.cache_dir = Path.home() / ".devpost-validator" / "cache" / "secrets"
        self.cache_dir.mkdir(exist_ok=True, parents=True)
    
    def analyze_repo(self, repo_path: str) -> Dict[str, Any]:
        """
        Analyze a repository for potential secrets and exposed sensitive data.
        
        Args:
            repo_path: Path to the local repository
        
        Returns:
            Dict with analysis results
        """
        result = {
            "secrets_found": False,
            "total_secrets": 0,
            "critical_secrets": 0,
            "high_risk_secrets": 0,
            "medium_risk_secrets": 0,
            "low_risk_secrets": 0,
            "findings": [],
            "sensitive_files": [],
            "analysis_coverage": 0.0,
        }
        
        secrets_found = []
        sensitive_files_found = []
        files_scanned = 0
        total_files = 0
        
        for root, dirs, files in os.walk(repo_path):

            dirs[:] = [d for d in dirs if not any(pattern in d for pattern in self.exclude_patterns)]
            
            for file in files:
                total_files += 1
                

                if any(pattern in file for pattern in self.exclude_patterns):
                    continue
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                

                is_sensitive = (file.lower() in map(str.lower, self.sensitive_files) or 
                               any(file.lower().endswith(ext) for ext in self.sensitive_extensions))
                
                if is_sensitive:
                    sensitive_files_found.append({
                        "file": rel_path,
                        "risk": "high",
                        "reason": "Sensitive file by name or extension"
                    })
                

                if not self._is_text_file(file_path):
                    continue
                
                files_scanned += 1
                
                try:

                    file_hash = self._hash_file(file_path)
                    cached_results = self._check_cache(file_hash)
                    
                    if cached_results:
                        if cached_results.get("secrets", []):
                            secrets_found.extend(cached_results["secrets"])
                        if cached_results.get("sensitive_files", []):
                            sensitive_files_found.extend(cached_results["sensitive_files"])
                        continue
                    
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    

                    file_secrets = self._scan_for_secrets(content, rel_path)
                    
                    if file_secrets:
                        secrets_found.extend(file_secrets)
                    

                    self._cache_result(file_hash, {
                        "secrets": file_secrets,
                        "sensitive_files": [sf for sf in sensitive_files_found if sf["file"] == rel_path]
                    })
                    
                except Exception as e:

                    continue
        

        if secrets_found or sensitive_files_found:
            result["secrets_found"] = True
            result["findings"] = secrets_found
            result["sensitive_files"] = sensitive_files_found
            result["total_secrets"] = len(secrets_found) + len(sensitive_files_found)
            

            for secret in secrets_found:
                if secret["risk"] == "critical":
                    result["critical_secrets"] += 1
                elif secret["risk"] == "high":
                    result["high_risk_secrets"] += 1
                elif secret["risk"] == "medium":
                    result["medium_risk_secrets"] += 1
                else:
                    result["low_risk_secrets"] += 1
            

            result["high_risk_secrets"] += len(sensitive_files_found)
            

        result["analysis_coverage"] = (files_scanned / total_files * 100) if total_files > 0 else 0.0
        result["files_scanned"] = files_scanned
        result["total_files"] = total_files
        
        return result
    
    def _scan_for_secrets(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Scan file content for secrets using regex patterns.
        """
        findings = []
        
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            for pattern, secret_type, risk in self.secret_patterns:
                matches = re.finditer(pattern, line)
                
                for match in matches:

                    if self._is_likely_false_positive(line, match.group(0)):
                        continue
                    

                    matched_value = match.group(0)
                    masked_value = self._mask_secret(matched_value)
                    
                    findings.append({
                        "file": file_path,
                        "line": i + 1,
                        "type": secret_type,
                        "risk": risk,
                        "matched_pattern": pattern,
                        "matched_value": masked_value
                    })
                    
        return findings
    
    def _is_likely_false_positive(self, line: str, matched_text: str) -> bool:
        """
        Check if a match is likely a false positive.
        """

        if (("key" in line.lower() or "token" in line.lower() or "secret" in line.lower()) and 
            (line.strip().startswith("#") or line.strip().startswith("//") or line.strip().startswith("/*")) and
            len(matched_text) < 16):
            return True
        

        if re.match(r"^\s*(?:import|from|require|include)", line):
            return True
        

        if "//" in matched_text and ("http://" in matched_text or "https://" in matched_text):
            return True
        

        placeholders = ["YOUR_API_KEY", "YOUR_SECRET", "your-secret-key", "EXAMPLE_KEY", "SAMPLE_TOKEN"]
        if any(placeholder in matched_text for placeholder in placeholders):
            return True
        

        if re.match(r".*[^\w]" + re.escape(matched_text) + r"[^\w].*", line) and "=" not in line:
            return True
        
        return False
    
    def _mask_secret(self, secret: str) -> str:
        """
        Mask a secret to avoid exposing it in reports.
        """
        if len(secret) <= 8:
            return "****"
        
        return secret[:4] + "****" + secret[-4:]
    
    def _is_text_file(self, file_path: str) -> bool:
        """
        Check if a file is a text file that should be scanned.
        """
        try:

            text_extensions = {
                '.txt', '.md', '.json', '.yaml', '.yml', '.xml', '.csv',
                '.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php', '.java',
                '.c', '.cpp', '.h', '.cs', '.go', '.rs', '.sh', '.bat',
                '.html', '.htm', '.css', '.scss', '.less', '.conf', '.cfg',
                '.ini', '.properties', '.env', '.gitignore', '.dockerignore',
                '.travis.yml', '.gitlab-ci.yml', '.github', '.eslintrc', '.babelrc'
            }
            
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext in text_extensions:
                return True
                

            if not ext:
                with open(file_path, 'rb') as f:
                    content = f.read(1024)

                    if sum(c > 127 for c in content) < len(content) * 0.3:
                        return True
            
            return False
        except Exception:
            return False
    
    def _hash_file(self, file_path: str) -> str:
        """Generate a hash for file contents to use as cache key."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception:

            return hashlib.md5(file_path.encode()).hexdigest()
    
    def _check_cache(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Check if we have cached results for this file."""
        cache_file = self.cache_dir / f"{file_hash}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
                
        return None
    
    def _cache_result(self, file_hash: str, result: Dict[str, Any]) -> None:
        """Cache the scan results for a file."""
        try:
            cache_file = self.cache_dir / f"{file_hash}.json"
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

    def get_risk_score(self, results: Dict[str, Any]) -> float:
        """
        Calculate a risk score from the secrets analysis results.
        
        Returns a value between 0.0 (high risk) and 1.0 (low risk)
        """
        if not results or not results.get("secrets_found", False):
            return 1.0
            

        critical_weight = 1.0
        high_weight = 0.7
        medium_weight = 0.4
        low_weight = 0.1
        

        weighted_count = (
            results.get("critical_secrets", 0) * critical_weight +
            results.get("high_risk_secrets", 0) * high_weight +
            results.get("medium_risk_secrets", 0) * medium_weight +
            results.get("low_risk_secrets", 0) * low_weight
        )
        

        if weighted_count == 0:
            return 1.0
            

        files_scanned = max(1, results.get("files_scanned", 1))
        risk_ratio = weighted_count / files_scanned
        

        score = max(0.0, 1.0 - min(1.0, risk_ratio * 5))
        

        if results.get("critical_secrets", 0) > 0:
            score = score * 0.8
            
        return score
