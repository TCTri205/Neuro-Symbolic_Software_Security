from src.core.context.loader import ContextLoader


def test_load_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=12345\nDEBUG=True")

    loader = ContextLoader(root_dir=str(tmp_path))
    context = loader.load()

    assert context.env_vars["SECRET_KEY"] == "12345"
    assert context.env_vars["DEBUG"] == "True"


def test_load_settings_py(tmp_path):
    settings_file = tmp_path / "settings.py"
    settings_file.write_text("ALLOWED_HOSTS = ['*']\nDATABASES = {'default': {}}")

    loader = ContextLoader(root_dir=str(tmp_path))
    context = loader.load()

    assert "ALLOWED_HOSTS" in context.settings
    assert context.settings["ALLOWED_HOSTS"] == ["*"]


def test_load_dockerfile(tmp_path):
    docker_file = tmp_path / "Dockerfile"
    docker_file.write_text("FROM python:3.10\nRUN pip install -r requirements.txt")

    loader = ContextLoader(root_dir=str(tmp_path))
    context = loader.load()

    assert context.docker is not None
    assert "FROM python:3.10" in context.docker


def test_load_pyproject(tmp_path):
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text('[tool.poetry]\nname = "nsss"')

    loader = ContextLoader(root_dir=str(tmp_path))
    context = loader.load()

    assert context.pyproject["tool"]["poetry"]["name"] == "nsss"
