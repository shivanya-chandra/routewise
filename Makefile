.PHONY: install test start smoke compose-config

install:
	python -m pip install -r requirements.txt

test:
	python -m pytest -q

start:
	./scripts/dev_start.sh

smoke:
	./scripts/smoke_test.sh

compose-config:
	docker compose config --quiet
