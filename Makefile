# PLAIN Stage-1 prototype — zero dependencies (Python 3.11+ stdlib only).
PY ?= python3

.PHONY: test check fmt-check validate hello counter todo a11y clean
test:
	PYTHONPATH=src $(PY) -m unittest discover -s tests -v

check:
	./plain check examples/*.plain

fmt-check:
	./plain fmt --check examples/*.plain

validate:
	./plain validate

hello:
	./plain render examples/00-hello-world.plain --out out/hello.svg

counter:
	./plain run examples/01-counter.plain --port 8000

todo:
	./plain render examples/02-todo.plain --out out/todo.svg

a11y:
	./plain a11y examples/01-counter.plain

clean:
	rm -rf out src/plainlang/__pycache__ tests/__pycache__
