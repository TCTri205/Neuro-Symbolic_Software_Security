from click.testing import CliRunner
from src.runner.cli.main import cli


def test_scan_command_basic():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("test_file.py", "w") as f:
            f.write("print('hello')")

        result = runner.invoke(cli, ["scan", "test_file.py"])
        assert result.exit_code == 0
        assert "Initializing NSSS Scan..." in result.output
        assert "Target: test_file.py" in result.output
        assert "Mode: audit" in result.output  # Default


def test_scan_command_options():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("test_file.py", "w") as f:
            f.write("print('hello')")

        result = runner.invoke(
            cli,
            [
                "scan",
                "test_file.py",
                "--mode",
                "ci",
                "--format",
                "json",
                "--emit-ir",
            ],
        )
        assert result.exit_code == 0
        assert "Mode: ci" in result.output
        assert "Format: json" in result.output
        assert '"ir"' in result.output


def test_scan_invalid_path():
    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "non_existent_file.py"])
    assert result.exit_code != 0
    assert "Path 'non_existent_file.py' does not exist" in result.output
