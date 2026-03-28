.venv:
	uv venv .venv

install: .venv
	uv pip install -e ".[dev]"

test:
	uv run python3 -m unittest discover -v

build:
	uv build

clean:
	rm -rf dist/ .venv/ *.egg-info
