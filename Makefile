.PHONY: test check

test:
	python -m unittest discover --start-directory tests --pattern 'test_*.py' --verbose

check: test
