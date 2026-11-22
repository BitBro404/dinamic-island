.PHONY: check check-x11 doctor

check:
	python3 -m compileall -q isla_dinamica tools
	python3 -W error::ResourceWarning -m unittest discover -s tests/unit

check-x11:
	bash tests/x11_smoke.sh

doctor:
	python3 -m isla_dinamica --doctor
