import os
from src.core.context.loader import ContextLoader


def test_load_pythonpath_from_env(tmp_path):
    env_file = tmp_path / ".env"
    # Testing with multiple paths using os.pathsep for cross-platform compatibility
    env_file.write_text(f"PYTHONPATH=./lib{os.pathsep}./src")

    loader = ContextLoader(root_dir=str(tmp_path))
    context = loader.load()

    assert context.python_paths is not None
    # Expecting absolute paths resolution
    expected_lib = str(tmp_path / "lib")
    expected_src = str(tmp_path / "src")

    # We need to handle potential path separator differences or normalization
    resolved_paths = [os.path.normpath(p) for p in context.python_paths]

    assert os.path.normpath(expected_lib) in resolved_paths
    assert os.path.normpath(expected_src) in resolved_paths


def test_load_pythonpath_from_settings(tmp_path):
    settings_file = tmp_path / "settings.py"
    settings_file.write_text("PYTHONPATH = ['./custom_lib']")

    loader = ContextLoader(root_dir=str(tmp_path))
    context = loader.load()

    expected_custom = str(tmp_path / "custom_lib")
    resolved_paths = [os.path.normpath(p) for p in context.python_paths]

    assert os.path.normpath(expected_custom) in resolved_paths
