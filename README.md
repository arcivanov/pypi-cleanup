# PyPI Bulk Release Version Cleanup Utility

[![PyPI Cleanup Version](https://img.shields.io/pypi/v/pypi-cleanup?logo=pypi)](https://pypi.org/project/pypi-cleanup/)
[![PyPI Cleanup Python Versions](https://img.shields.io/pypi/pyversions/pypi-cleanup?logo=pypi)](https://pypi.org/project/pypi-cleanup/)
[![Build Status](https://img.shields.io/github/workflow/status/arcivanov/pypi-cleanup/pypi-cleanup/master)](https://github.com/arcivanov/pypi-cleanup/actions/workflows/pypi-cleanup.yml)
[![PyPI Cleanup Downloads Per Day](https://img.shields.io/pypi/dd/pypi-cleanup?logo=pypi)](https://pypi.org/project/pypi-cleanup/)
[![PyPI Cleanup Downloads Per Week](https://img.shields.io/pypi/dw/pypi-cleanup?logo=pypi)](https://pypi.org/project/pypi-cleanup/)
[![PyPI Cleanup Downloads Per Month](https://img.shields.io/pypi/dm/pypi-cleanup?logo=pypi)](https://pypi.org/project/pypi-cleanup/)

## Overview

PyPI Bulk Release Version Cleanup Utility (`pypi-cleanup`) is designed to bulk-delete releases from PyPI that match
specified patterns.
This utility is most useful when CI/CD method produces a swarm of temporary
[.devN pre-releases](https://www.python.org/dev/peps/pep-0440/#developmental-releases) in between versioned releases.

Being able to cleanup past .devN junk helps PyPI cut down on the storage requirements and keeps release history neatly
organized.

## WARNING

THIS UTILITY IS DESTRUCTIVE AND CAN POTENTIALLY WRECK YOUR PROJECT RELEASES AND MAKE THE PROJECT INACCESSIBLE ON PYPI.

This utility is provided on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied, including, without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY,
or FITNESS FOR A PARTICULAR PURPOSE.

## Details

The default package release version selection pattern is `r".*dev\d+$"`.

Authentication password may be passed via environment variable
`PYPI_CLEANUP_PASSWORD`. Otherwise, you will be prompted to enter it.

Authentication with TOTP is supported.

Examples:

```bash
$ pypi-cleanup --help
usage: pypi-cleanup [-h] -u USERNAME -p PACKAGE [-t URL] [-r PATTERNS] [--do-it] [-y] [-v]

PyPi Package Cleanup Utility

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        authentication username (default: None)
  -p PACKAGE, --package PACKAGE
                        PyPI package name (default: None)
  -t URL, --host URL    PyPI <proto>://<host> prefix (default: https://pypi.org/)
  -r PATTERNS, --version-regex PATTERNS
                        regex to use to match package versions to be deleted (default: None)
  --do-it               actually perform the destructive delete (default: False)
  -y, --yes             confirm extremely dangerous destructive delete (default: False)
  -v, --verbose         be verbose (default: 0)
```

```bash
$ pypi-cleanup -u arcivanov -p pybuilder
Password: 
Authentication code: 123456
INFO:root:Deleting pybuilder version 0.12.3.dev20200421010849
INFO:root:Deleted pybuilder version 0.12.3.dev20200421010849
INFO:root:Deleting pybuilder version 0.12.3.dev20200421010857
INFO:root:Deleted pybuilder version 0.12.3.dev20200421010857
```

```bash
$ pypi-cleanup -u arcivanov -p geventmp -n -r '.*\\.dev1$'
Password:
WARNING:root:RUNNING IN DRY-RUN MODE
INFO:root:Will use the following patterns [re.compile('.*\\.dev1$')] on package geventmp
Authentication code: 123456
INFO:root:Deleting geventmp version 0.0.1.dev1
```
