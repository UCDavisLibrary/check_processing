PREFIX = /usr/local/alma/dafis
CWD = $(shell pwd)

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

.PHONY: install
install : $(PREFIX)/update_alma.py $(PREFIX)/xml_to_apfeed.py $(PREFIX)/read_apfeed.py

$(PREFIX)/xml_to_apfeed.py: $(CWD)/xml_to_apfeed.py
	cp $(CWD)/xml_to_apfeed.py $(PREFIX)/xml_to_apfeed.py

$(PREFIX)/update_alma.py: $(CWD)/update_alma.py
	cp $(CWD)/update_alma.py $(PREFIX)/update_alma.py

$(PREFIX)/read_apfeed.py: $(CWD)/read_apfeed.py
	cp $(CWD)/read_apfeed.py $(PREFIX)/read_apfeed.py
