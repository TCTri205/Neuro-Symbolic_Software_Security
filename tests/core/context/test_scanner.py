from src.core.context.loader import ProjectContext
from src.core.context.scanner import ConfigScanner, Severity


def test_scan_debug_mode_enabled():
    context = ProjectContext(settings={"DEBUG": True}, env_vars={"DEBUG": "True"})
    scanner = ConfigScanner()
    issues = scanner.scan(context)

    debug_issues = [i for i in issues if i.key == "DEBUG"]
    assert len(debug_issues) > 0
    assert debug_issues[0].severity == Severity.HIGH
    assert "DEBUG mode is enabled" in debug_issues[0].message


def test_scan_insecure_secret_key():
    context = ProjectContext(settings={"SECRET_KEY": "123456"}, env_vars={})
    scanner = ConfigScanner()
    issues = scanner.scan(context)

    secret_issues = [i for i in issues if i.key == "SECRET_KEY"]
    assert len(secret_issues) > 0
    assert secret_issues[0].severity == Severity.CRITICAL
    assert "Weak SECRET_KEY" in secret_issues[0].message


def test_scan_cors_allow_all():
    context = ProjectContext(settings={"CORS_ALLOW_ALL_ORIGINS": True}, env_vars={})
    scanner = ConfigScanner()
    issues = scanner.scan(context)

    cors_issues = [i for i in issues if i.key == "CORS"]
    assert len(cors_issues) > 0
    assert cors_issues[0].severity == Severity.HIGH


def test_scan_safe_config():
    context = ProjectContext(
        settings={
            "DEBUG": False,
            "SECRET_KEY": "super-secret-long-random-string-must-be-32-chars",
            "CORS_ALLOW_ALL_ORIGINS": False,
        },
        env_vars={},
    )
    scanner = ConfigScanner()
    issues = scanner.scan(context)
    assert len(issues) == 0
