# HTTP CLI Protocol — developer tasks
# Requires Python 3.8+. No third-party dependencies.

PY ?= python3
PORT ?= 8080
BASE ?= http://127.0.0.1:$(PORT)/cli
TOKEN ?= demo-token

.PHONY: help serve selftest conformance unit lint clean

help:
	@echo "Targets:"
	@echo "  serve         start the demo tree at $(BASE) (token: $(TOKEN))"
	@echo "  unit          run engine unit tests"
	@echo "  conformance   run the black-box suite against BASE (TOKEN=...)"
	@echo "  selftest      unit tests + in-process conformance run (no server needed)"
	@echo "  lint          syntax-check all Python sources"
	@echo "  clean         remove caches"

serve:
	$(PY) reference/server.py --port $(PORT)

unit:
	$(PY) tests/test_engine.py

conformance:
	$(PY) conformance/run.py --base $(BASE) --token $(TOKEN)

selftest: unit lint
	@echo "== in-process conformance =="
	$(PY) tests/selftest.py

lint:
	$(PY) -m py_compile reference/httpcli.py reference/app.py reference/server.py \
		conformance/run.py tests/test_engine.py tests/selftest.py
	@echo "lint OK"

clean:
	find . -name __pycache__ -type d -exec rm -rf {} +
