from typing import Dict, List, Any, Optional, Tuple, Set
import os
import re
from pathlib import Path
import json
from collections import Counter


class TechnologyAnalyzer:
    def __init__(self):
        self.tech_markers = {
            "python": [r"\.py$", r"requirements\.txt$", r"setup\.py$", r"Pipfile$", r"pyproject\.toml$"],
            "javascript": [r"\.js$", r"package\.json$", r"yarn\.lock$", r"webpack\.config\.js$"],
            "typescript": [r"\.ts$", r"\.tsx$", r"tsconfig\.json$"],
            "react": [r"\.jsx$", r"\.tsx$", r"react", r"import\s+React"],
            "vue": [r"\.vue$", r"vue\.config\.js$"],
            "angular": [r"angular\.json$", r"\.component\.ts$"],
            "node": [r"package\.json$", r"node_modules", r"express",
                     r"import\s+.*\s+from\s+['\"](express|koa|hapi|nest)"],
            "java": [r"\.java$", r"pom\.xml$", r"build\.gradle$"],
            "kotlin": [r"\.kt$", r"\.kts$"],
            "swift": [r"\.swift$", r"Package\.swift$"],
            "ruby": [r"\.rb$", r"Gemfile$", r"\.gemspec$"],
            "php": [r"\.php$", r"composer\.json$"],
            "go": [r"\.go$", r"go\.mod$"],
            "rust": [r"\.rs$", r"Cargo\.toml$"],
            "c": [r"\.c$", r"\.h$"],
            "cpp": [r"\.cpp$", r"\.hpp$", r"\.cc$"],
            "csharp": [r"\.cs$", r"\.csproj$", r"\.sln$"],
            "flutter": [r"\.dart$", r"pubspec\.yaml$"],
            "django": [r"settings\.py$", r"urls\.py$", r"models\.py$", r"views\.py$", r"from\s+django"],
            "flask": [r"from\s+flask", r"Flask\("],
            "fastapi": [r"from\s+fastapi", r"FastAPI\("],
            "spring": [r"@SpringBootApplication", r"@RestController"],
            "unity": [r"\.unity$", r"\.prefab$", r"\.mat$"],
            "tensorflow": [r"import\s+tensorflow", r"from\s+tensorflow", r"tf\."],
            "pytorch": [r"import\s+torch", r"from\s+torch"],
            "docker": [r"Dockerfile", r"docker-compose\.yml$"],
            "kubernetes": [r"\.yaml$", r"\.yml$", r"apiVersion:", r"kind:", r"kubectl"],
            "html": [r"\.html$", r"\.htm$"],
            "css": [r"\.css$", r"\.scss$", r"\.sass$", r"\.less$"],
            "tailwind": [r"tailwind\.config\.js$", r"class=\".*tailwind"],
            "bootstrap": [r"bootstrap", r"class=\".*bootstrap"],
            "jquery": [r"jquery", r"\$\("],
            "graphql": [r"\.graphql$", r"\.gql$", r"apollo", r"gql`"],
            "sql": [r"\.sql$"],
            "mongodb": [r"mongodb", r"mongoose"],
            "postgresql": [r"postgres", r"psql", r"pg_"],
            "mysql": [r"mysql", r"MariaDB"],
            "redis": [r"redis"],
            "aws": [r"aws", r"amazon", r"dynamodb", r"s3"],
            "azure": [r"azure", r"microsoft cloud"],
            "gcp": [r"gcp", r"google cloud"],
            "firebase": [r"firebase", r"firestore"],
            "machinelearning": [r"sklearn", r"scikit", r"pandas", r"numpy", r"matplotlib", r"keras"]
        }

        self.file_content_analyzers = {
            ".py": self._analyze_python_file,
            ".js": self._analyze_js_file,
            ".jsx": self._analyze_js_file,
            ".ts": self._analyze_js_file,
            ".tsx": self._analyze_js_file,
            ".java": self._analyze_java_file,
            "package.json": self._analyze_package_json,
            "requirements.txt": self._analyze_requirements_txt,
            "pyproject.toml": self._analyze_pyproject_toml,
            "pom.xml": self._analyze_pom_xml,
            "build.gradle": self._analyze_gradle_file,
        }

        self.content_signatures = {
            "react": [r"import\s+React", r"from\s+['\"](react|react-dom)",
                      r"React\.(Component|createClass|useState|useEffect)"],
            "vue": [r"import\s+Vue", r"new\s+Vue\(", r"createApp\("],
            "angular": [r"@angular", r"@Component", r"NgModule"],
            "django": [r"from\s+django", r"urlpatterns", r"INSTALLED_APPS"],
            "flask": [r"from\s+flask", r"Flask\(__name__\)"],
            "express": [r"express\(\)", r"app\.get\(", r"app\.post\("],
            "redux": [r"createStore", r"useSelector", r"useDispatch", r"combineReducers"],
            "tensorflow": [r"import\s+tensorflow", r"tf\."],
            "pytorch": [r"import\s+torch", r"torch\.nn"],
            "mongodb": [r"mongoose", r"MongoClient", r"mongodb:\/\/"],
            "graphql": [r"gql`", r"ApolloClient", r"useQuery"],
        }

    def analyze_repo(self, repo_path: str) -> Dict[str, Any]:
        result = {
            "detected_technologies": [],
            "primary_languages": [],
            "frameworks": [],
            "database_technologies": [],
            "cloud_services": [],
            "devops_tools": [],
            "technology_diversity": 0.0,
            "tech_file_counts": {},
            "missing_required": [],
            "forbidden_used": [],
        }

        tech_occurrences = {}
        for tech in self.tech_markers:
            tech_occurrences[tech] = 0

        total_files = 0
        content_techs = set()

        for root, dirs, files in os.walk(repo_path):
            if ".git" in root or "node_modules" in root or "__pycache__" in root:
                continue

            for filename in files:
                if filename.startswith('.'):
                    continue

                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, repo_path)

                found_techs = set()
                for tech, patterns in self.tech_markers.items():
                    for pattern in patterns:
                        if re.search(pattern, filename, re.IGNORECASE) or re.search(pattern, rel_path, re.IGNORECASE):
                            tech_occurrences[tech] = tech_occurrences.get(tech, 0) + 1
                            found_techs.add(tech)

                file_extension = Path(filename).suffix.lower()
                if filename in self.file_content_analyzers or file_extension in self.file_content_analyzers:
                    analyzer = None
                    if filename in self.file_content_analyzers:
                        analyzer = self.file_content_analyzers[filename]
                    else:
                        analyzer = self.file_content_analyzers.get(file_extension)

                    if analyzer:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                additional_techs = analyzer(content)
                                content_techs.update(additional_techs)

                                for tech, patterns in self.content_signatures.items():
                                    for pattern in patterns:
                                        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                                            tech_occurrences[tech] = tech_occurrences.get(tech, 0) + 1
                                            found_techs.add(tech)
                        except Exception:
                            pass

                total_files += 1

        for tech in content_techs:
            tech_occurrences[tech] = tech_occurrences.get(tech, 0) + 1

        tech_file_counts = {tech: count for tech, count in tech_occurrences.items() if count > 0}
        result["tech_file_counts"] = tech_file_counts

        detected_technologies = [tech for tech, count in tech_file_counts.items() if count > 0]
        result["detected_technologies"] = detected_technologies

        language_techs = ["python", "javascript", "typescript", "java", "kotlin", "swift", "ruby", "php", "go", "rust",
                          "c", "cpp", "csharp"]
        framework_techs = ["react", "vue", "angular", "django", "flask", "fastapi", "spring", "express", "flutter",
                           "unity"]
        database_techs = ["mongodb", "postgresql", "mysql", "redis", "sqlite", "firebase"]
        cloud_techs = ["aws", "azure", "gcp", "firebase", "heroku", "netlify", "vercel"]
        devops_techs = ["docker", "kubernetes", "github", "gitlab", "jenkins", "travis", "circleci"]

        result["primary_languages"] = [tech for tech in detected_technologies if tech in language_techs]
        result["frameworks"] = [tech for tech in detected_technologies if tech in framework_techs]
        result["database_technologies"] = [tech for tech in detected_technologies if tech in database_techs]
        result["cloud_services"] = [tech for tech in detected_technologies if tech in cloud_techs]
        result["devops_tools"] = [tech for tech in detected_technologies if tech in devops_techs]

        diversity_score = min(1.0, len(detected_technologies) / 10)
        result["technology_diversity"] = diversity_score

        return result

    def check_tech_requirements(self, detected_techs: List[str], required_techs: List[str],
                                disallowed_techs: List[str]) -> Dict[str, Any]:
        result = {
            "missing_required": [],
            "forbidden_used": [],
            "compliance_score": 1.0
        }

        detected_set = set(detected_techs)
        required_set = set(required_techs)
        disallowed_set = set(disallowed_techs)

        missing = required_set - detected_set
        forbidden = detected_set.intersection(disallowed_set)

        result["missing_required"] = list(missing)
        result["forbidden_used"] = list(forbidden)

        compliance_score = 1.0
        if required_set:
            required_compliance = (len(required_set) - len(missing)) / len(required_set)
            compliance_score = compliance_score * required_compliance

        if disallowed_set and forbidden:
            forbidden_penalty = len(forbidden) / len(disallowed_set)
            compliance_score = compliance_score * (1 - forbidden_penalty)

        result["compliance_score"] = compliance_score

        return result

    def _analyze_python_file(self, content: str) -> Set[str]:
        technologies = set()

        import_patterns = [
            (r"import\s+flask", "flask"),
            (r"from\s+flask", "flask"),
            (r"import\s+django", "django"),
            (r"from\s+django", "django"),
            (r"import\s+fastapi", "fastapi"),
            (r"from\s+fastapi", "fastapi"),
            (r"import\s+numpy", "numpy"),
            (r"import\s+pandas", "pandas"),
            (r"import\s+tensorflow", "tensorflow"),
            (r"import\s+torch", "pytorch"),
            (r"import\s+sklearn", "scikit-learn"),
            (r"from\s+sklearn", "scikit-learn"),
            (r"import\s+matplotlib", "matplotlib"),
            (r"import\s+pymongo", "mongodb"),
            (r"import\s+sqlalchemy", "sqlalchemy"),
            (r"import\s+psycopg2", "postgresql"),
            (r"import\s+mysql", "mysql"),
            (r"import\s+boto3", "aws"),
            (r"import\s+firebase_admin", "firebase"),
            (r"import\s+keras", "keras"),
        ]

        for pattern, tech in import_patterns:
            if re.search(pattern, content, re.MULTILINE):
                technologies.add(tech)

        return technologies

    def _analyze_js_file(self, content: str) -> Set[str]:
        technologies = set()

        import_patterns = [
            (r"import\s+.*\s+from\s+['\"]react", "react"),
            (r"import\s+.*\s+from\s+['\"]vue", "vue"),
            (r"import\s+.*\s+from\s+['\"]@angular", "angular"),
            (r"import\s+.*\s+from\s+['\"]express", "express"),
            (r"import\s+.*\s+from\s+['\"]mongoose", "mongodb"),
            (r"import\s+.*\s+from\s+['\"]sequelize", "sql"),
            (r"import\s+.*\s+from\s+['\"]pg\b", "postgresql"),
            (r"import\s+.*\s+from\s+['\"]mysql", "mysql"),
            (r"import\s+.*\s+from\s+['\"]firebase", "firebase"),
            (r"import\s+.*\s+from\s+['\"]@aws-sdk", "aws"),
            (r"import\s+.*\s+from\s+['\"]@azure", "azure"),
            (r"import\s+.*\s+from\s+['\"]@google-cloud", "gcp"),
            (r"import\s+.*\s+from\s+['\"]redux", "redux"),
            (r"import\s+.*\s+from\s+['\"]@apollo/client", "graphql"),
            (r"import\s+.*\s+from\s+['\"]axios", "axios"),
        ]

        for pattern, tech in import_patterns:
            if re.search(pattern, content, re.MULTILINE):
                technologies.add(tech)

        return technologies

    def _analyze_java_file(self, content: str) -> Set[str]:
        technologies = set()

        import_patterns = [
            (r"import\s+org\.springframework", "spring"),
            (r"import\s+javax\.persistence", "jpa"),
            (r"import\s+java\.sql", "jdbc"),
            (r"import\s+com\.fasterxml\.jackson", "jackson"),
            (r"import\s+org\.hibernate", "hibernate"),
            (r"import\s+com\.google\.firebase", "firebase"),
            (r"import\s+com\.amazonaws", "aws"),
            (r"import\s+com\.azure", "azure"),
            (r"import\s+com\.google\.cloud", "gcp"),
            (r"import\s+io\.reactivex", "rxjava"),
            (r"import\s+reactor\.core", "reactor"),
            (r"import\s+org\.mongodb", "mongodb"),
        ]

        for pattern, tech in import_patterns:
            if re.search(pattern, content, re.MULTILINE):
                technologies.add(tech)

        return technologies

    def _analyze_package_json(self, content: str) -> Set[str]:
        technologies = set()

        try:
            package_data = json.loads(content)

            dependencies = {}
            dependencies.update(package_data.get("dependencies", {}))
            dependencies.update(package_data.get("devDependencies", {}))

            dependency_map = {
                "react": "react",
                "react-dom": "react",
                "vue": "vue",
                "@vue/cli": "vue",
                "@angular/core": "angular",
                "express": "express",
                "koa": "koa",
                "next": "nextjs",
                "nuxt": "nuxtjs",
                "mongoose": "mongodb",
                "sequelize": "sql",
                "pg": "postgresql",
                "mysql": "mysql",
                "sqlite3": "sqlite",
                "redis": "redis",
                "firebase": "firebase",
                "aws-sdk": "aws",
                "@azure/core": "azure",
                "@google-cloud/storage": "gcp",
                "redux": "redux",
                "apollo-client": "graphql",
                "@apollo/client": "graphql",
                "graphql": "graphql",
                "tailwindcss": "tailwind",
                "bootstrap": "bootstrap",
                "jquery": "jquery",
                "webpack": "webpack",
                "jest": "jest",
                "mocha": "mocha",
                "cypress": "cypress",
                "electron": "electron",
                "typescript": "typescript"
            }

            for dep in dependencies:
                for known_dep, tech in dependency_map.items():
                    if dep == known_dep or dep.startswith(f"{known_dep}/"):
                        technologies.add(tech)
        except Exception:
            pass

        return technologies

    def _analyze_requirements_txt(self, content: str) -> Set[str]:
        technologies = set()

        dependency_map = {
            "flask": "flask",
            "django": "django",
            "fastapi": "fastapi",
            "numpy": "numpy",
            "pandas": "pandas",
            "tensorflow": "tensorflow",
            "torch": "pytorch",
            "scikit-learn": "scikit-learn",
            "matplotlib": "matplotlib",
            "pymongo": "mongodb",
            "sqlalchemy": "sqlalchemy",
            "psycopg2": "postgresql",
            "mysqlclient": "mysql",
            "boto3": "aws",
            "firebase-admin": "firebase",
            "google-cloud": "gcp",
            "azure-": "azure",
            "pytest": "pytest",
            "jupyter": "jupyter",
        }

        for line in content.split('\n'):
            line = line.strip().lower()
            if not line or line.startswith('#'):
                continue

            package = line.split('==')[0].split('>=')[0].split('<=')[0].strip()

            for known_dep, tech in dependency_map.items():
                if package == known_dep or package.startswith(f"{known_dep}-"):
                    technologies.add(tech)

        return technologies

    def _analyze_pyproject_toml(self, content: str) -> Set[str]:
        technologies = set()

        dependency_patterns = [
            (r"flask\s*=", "flask"),
            (r"django\s*=", "django"),
            (r"fastapi\s*=", "fastapi"),
            (r"numpy\s*=", "numpy"),
            (r"pandas\s*=", "pandas"),
            (r"tensorflow\s*=", "tensorflow"),
            (r"torch\s*=", "pytorch"),
            (r"scikit-learn\s*=", "scikit-learn"),
            (r"matplotlib\s*=", "matplotlib"),
            (r"pymongo\s*=", "mongodb"),
            (r"sqlalchemy\s*=", "sqlalchemy"),
            (r"psycopg2\s*=", "postgresql"),
            (r"mysqlclient\s*=", "mysql"),
            (r"boto3\s*=", "aws"),
            (r"firebase-admin\s*=", "firebase"),
            (r"google-cloud\s*=", "gcp"),
            (r"azure-\w+\s*=", "azure"),
        ]

        for pattern, tech in dependency_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                technologies.add(tech)

        return technologies

    def _analyze_pom_xml(self, content: str) -> Set[str]:
        technologies = set()

        dependency_patterns = [
            (r"<artifactId>spring-boot</artifactId>", "spring"),
            (r"<artifactId>spring-webmvc</artifactId>", "spring"),
            (r"<artifactId>hibernate-core</artifactId>", "hibernate"),
            (r"<artifactId>mysql-connector-java</artifactId>", "mysql"),
            (r"<artifactId>postgresql</artifactId>", "postgresql"),
            (r"<artifactId>mongodb-driver</artifactId>", "mongodb"),
            (r"<artifactId>aws-java-sdk</artifactId>", "aws"),
            (r"<artifactId>azure-sdk</artifactId>", "azure"),
            (r"<artifactId>google-cloud</artifactId>", "gcp"),
            (r"<artifactId>firebase-admin</artifactId>", "firebase"),
        ]

        for pattern, tech in dependency_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                technologies.add(tech)

        return technologies

    def _analyze_gradle_file(self, content: str) -> Set[str]:
        technologies = set()

        dependency_patterns = [
            (r"org\.springframework\.boot", "spring"),
            (r"org\.hibernate", "hibernate"),
            (r"mysql-connector-java", "mysql"),
            (r"org\.postgresql", "postgresql"),
            (r"org\.mongodb", "mongodb"),
            (r"com\.amazonaws", "aws"),
            (r"com\.azure", "azure"),
            (r"com\.google\.cloud", "gcp"),
            (r"com\.google\.firebase", "firebase"),
        ]

        for pattern, tech in dependency_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                technologies.add(tech)

        return technologies