# vim: fileencoding=utf-8 tw=100 expandtab ts=4 sw=4 :
#
# Castor
# (c) 2015 ActivKonnect
# Rémy Sanchez <remy.sanchez@activkonnect.com>

import unittest

from os import path, rename
from castor.repo import validate_castorfile, find_repo

ASSETS_ROOT = path.join(path.dirname(__file__), 'assets')


class TestValidateCastorfile(unittest.TestCase):
    def test_validate_1(self):
        with open(path.join(ASSETS_ROOT, 'test1', 'Castorfile')) as f:
            self.assertTrue(validate_castorfile(f))


class TestRepoDiscovery(unittest.TestCase):
    def test_find_repo_none(self):
        self.assertIsNone(find_repo(__file__))

    def test_find_repo_1(self):
        test_root = path.join(ASSETS_ROOT, 'test1')
        stock_git = path.join(test_root, 'git')
        tmp_git = path.join(test_root, '.git')

        rename(stock_git, tmp_git)

        try:
            initial_path = path.join(test_root, 'lodge', 'some', 'path')
            found_path = find_repo(initial_path)
            self.assertEqual(test_root, found_path)
        finally:
            rename(tmp_git, stock_git)
