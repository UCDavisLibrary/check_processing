.PHONY: cover
cover:
	coverage run --omit "test/*" -m unittest discover -s test -v
	coverage html
	coverage report

.PHONY: test
test:
	python2.7 -m unittest discover -s test

.PHONY: pep8
pep8:
	pep8 --show-source --show-pep8 *.py

.PHONY: lint
lint:
	 pylint --rcfile=.pylintrc *.py
