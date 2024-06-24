# PyPI Bulk Release Version Cleanup Utility

[![PyPI Cleanup Version](https://img.shields.io/pypi/v/pypi-cleanup?logo=pypi)](https://pypi.org/project/pypi-cleanup/)
[![PyPI Cleanup Python Versions](https://img.shields.io/pypi/pyversions/pypi-cleanup?logo=pypi)](https://pypi.org/project/pypi-cleanup/)
[![Build Status](https://img.shields.io/github/actions/workflow/status/arcivanov/pypi-cleanup/pypi-cleanup.yml?branch=master)](https://github.com/arcivanov/pypi-cleanup/actions/workflows/pypi-cleanup.yml)
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

### Examples:

```bash
$ pypi-cleanup --help
usage: pypi-cleanup [-h] [-u USERNAME] -p PACKAGE [-t URL] [-r PATTERNS | --leave-most-recent-only] [--query-only] [--do-it] [-y] [-d DAYS] [-v]

PyPi Package Cleanup Utility v0.1.7.dev20240624230606

options:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        authentication username (default: None)
  -p PACKAGE, --package PACKAGE
                        PyPI package name (default: None)
  -t URL, --host URL    PyPI <proto>://<host> prefix (default: https://pypi.org/)
  -r PATTERNS, --version-regex PATTERNS
                        regex to use to match package versions to be deleted (default: None)
  --leave-most-recent-only
                        delete all releases except the *most recent* one, i.e. the one containing the most recently created files (default: False)
  --query-only          only queries and processes the package, no login required (default: False)
  --do-it               actually perform the destructive delete (default: False)
  -y, --yes             confirm extremely dangerous destructive delete (default: False)
  -d DAYS, --days DAYS  only delete releases **matching specified patterns** where all files are older than X days (default: 0)
  -v, --verbose         be verbose (default: 0)
```

#### Regular Cleanup of Development Artifacts
```bash
$ pypi-cleanup -u arcivanov -p pybuilder
Password: 
Authentication code: 123456
INFO:root:Deleting pybuilder version 0.12.3.dev20200421010849
INFO:root:Deleted pybuilder version 0.12.3.dev20200421010849
INFO:root:Deleting pybuilder version 0.12.3.dev20200421010857
INFO:root:Deleted pybuilder version 0.12.3.dev20200421010857
```

#### Using Custom Regex Pattern
```bash
$ pypi-cleanup -u arcivanov -p geventmp -r '.*\\.dev1$' 
WARNING:root:
WARNING:
        You're using custom patterns: [re.compile('.*\\\\.dev1$')].
        If you make a mistake in your patterns you can potentially wipe critical versions irrecoverably.
        Make sure to test your patterns before running the destructive cleanup.
        Once you're satisfied the patterns are correct re-run with `-y`/`--yes` to confirm you know what you're doing.
        Goodbye.
$ pypi-cleanup -u arcivanov -p geventmp -r '.*\\.dev1$' -y
Password:
WARNING:root:RUNNING IN DRY-RUN MODE
INFO:root:Will use the following patterns [re.compile('.*\\.dev1$')] on package geventmp
Authentication code: 123456
INFO:root:Deleting geventmp version 0.0.1.dev1
```

#### Deleting All Versions Except The Most Recent One

```bash
$ pypi-cleanup -p pypi-cleanup --leave-most-recent-only
WARNING:root:
WARNING:
        You're trying to delete ALL versions of the package EXCEPT for the *most recent one*, i.e.
        the one with the most recent (by the wall clock) files, disregarding the actual version numbers 
        or versioning schemes!

        You can potentially wipe critical versions irrecoverably.
        Make sure this is what you really want before running the destructive cleanup.
        Once you're sure you want to delete all versions except the most recent one,
        re-run with `-y`/`--yes` to confirm you know what you're doing.
        Goodbye.
$ pypi-cleanup -p pypi-cleanup --leave-most-recent-only -y --query-only
INFO:root:Running in DRY RUN mode
INFO:root:Will only leave the MOST RECENT version of the package 'pypi-cleanup'
INFO:root:Leaving the MOST RECENT package version: 0.1.7.dev20240624221535 - 2024-06-24T22:15:52.778775+0000
INFO:root:Found the following releases to delete:
INFO:root: 0.0.1
INFO:root: 0.0.2
INFO:root: 0.0.3
INFO:root: 0.1.0
INFO:root: 0.1.1
INFO:root: 0.1.2
INFO:root: 0.1.3
INFO:root: 0.1.4
INFO:root: 0.1.5
INFO:root: 0.1.6
INFO:root:Query-only mode - exiting
```
