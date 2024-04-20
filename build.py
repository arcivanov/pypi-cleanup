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

from pybuilder.core import use_plugin, init, Author

use_plugin("python.core")
use_plugin("python.unittest")
use_plugin("python.integrationtest")
use_plugin("python.flake8")
use_plugin("python.coverage")
use_plugin("python.distutils")
use_plugin("python.pycharm")

name = "pypi-cleanup"
version = "0.1.6.dev"
summary = "PyPI Bulk Release Version Cleanup Utility"

authors = [Author("Arcadiy Ivanov", "arcadiy@ivanov.biz")]
maintainers = [Author("Arcadiy Ivanov", "arcadiy@ivanov.biz")]
license = "Apache License, Version 2.0"

url = "https://github.com/arcivanov/pypi-cleanup"
urls = {"Bug Tracker": "https://github.com/arcivanov/pypi-cleanup/issues",
        "Source Code": "https://github.com/arcivanov/pypi-cleanup",
        "Documentation": "https://github.com/arcivanov/pypi-cleanup"
        }

requires_python = ">=3.7"

default_task = ["analyze", "publish"]


@init
def set_properties(project):
    project.depends_on("requests", "~=2.23")
    project.set_property("verbose", True)

    project.set_property("coverage_break_build", False)

    project.set_property("flake8_break_build", True)
    project.set_property("flake8_extend_ignore", "E303")
    project.set_property("flake8_include_test_sources", True)
    project.set_property("flake8_include_scripts", True)
    project.set_property("flake8_max_line_length", 130)

    project.set_property("copy_resources_target", "$dir_dist/pypi_cleanup")
    project.include_file("pypi_cleanup", "LICENSE")

    project.set_property("distutils_readme_description", True)
    project.set_property("distutils_description_overwrite", True)
    project.set_property("distutils_upload_skip_existing", True)
    project.set_property("distutils_console_scripts", ["pypi-cleanup = pypi_cleanup:main"])
    project.set_property("distutils_classifiers", [
        "Programming Language :: Python",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Software Development :: Build Tools"])
    project.set_property("distutils_setup_keywords", ["PyPI", "cleanup", "build", "dev", "tool", "release", "version"])
