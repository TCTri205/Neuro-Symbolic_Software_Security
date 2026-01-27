import re
import math
from dataclasses import dataclass
from typing import List, Dict, Pattern


@dataclass
class SecretMatch:
    type: str
    value: str
    line: int
    confidence: float


class SecretScanner:
    """
    Scans content for hardcoded secrets using Regex patterns and Shannon Entropy.
    """

    def __init__(self):
        self.patterns: Dict[str, Pattern] = {
            "AWS Access Key ID": re.compile(
                r"(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"
            ),
            "Private Key": re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
            "Google API Key": re.compile(r"AIza[0-9A-Za-z\\-_]{35}"),
            "Slack Token": re.compile(r"xox[baprs]-([0-9a-zA-Z]{10,48})?"),
            "GitHub Token": re.compile(r"ghp_[a-zA-Z0-9]{36}"),
            "Stripe Secret Key": re.compile(r"sk_live_[0-9a-zA-Z]{24}"),
        }

        # Threshold for high entropy (experimentally determined, usually > 3.0 for alphanumeric secrets)
        self.entropy_threshold = 3.5

        # Keywords that suggest a secret assignment
        self.suspicious_keywords = re.compile(
            r"(api_key|api_secret|auth_token|access_token|secret|password|passwd|pwd|token)[\s]*=[\s]*['\"]([^'\"]+)['\"]",
            re.IGNORECASE,
        )

    def calculate_entropy(self, data: str) -> float:
        """
        Calculates the Shannon entropy of a string.
        """
        if not data:
            return 0.0

        entropy = 0.0
        length = len(data)

        # Count occurrences of each character
        char_counts = {}
        for char in data:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Calculate entropy
        for count in char_counts.values():
            p = count / length
            entropy -= p * math.log2(p)

        return entropy

    def scan(self, content: str) -> List[SecretMatch]:
        """
        Scans the provided content for secrets.
        """
        matches = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1

            # 1. Check Specific Regex Patterns
            for name, pattern in self.patterns.items():
                found = pattern.search(line)
                if found:
                    matches.append(
                        SecretMatch(
                            type=name,
                            value=found.group(),
                            line=line_num,
                            confidence=1.0,
                        )
                    )

            # 2. Check Suspicious Assignments + Entropy
            # Look for patterns like "secret = '...'"
            suspicious = self.suspicious_keywords.search(line)
            if suspicious:
                candidate_value = suspicious.group(2)
                entropy = self.calculate_entropy(candidate_value)

                # Filter out obvious false positives (short strings, low entropy)
                if len(candidate_value) > 8 and entropy > self.entropy_threshold:
                    matches.append(
                        SecretMatch(
                            type="High Entropy String",
                            value=candidate_value,
                            line=line_num,
                            confidence=0.8,  # Slightly lower confidence than exact regex
                        )
                    )

        return matches
