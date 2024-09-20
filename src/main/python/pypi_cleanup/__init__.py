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
from requests.__version__ import __version__ as requests_version
from requests.exceptions import RequestException

from pypi_cleanup.__version__ import __version__

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
    def __init__(self, url, username, packages, do_it, patterns, verbose, days, query_only, leave_most_recent_only,
                 confirm, delete_project, **_):
        self.url = urlparse(url).geturl()
        if self.url[-1] == "/":
            self.url = self.url[:-1]
        self.username = username
        self.do_it = do_it
        self.confirm = confirm
        self.delete_project = delete_project
        self.packages = packages
        self.patterns = patterns or DEFAULT_PATTERNS
        self.verbose = verbose
        self.query_only = query_only
        self.leave_most_recent_only = leave_most_recent_only
        self.date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

    def run(self):
        csrf = None

        if self.verbose:
            logging.root.setLevel(logging.DEBUG)

        if not self.query_only:
            if self.do_it:
                logging.warning("!!! POSSIBLE DESTRUCTIVE OPERATION !!!")
            else:
                logging.info("Running in DRY RUN mode")
        else:
            logging.info("Running in QUERY-ONLY mode")

        for package in self.packages:
            if not self.leave_most_recent_only:
                logging.info(f"Will use the following patterns {self.patterns} on package {package!r}")
            else:
                logging.info(f"Will only leave the MOST RECENT version of the package {package!r}")

        with requests.Session() as s:
            s.headers.update({"User-Agent": f"pypi-cleanup/{__version__} (requests/{requests_version})"})

            pkg_to_pkg_vers = {}
            for package in self.packages:
                with s.get(f"{self.url}/simple/{package}/",
                           headers={"Accept": "application/vnd.pypi.simple.v1+json"}) as r:
                    try:
                        r.raise_for_status()
                    except RequestException as e:
                        logging.error(f"Unable to find package {package!r}", exc_info=e)
                        return 1

                    project_info = r.json()
                    releases_by_date = {}

                    def package_matches_file(p, v, f):
                        filename = f["filename"].lower()
                        if filename.endswith(".whl") or filename.endswith(".egg") or filename.endswith(".src.rpm"):
                            return filename.startswith(f"{p.replace('-', '_')}-{v}-")

                        return filename in (f"{p}-{v}.tar.gz", f"{p}-{v}.zip")

                    for version in project_info["versions"]:
                        releases_by_date[version] = max(
                            [datetime.datetime.strptime(f["upload-time"], "%Y-%m-%dT%H:%M:%S.%f%z")
                             for f in project_info["files"]
                             if package_matches_file(package, version, f)])

                if not releases_by_date:
                    logging.info(f"No releases for package {package!r} have been found")
                    continue

                if self.leave_most_recent_only:
                    leave_release = max(releases_by_date, key=releases_by_date.get)
                    logging.info(
                        f"Leaving the MOST RECENT version for {package!r}: {leave_release} - "
                        f"{releases_by_date[leave_release].strftime('%Y-%m-%dT%H:%M:%S.%f%z')}")
                    pkg_vers = list(r for r in releases_by_date if r != leave_release)
                else:
                    pkg_vers = list(filter(lambda k:
                                           any(filter(lambda rex: rex.match(k),
                                                      self.patterns)) and releases_by_date[k] < self.date,
                                           releases_by_date.keys()))

                if not pkg_vers:
                    logging.info(f"No releases were found matching specified patterns "
                                 f"and dates in package {package!r}")
                else:
                    logging.info(f"Found the following releases of package {package!r} to delete:")
                    for pkg_ver in pkg_vers:
                        logging.info(f" {pkg_ver}")

                if pkg_vers and set(pkg_vers) == set(releases_by_date.keys()):
                    msg = f"""
                    WARNING:
                    \tYou have selected the following patterns: {self.patterns}
                    \tThese patterns would delete ALL AVAILABLE RELEASED VERSIONS of {package!r}.
                    \tThis will render your project/package permanently inaccessible.
                    """

                    if not self.delete_project:
                        print(dedent(f"""
                        {msg}
                        \tSince the costs of an error are too high I'm refusing to do this.
                        \tGoodbye.
                        """), file=sys.stderr)
                        return 3
                    else:
                        print(dedent(f"""
                        {msg}
                        \tSince you've specified "--delete-project", I will proceed anyway.
                        """), file=sys.stderr)

                if pkg_vers:
                    pkg_to_pkg_vers[package] = pkg_vers

            if self.query_only:
                logging.info("Query-only mode - exiting")
                return

            if not pkg_to_pkg_vers:
                return

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

            if self.do_it:
                logging.warning("!!! WILL ACTUALLY DELETE THINGS - LAST CHANCE TO CHANGE YOUR MIND !!!")
                logging.warning("Sleeping for 5 seconds - Ctrl-C to abort!")
                time.sleep(5.0)

            for package, pkg_vers in pkg_to_pkg_vers.items():
                for pkg_ver in pkg_vers:
                    if self.do_it:
                        logging.info(f"Deleting {package!r} version {pkg_ver}")
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

                        logging.info(f"Deleted {package!r} version {pkg_ver}")
                    else:
                        logging.info(f"Would be deleting {package!r} version {pkg_ver}, but not doing it!")


