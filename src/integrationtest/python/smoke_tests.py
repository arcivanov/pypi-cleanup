import unittest
import sys


class SmokeTest(unittest.TestCase):
    def test_smoke(self):
        import pypi_cleanup
        old_args = list(sys.argv)
        try:
            sys.argv = ["pypi-cleanup", "--query-only", "-p", "pypi-cleanup"]
            self.assertFalse(pypi_cleanup.main())
        finally:
            sys.argv = old_args


if __name__ == '__main__':
    unittest.main()
