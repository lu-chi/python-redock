# Makefile for Redock.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: September 26, 2013
# URL: https://github.com/xolox/python-redock

default:
	@echo 'Makefile for the redock program'
	@echo
	@echo 'Usage:'
	@echo
	@echo '    make test       run the unit test suite'
	@echo '    make docs       update documentation using Sphinx'
	@echo '    make publish    publish changes to GitHub/PyPI'
	@echo '    make clean      cleanup all temporary files'
	@echo

test:
	python setup.py test

clean:
	rm -Rf .tox build dist docs/build *.egg *.egg-info

reset: clean
	rm -Rf $(WORKON_HOME)/redock
	virtualenv $(WORKON_HOME)/redock
	$(WORKON_HOME)/redock/bin/pip install pip-accel
	$(WORKON_HOME)/redock/bin/pip-accel install -r requirements.txt
	$(WORKON_HOME)/redock/bin/pip install .

docs:
	cd docs && make html

publish:
	git push origin && git push --tags origin
	make clean && python setup.py sdist upload

.PHONY: docs
