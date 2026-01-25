.PHONY: venv install lint format test scan-fast scan-full clean

VENV_DIR ?= venv
PYTHON ?= python
PIP ?= $(PYTHON) -m pip

venv:
	$(PYTHON) -m venv $(VENV_DIR)

install:
	$(PIP) install -r requirements.txt

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

test:
	$(PYTHON) -m pytest

scan-fast:
	$(PYTHON) -m src.runner scan . --mode ci

scan-full:
	$(PYTHON) -m src.runner scan . --mode audit

clean:
	$(PYTHON) -m ruff clean
	$(PYTHON) -m pytest --cache-clear