def main():
    logging.basicConfig(level=logging.INFO)

    try:
        parser = argparse.ArgumentParser(description=f"PyPi Package Cleanup Utility v{__version__}",
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("-u", "--username", help="authentication username")
        parser.add_argument("-p", "--package", dest="packages", action="append", required=True,
                            help="PyPI package name")
        parser.add_argument("-t", "--host", default="https://pypi.org/", dest="url",
                            help="PyPI <proto>://<host> prefix")
        g = parser.add_mutually_exclusive_group()
        g.add_argument("-r", "--version-regex", type=re.compile, action="append",
                       dest="patterns", help="regex to use to match package versions to be deleted")
        g.add_argument("--leave-most-recent-only", action="store_true", default=False,
                       help="delete all releases except the *most recent* one, i.e. the one containing "
                            "the most recently created files")
        parser.add_argument("--query-only", action="store_true", default=False,
                            help="only queries and processes the package, no login required")
        parser.add_argument("--do-it", action="store_true", default=False,
                            help="actually perform the destructive delete")
        parser.add_argument("--delete-project", action="store_true", default=False,
                            help="actually perform the destructive delete that will remove all versions of the project")
        parser.add_argument("-y", "--yes", action="store_true", default=False, dest="confirm",
                            help="confirm extremely dangerous destructive delete")
        parser.add_argument("-d", "--days", type=int, default=0,
                            help="only delete releases **matching specified patterns** where all files are "
                                 "older than X days")
        parser.add_argument("-v", "--verbose", action="store_const", const=1, default=0, help="be verbose")

        args = parser.parse_args()
        if args.patterns and not args.confirm and not args.do_it and not args.query_only:
            logging.warning(dedent(f"""
            WARNING:
            \tYou're using custom patterns: {args.patterns}.
            \tIf you make a mistake in your patterns you can potentially wipe critical versions irrecoverably.
            \tMake sure to test your patterns before running the destructive cleanup.
            \tOnce you're satisfied the patterns are correct re-run with `-y`/`--yes` to confirm you know what you're doing.
            \tGoodbye.
            \t"""))
            return 3

        if args.leave_most_recent_only and not args.confirm and not args.do_it and not args.query_only:
            logging.warning(dedent("""
            WARNING:
            \tYou're trying to delete ALL versions of the package EXCEPT for the *most recent one*, i.e.
            \tthe one with the most recent (by the wall clock) files, disregarding the actual version numbers
            \tor versioning schemes!
            \t
            \tYou can potentially wipe critical versions irrecoverably.
            \tMake sure this is what you really want before running the destructive cleanup.
            \tOnce you're sure you want to delete all versions except the most recent one,
            \tre-run with `-y`/`--yes` to confirm you know what you're doing.
            \tGoodbye.
            \t"""))
            return 3

        return PypiCleanup(**vars(args)).run()
    finally:
        logging.shutdown()


if __name__ == "__main__":
    sys.exit(main())
