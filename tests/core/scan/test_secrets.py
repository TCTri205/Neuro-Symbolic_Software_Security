import pytest
from src.core.scan.secrets import SecretScanner


@pytest.fixture
def scanner():
    return SecretScanner()


def test_entropy_calculation(scanner):
    # Low entropy (repetitive)
    assert scanner.calculate_entropy("aaaaa") < 1.0
    # High entropy (random)
    assert scanner.calculate_entropy("7F3c9q2@#kL$v") > 3.0


def test_regex_detection_aws(scanner):
    content = "aws_key = 'AKIAIOSFODNN7EXAMPLE'"
    matches = scanner.scan(content)
    assert any(m.type == "AWS Access Key ID" for m in matches)
    assert "AKIAIOSFODNN7EXAMPLE" in [m.value for m in matches]


def test_regex_detection_private_key(scanner):
    content = """
    -----BEGIN RSA PRIVATE KEY-----
    MIIEpQIBAAKCAQEA3...
    -----END RSA PRIVATE KEY-----
    """
    matches = scanner.scan(content)
    assert any(m.type == "Private Key" for m in matches)


def test_high_entropy_string_detection(scanner):
    # A random API key looking string without specific prefix
    content = "api_secret = 'zbK7#9L1@mP2$xR5qY8n'"
    matches = scanner.scan(content)
    # This might match via entropy or generic generic keyword + entropy logic
    # For now, let's assume we have a high entropy detector
    high_entropy_matches = [m for m in matches if m.type == "High Entropy String"]
    assert len(high_entropy_matches) > 0


def test_false_positive_filtering(scanner):
    # Common words or low entropy strings shouldn't trigger
    content = "my_variable = 'hello_world'"
    matches = scanner.scan(content)
    assert len(matches) == 0
