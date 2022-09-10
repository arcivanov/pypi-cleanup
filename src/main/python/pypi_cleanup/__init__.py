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
import configparser
import datetime
import getpass
import logging
import os
import re
import sys
import time
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
            action = attrs.get("action")  # Might be None.
            if action and (action == self._target or action.startswith(self._target)):
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
    def __init__(self, url, username, packages, do_it, patterns, verbose, days, **_):
        self.url = urlparse(url).geturl()
        if self.url[-1] == "/":
            self.url = self.url[:-1]
        self.username = username
        self.do_it = do_it
        self.packages = packages
        self.patterns = patterns or DEFAULT_PATTERNS
        self.verbose = verbose
        self.date = datetime.datetime.now() - datetime.timedelta(days=days)

    def run(self):
        if self.verbose:
            logging.root.setLevel(logging.DEBUG)

        if self.do_it:
            logging.warning("!!! WILL ACTUALLY DELETE THINGS !!!")
            logging.warning("Will sleep for 3 seconds - Ctrl-C to abort!")
            time.sleep(3.0)
        else:
            logging.info("Running in DRY RUN mode")

        password = os.getenv("PYPI_CLEANUP_PASSWORD")

        if self.username is None:
            realpath = os.path.realpath(os.path.expanduser("~/.pypirc"))
            parser = configparser.RawConfigParser()
            try:
                with open(realpath) as f:
                    parser.read_file(f)
                    logging.info(f"Using configuration from {realpath}")
            except FileNotFoundError:
                logging.error(f"Could not find configuration file {realpath} and no username was set")
                return 1
            repo = None
            if self.url == "https://pypi.org":
                repo = "pypi"
            if self.url == "https://test.pypi.org":
                repo = "testpypi"
            if repo:
                self.username = parser.get(repo, "username", fallback=None)
                password = parser.get(repo, "password", fallback=None)

        if password is None:
            password = getpass.getpass("Password: ")

        for p in self.packages:
            result = self.cleanup(p, password)
            if result:
                return result


    def cleanup(self, package, password):
        logging.info(f"Will use the following patterns {self.patterns} on package {package}")
        csrf = None
        with requests.Session() as s:
            with s.get(f"{self.url}/pypi/{package}/json") as r:
                try:
                    r.raise_for_status()
                except RequestException as e:
                    logging.error(f"Unable to find package {repr(package)}", exc_info=e)
                    return 1

                release_date = {}
                for release, files in r.json()["releases"].items():
                    release_date[release] = max([datetime.datetime.strptime(f["upload_time"], '%Y-%m-%dT%H:%M:%S') for f in files])

            if not release_date:
                logging.info(f"No releases for package {package} have been found")
                return

            pkg_vers = list(filter(lambda k:
                                   any(filter(lambda rex: rex.match(k),
                                              self.patterns)) and release_date[k] < self.date,
                                   release_date.keys()))

            if not pkg_vers:
                logging.info(f"No releases were found matching specified patterns and dates in package {package}")
                return

            if set(pkg_vers) == set(release_date.keys()):
                print(dedent(f"""
                WARNING:
                \tYou have selected the following patterns: {self.patterns}
                \tThese patterns would delete all available released versions of `{package}`.
                \tThis will render your project/package permanently inaccessible.
                \tSince the costs of an error are too high I'm refusing to do this.
                \tGoodbye.
                """), file=sys.stderr)

                if not self.do_it:
                    return 3

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
                if self.do_it:
                    logging.info(f"Deleting {package} version {pkg_ver}")
                    form_action = f"/manage/project/{package}/release/{pkg_ver}/"
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

                    logging.info(f"Deleted {package} version {pkg_ver}")
                else:
                    logging.info(f"Would be deleting {package} version {pkg_ver}, but not doing it!")


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="PyPi Package Cleanup Utility",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-u", "--username", help="authentication username")
    parser.add_argument("-p", "--packages", "--package", nargs='+', help="PyPI package name(s)")
    parser.add_argument("-t", "--host", default="https://pypi.org/", dest="url", help="PyPI <proto>://<host> prefix")
    parser.add_argument("-r", "--version-regex", type=re.compile, action="append",
                        dest="patterns", help="regex to use to match package versions to be deleted")
    parser.add_argument("--do-it", action="store_true", default=False, help="actually perform the destructive delete")
    parser.add_argument("-y", "--yes", action="store_true", default=False, dest="confirm",
                        help="confirm extremely dangerous destructive delete")
    parser.add_argument("-d", "--days", type=int, default=0,
                        help="only delete releases where all files are older than X days")
    parser.add_argument("-v", "--verbose", action="store_const", const=1, default=0, help="be verbose")

    args = parser.parse_args()
    if args.patterns and not args.confirm and not args.do_it:
        logging.warning(dedent(f"""
        WARNING:
        \tYou're using custom patterns: {args.patterns}.
        \tIf you make a mistake in your patterns you can potentially wipe critical versions irrecoverably.
        \tMake sure to test your patterns before running the destructive cleanup.
        \tOnce you're satisfied the patterns are correct re-run with `-y`/`--yes` to confirm you know what you're doing.
        \tGoodbye.
        \t"""))
        return 3

    return PypiCleanup(**vars(args)).run()


if __name__ == "__main__":
    sys.exit(main())
