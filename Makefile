PHONY: lint run

venv:
	python -m venv .venv

setup-dev:
	pip install -r requirements.dev.txt

setup:
	pip install -r requirements.txt

lint:
	ruff format main.py
	ruff check --fix main.py
	mypy --strict main.py

run:
	python main.py
