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

import unittest
from unittest.mock import Mock, patch, MagicMock
from pypi_cleanup import PypiCleanup


class TestEmptyMatchesListRegression(unittest.TestCase):
    """
    Regression test for the bug where max() is called on an empty list when
    a package version has no matching files based on the package_matches_file filter.

    This can happen when a package has versions listed but the files don't match
    the expected naming patterns (e.g., .whl, .tar.gz, .zip with correct naming).

    Bug: ValueError: max() arg is an empty sequence
    """

    @patch('pypi_cleanup.requests.Session')
    def test_version_with_no_matching_files_does_not_crash(self, mock_session):
        """
        Test that when a version has files but none match the expected patterns,
        the code doesn't crash with ValueError from max() on empty list.
        """
        # Mock the session and response
        mock_session_instance = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_session_instance

        # Mock response for package query with a version that has no matching files
        mock_response = Mock()
        mock_response.json.return_value = {
            "name": "test-package",
            "versions": ["1.0.0"],
            "files": [
                # Files that won't match the package_matches_file filter
                {
                    "filename": "wrongname-1.0.0.tar.gz",  # Wrong package name
                    "upload-time": "2024-01-01T12:00:00.000000+00:00"
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_session_instance.get.return_value.__enter__.return_value = mock_response

        # Create PypiCleanup instance in query-only mode (no auth needed)
        cleanup = PypiCleanup(
            url="https://test.pypi.org",
            username=None,
            packages=["test-package"],
            do_it=False,
            patterns=None,
            verbose=False,
            days=0,
            query_only=True,
            leave_most_recent_only=False,
            confirm=False,
            delete_project=False
        )

        # This should not raise ValueError from max() on empty list
        try:
            result = cleanup.run()
            # In query-only mode with no matching releases, it should return None
            self.assertIsNone(result)
        except ValueError as e:
            if "max() arg is an empty sequence" in str(e):
                self.fail("max() was called on empty list - bug not fixed!")
            raise


if __name__ == '__main__':
    unittest.main()
