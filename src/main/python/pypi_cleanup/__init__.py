#   -*- coding: utf-8 -*-
#   Copyright (C) 2020 Arcadiy Ivanov <arcadiy@ivanov.biz>
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

import argparse
import getpass
import logging
import re
import sys
from html.parser import HTMLParser
from textwrap import dedent
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException

DEFAULT_PATTERNS = [re.compile(r".*\.dev\d+$")]


class CsfrParser(HTMLParser):
    def __init__(self, target, contains_input=None):
        super().__init__()
        self._target = target
        self._contains_input = contains_input
        self.csrf = None  # Result value from all forms on page
        self._csrf = None  # Temp value from current form
        self._in_form = False  # Currently parsing a form with an action we're interested in
        self._input_contained = False  # Input field requested is contained in the current form

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            attrs = dict(attrs)
            if attrs["action"] == self._target or attrs["action"].startswith(self._target):
                self._in_form = True
            return

        if self._in_form and tag == "input":
            attrs = dict(attrs)
            if attrs.get("name") == "csrf_token":
                self._csrf = attrs["value"]

            if self._contains_input and attrs.get("name") == self._contains_input:
                self._input_contained = True

            return

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_form = False
            # If we're in a right form that contains the requested input and csrf is not set
            if (not self._contains_input or self._input_contained) and not self.csrf:
                self.csrf = self._csrf
            return


class PypiCleanup:
    def __init__(self, url, username, package, dry_run, patterns, verbose, **_):
        self.url = urlparse(url).geturl()
        if self.url[-1] == "/":
            self.url = self.url[:-1]
        self.username = username
        self.dry_run = dry_run
        self.package = package
        self.patterns = patterns or DEFAULT_PATTERNS
        self.verbose = verbose

    def run(self):
        csrf = None

        if self.verbose:
            logging.root.setLevel(logging.DEBUG)

        if self.dry_run:
            logging.warning("RUNNING IN DRY-RUN MODE")

        logging.info(f"Will use the following patterns {self.patterns} on package {self.package}")

        with requests.Session() as s:
            with s.get(f"{self.url}/pypi/{self.package}/json") as r:
                try:
                    r.raise_for_status()
                except RequestException as e:
                    logging.error(f"Unable to find package {repr(self.package)}", exc_info=e)
                    return 1

                keys = list(r.json()["releases"].keys())

            if not keys:
                logging.info(f"No releases for package {self.package} have been found")
                return

            pkg_vers = list(filter(lambda k:
                                   any(filter(lambda rex: rex.match(k),
                                              self.patterns)),
                                   keys))

            if not pkg_vers:
                logging.info(f"No packages were found matching specified patterns in package {self.package}")
                return

            if set(pkg_vers) == set(keys):
                print(dedent(f"""
                WARNING:
                \tYour have selected the following patterns: {self.patterns}
                \tThese patterns would delete all available released versions of `{self.package}`.
                \tThis will render your project/package permanently inaccessible.
                \tSince the costs of an error are too high I'm refusing to do this.
                \tGoodbye.
                """), file=sys.stderr)

                if not self.dry_run:
                    return 3

            password = getpass.getpass("Password: ")

            with s.get(f"{self.url}/account/login/") as r:
                r.raise_for_status()
                form_action = "/account/login/"
                parser = CsfrParser(form_action)
                parser.feed(r.text)
                if not parser.csrf:
                    raise ValueError(f"No CSFR found in {form_action}")
                csrf = parser.csrf

            two_factor = False
            with s.post(f"{self.url}/account/login/",
                        data={"csrf_token": csrf,
                              "username": self.username,
                              "password": password},
                        headers={"referer": f"{self.url}/account/login/"}) as r:
                r.raise_for_status()
                if r.url == f"{self.url}/account/login/":
                    logging.error(f"Login for user {self.username} failed")
                    return 1

                if r.url.startswith(f"{self.url}/account/two-factor/"):
                    form_action = r.url[len(self.url):]
                    parser = CsfrParser(form_action)
                    parser.feed(r.text)
                    if not parser.csrf:
                        raise ValueError(f"No CSFR found in {form_action}")
                    csrf = parser.csrf
                    two_factor = True
                    two_factor_url = r.url

            if two_factor:
                auth_code = input("Authentication code: ")
                with s.post(two_factor_url, data={"csrf_token": csrf,
                                                  "method": "totp",
                                                  "totp_value": auth_code},
                            headers={"referer": two_factor_url}) as r:
                    r.raise_for_status()
                    if r.url == two_factor_url:
                        logging.error(f"Authentication code {auth_code} is invalid")
                        return 1

            for pkg_ver in pkg_vers:
                logging.info(f"Deleting {self.package} version {pkg_ver}")
                if not self.dry_run:
                    form_action = f"/manage/project/{self.package}/release/{pkg_ver}/"
                    form_url = f"{self.url}{form_action}"
                    with s.get(form_url) as r:
                        r.raise_for_status()
                        parser = CsfrParser(form_action, "confirm_delete_version")
                        parser.feed(r.text)
                        if not parser.csrf:
                            raise ValueError(f"No CSFR found in {form_action}")
                        csrf = parser.csrf
                        referer = r.url

                    with s.post(form_url,
                                data={"csrf_token": csrf,
                                      "confirm_delete_version": pkg_ver,
                                      },
                                headers={"referer": referer}) as r:
                        r.raise_for_status()

                    logging.info(f"Deleted {self.package} version {pkg_ver}")


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="PyPi Package Cleanup Utility",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-u", "--username", required=True, help="authentication username")
    parser.add_argument("-p", "--package", required=True, help="PyPI package name")
    parser.add_argument("-t", "--host", default="https://pypi.org/", dest="url", help="PyPI <proto>://<host> prefix")
    parser.add_argument("-r", "--version-regex", type=re.compile, action="append",
                        dest="patterns", help="regex to use to match package versions to be deleted")
    parser.add_argument("-n", "--dry-run", action="store_true", default=False, help="do not actually delete anything")
    parser.add_argument("-y", "--yes", action="store_true", default=False, dest="confirm",
                        help="confirm dangerous action")
    parser.add_argument("-v", "--verbose", action="store_const", const=1, default=0, help="be verbose")

    args = parser.parse_args()
    if args.patterns and not args.confirm and not args.dry_run:
        logging.warning(dedent(f"""
        WARNING:
        \tYou're using custom patterns: {args.patterns}.
        \tIf you make a mistake in your patterns you can potentially wipe critical versions irrecoverably.
        \tMake sure to `-n`/`--dry-run` your patterns before running the destructive cleanup.
        \tOnce you're satisfied the patterns are correct re-run with `-y`/`--yes` to confirm you know what you're doing.
        \tGoodbye.
        \t"""))
        return 3

    return PypiCleanup(**vars(args)).run()


if __name__ == "__main__":
    sys.exit(main())
