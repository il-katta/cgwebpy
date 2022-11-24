
PYTHON?=python3
VERSION=1.0.6
PKG_VER=1

build:
	$(PYTHON) setup.py build
.PHONY: build

install: build
	$(PYTHON) setup.py install
	install -m 655 service/cgwebpy.service /etc/systemd/system/
.PHONY: install

../cgwebpy_$(VERSION)-$(PKG_VER)_amd64.deb:
	dpkg-buildpackage -b -rfakeroot -us -uc

debian-build: ../cgwebpy_$(VERSION)-$(PKG_VER)_amd64.deb

debian-install: debian-build
	dpkg -i ../cgwebpy_$(VERSION)-$(PKG_VER)_amd64.deb
.PHONY: debian-install

clean:
	$(PYTHON) setup.py clean
	rm -rf build cgwebpy.egg-info .pybuild
	rm -rf dist
	rm -f ../cgwebpy_*.changes ../cgwebpy_*.buildinfo ../cgwebpy_*.deb
	rm -rf debian/cgwebpy
.PHONY: clean

uninstall:
	rm -f /etc/systemd/system/cgwebpy.service
	$(PYTHON) -m pip uninstall cgwebpy

.PHONY: uninstall