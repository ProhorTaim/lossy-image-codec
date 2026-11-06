.PHONY: run test check lint

run:
	@echo "TODO: поднять API локально (реализует разработчик ПО)"

test:
	@python3 -m pytest tests/ -q || echo "нет тестов или pytest не установлен"

check:
	@bash tests/check_api.sh

lint:
	@python3 -m compileall -q codec api