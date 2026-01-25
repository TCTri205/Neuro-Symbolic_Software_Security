import re
from typing import List, Dict, Set, Optional

# Top 50 downloaded PyPI packages + common frameworks (Representative list)
POPULAR_PACKAGES = {
    "boto3", "botocore", "urllib3", "requests", "six", "python-dateutil", "setuptools",
    "certifi", "pip", "wheel", "idna", "s3transfer", "typing-extensions", "charset-normalizer",
    "rsa", "awscli", "pyyaml", "numpy", "pandas", "jmespath", "colorama", "packaging",
    "zipp", "google-api-core", "fsspec", "click", "importlib-metadata", "markupsafe",
    "pyasn1", "jinja2", "protobuf", "pytz", "tomli", "attrs", "platformdirs", "more-itertools",
    "flask", "django", "fastapi", "pytest", "scikit-learn", "scipy", "tensorflow", "torch",
    "pydantic", "sqlalchemy", "aiohttp", "pillow", "matplotlib", "beautifulsoup4"
}

class TyposquatScanner:
    def __init__(self, popular_packages: Optional[Set[str]] = None, threshold: int = 2):
        self.popular_packages = popular_packages or POPULAR_PACKAGES
        self.threshold = threshold

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]

    def check_package(self, package_name: str) -> List[str]:
        """
        Checks if a package name is a potential typosquat of a popular package.
        Returns a list of popular packages it might be impersonating.
        """
        package_name = package_name.lower()
        if package_name in self.popular_packages:
            return []
        
        matches = []
        for popular in self.popular_packages:
            # Skip if length difference is too big
            if abs(len(package_name) - len(popular)) > self.threshold:
                continue
                
            dist = self._levenshtein_distance(package_name, popular)
            if dist > 0 and dist <= self.threshold:
                matches.append(popular)
        
        return matches

    def parse_requirements_file(self, content: str) -> List[str]:
        """
        Parses requirements.txt content and extracts package names.
        Handles:
        - package==1.0.0
        - package>=1.0
        - package
        - Comments (#)
        """
        packages = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Simple regex to capture package name before specifiers
            # Specifiers usually start with ==, >=, <=, >, <, ~=, !=, ;
            match = re.match(r'^([a-zA-Z0-9_\-\.]+)', line)
            if match:
                packages.append(match.group(1).lower())
        return packages

    def scan(self, file_content: str) -> List[Dict[str, any]]:
        packages = self.parse_requirements_file(file_content)
        results = []
        
        for pkg in packages:
            squatted = self.check_package(pkg)
            if squatted:
                results.append({
                    "package": pkg,
                    "candidates": squatted,
                    "risk": "HIGH",
                    "reason": f"Potential typosquatting of {', '.join(squatted)}"
                })
        
        return results
