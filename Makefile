PYFILES=$(shell find algotrade -name "*.py")

test: $(PYFILES) .venv
	python -m pytest -slv tests/ 

darker: $(PYFILES)
	python -m darker --skip-magic-trailing-comma --skip-string-normalization --line-length 88 $(PYFILES)

precommit: autoflake isort darker clean test
	
autoflake: 
	autoflake --in-place --remove-unused-variables --remove-all-unused-imports $(PYFILES)

isort:
	isort . $(PYFILES)

clean:
	find -type d -name __pycache__ -exec rm -rf {} +
	rm -rf cov.xml .coverage dist .pytest_cache

clearlogs:
	rm logs/*