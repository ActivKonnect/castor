# vim: fileencoding=utf-8 tw=100 expandtab ts=4 sw=4 :
#
# Castor
# (c) 2015 ActivKonnect
# Rémy Sanchez <remy.sanchez@activkonnect.com>

import unittest
import git

from shutil import rmtree, copytree
from tempfile import mkdtemp, NamedTemporaryFile
from os import path, rename
from castor.repo import validate_castorfile, find_repo, Castor, CastorException, init, \
    ensure_line_in_file

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
            init(path.join(ASSETS_ROOT, 'this-does-not-exist', 'nope'))

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

            with open(path.join(dir_name, '.gitignore')) as f:
                self.assertEqual('/lodge\n', f.read())

            repo = git.Repo(dir_name)
            self.assertFalse(repo.bare)
            self.assertFalse(repo.is_dirty())
            self.assertEqual(repo.untracked_files, [])

        finally:
            rmtree(dir_name)


class TestEnsureLineInFile(unittest.TestCase):
    def test_ensure_when_empty(self):
        with NamedTemporaryFile('r') as f:
            ensure_line_in_file(f.name, 'hello')
            self.assertEqual(f.read(), 'hello\n')

    def test_ensure_when_content_with_line_feed(self):
        with NamedTemporaryFile('w') as f:
            f.write('hi\n')
            f.flush()

            ensure_line_in_file(f.name, 'hello')

            with open(f.name, 'r') as r:
                self.assertEqual('hi\nhello\n', r.read())

    def test_ensure_when_content_without_line_feed(self):
        with NamedTemporaryFile('w') as f:
            f.write('hi')
            f.flush()

            ensure_line_in_file(f.name, 'hello')

            with open(f.name, 'r') as r:
                self.assertEqual('hi\nhello\n', r.read())

    def test_ensure_auto_line_feed(self):
        with NamedTemporaryFile('r') as f:
            ensure_line_in_file(f.name, 'hello\n')
            self.assertEqual('hello\n', f.read())


class TestCastor(unittest.TestCase):
    def setUp(self):
        self.real_root = path.join(ASSETS_ROOT, 'test1')
        self.test_root_holder = mkdtemp()
        self.test_root = path.join(self.test_root_holder, 'repo')
        copytree(self.real_root, self.test_root)

        self.stock_git = path.join(self.test_root, 'git')
        self.tmp_git = path.join(self.test_root, '.git')

        rename(self.stock_git, self.tmp_git)

    def tearDown(self):
        rmtree(self.test_root_holder)

    def test_init(self):
        c = Castor(self.test_root)
        self.assertEqual(
            c.castorfile['lodge'][0]['repo'],
            'https://bitbucket.org/activkonnect/castor-test-1.git'
        )

    def test_init_fail(self):
        with self.assertRaises(CastorException):
            Castor(__file__)

    def test_apply_git(self):
        repo_path = path.join(self.test_root_holder, 'test')
        c = Castor(self.test_root)
        c.apply_git(
            repo_path,
            'https://github.com/Xowap/FreneticBunny.git',
            '0.1',
        )

        repo = git.Repo(repo_path)
        self.assertEqual(str(repo.head.commit), '40ac859b274e9298d29fda83540b3b72bd2f54f0')
        self.assertFalse(repo.is_dirty())
        self.assertEqual(repo.untracked_files, [])

    def test_apply(self):
        c = Castor(self.test_root)
        c.apply()

        repo = git.Repo(path.join(self.test_root, 'lodge'))
        self.assertEqual(str(repo.head.commit), 'cb83f96c803fb1067d7932a808b6f6eddf096ae5')
        self.assertFalse(repo.is_dirty())
        self.assertEqual(repo.untracked_files, [])
