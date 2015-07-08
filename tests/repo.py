# vim: fileencoding=utf-8 tw=100 expandtab ts=4 sw=4 :
#
# Castor
# (c) 2015 ActivKonnect
# Rémy Sanchez <remy.sanchez@activkonnect.com>

import unittest
import git

from shutil import rmtree
from tempfile import mkdtemp
from os import path, rename
from castor.repo import validate_castorfile, find_repo, Castor, CastorException, init

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


class TestCastorInit(unittest.TestCase):
    def test_init_fail_does_not_exist(self):
        with self.assertRaises(CastorException):
            init(path.join(ASSETS_ROOT, 'this-does-not-exist'))

    def test_init_fail_is_file(self):
        with self.assertRaises(CastorException):
            init(__file__)

    def test_init_fail_dir_has_content(self):
        with self.assertRaises(CastorException):
            init(ASSETS_ROOT)

    def test_init_success(self):
        dir_name = mkdtemp()

        try:
            init(dir_name)

            with open(path.join(dir_name, 'Castorfile')) as f:
                self.assertTrue(validate_castorfile(f))

            repo = git.Repo(dir_name)
            self.assertFalse(repo.bare)
        finally:
            rmtree(dir_name)


class TestCastor(unittest.TestCase):
    def setUp(self):
        self.test_root = path.join(ASSETS_ROOT, 'test1')
        self.stock_git = path.join(self.test_root, 'git')
        self.tmp_git = path.join(self.test_root, '.git')

        rename(self.stock_git, self.tmp_git)

    def tearDown(self):
        rename(self.tmp_git, self.stock_git)

    def test_init(self):
        c = Castor(self.test_root)
        self.assertEqual(
            c.castorfile['lodge'][0]['repo'],
            'https://github.com/PrestaShop/PrestaShop.git'
        )

    def test_init_fail(self):
        with self.assertRaises(CastorException):
            Castor(__file__)
