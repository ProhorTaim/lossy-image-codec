.PHONY: run test check lint

run:
	@echo "TODO: поднять API локально (реализует разработчик ПО)"

test:
	@python3 -c "import pytest" 2>/dev/null && \
		python3 -m pytest tests/ -q || \
		(echo "pytest не установлен — поставь его в venv и повтори"; exit 1)

check:
	@bash tests/check_api.sh

lint:
	@python3 -m compileall -q codec api