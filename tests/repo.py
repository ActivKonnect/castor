# vim: fileencoding=utf-8 tw=100 expandtab ts=4 sw=4 :
#
# Castor
# (c) 2015 ActivKonnect
# Rémy Sanchez <remy.sanchez@activkonnect.com>

import json
import unittest
import git

from shutil import rmtree, copytree
from tempfile import mkdtemp, NamedTemporaryFile
from os import path, rename, walk
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
        self.workdir = mkdtemp()
        self.test_root = path.join(self.workdir, 'repo')
        copytree(self.real_root, self.test_root)

        self.stock_git = path.join(self.test_root, 'git')
        self.tmp_git = path.join(self.test_root, '.git')

        rename(self.stock_git, self.tmp_git)

    def tearDown(self):
        rmtree(self.workdir)

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
        repo_path = path.join(self.workdir, 'test')
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

    def test_apply_file(self):
        file_path = path.join(self.workdir, '.htaccess')
        c = Castor(self.test_root)
        c.apply_file('files/htaccess', file_path)

        with open(file_path, 'r') as f:
            self.assertEqual(f.read(), 'Require all granted\n')

    def test_apply(self):
        c = Castor(self.test_root)
        c.apply()

        repo = git.Repo(path.join(self.test_root, 'lodge'))
        self.assertEqual(str(repo.head.commit), 'cb83f96c803fb1067d7932a808b6f6eddf096ae5')
        self.assertFalse(repo.is_dirty())
        self.assertEqual(repo.untracked_files, [])
        self.assertFalse(path.exists(path.join(self.test_root, 'lodge', 'modules', 'test', 'foo')))

    def test_apply_exec_post_freeze(self):
        c = Castor(self.test_root)
        c.apply(True)

        repo = git.Repo(path.join(self.test_root, 'lodge'))
        self.assertEqual(str(repo.head.commit), 'cb83f96c803fb1067d7932a808b6f6eddf096ae5')
        self.assertFalse(repo.is_dirty())
        self.assertEqual(repo.untracked_files, [])
        self.assertTrue(path.exists(path.join(self.test_root, 'lodge', 'modules', 'test', 'foo')))

    def test_write_castorfile(self):
        c = Castor(self.test_root)
        c.castorfile['lodge'][0]['version'] = 'foo'
        c.write_castorfile()

        with open(path.join(self.test_root, 'Castorfile'), 'r') as f:
            cf = json.load(f)

        self.assertEqual(cf['lodge'][0]['version'], 'foo')

    def test_update_versions(self):
        c = Castor(self.test_root)
        c.apply()

        repo_dir = path.join(self.test_root, 'lodge')
        g = git.Git(repo_dir)
        g.checkout('master')

        modified_file = path.join(self.test_root, 'lodge', 'test.txt')
        with open(modified_file, 'w') as f:
            f.write('Saluton')

        r = git.Repo(repo_dir)
        r.index.add([modified_file])
        r.index.commit('Translated to Esperanto')
        r.create_tag('tag2')

        c.update_versions()

        self.assertEqual(c.castorfile['lodge'][0]['version'], 'tag2')

    def test_freeze_subdir(self):
        c = Castor(self.test_root)
        c.apply()
        del c

        with open(path.join(self.test_root, 'Castorfile'), 'r') as f:
            d = json.load(f)

        d['lodge'][2]['version'] = 'this-version-does-not-exist'

        with open(path.join(self.test_root, 'Castorfile'), 'w') as f:
            json.dump(d, f)

        c = Castor(self.test_root)
        c.update_versions()

        self.assertEqual(c.castorfile['lodge'][2]['version'], 'tag1')

    def test_gather_dam(self):
        c = Castor(self.test_root)
        c.apply()
        c.gather_dam()

        dam_files = set()
        dam_path = path.join(self.test_root, 'dam')

        for root, dir_names, file_names in walk(dam_path):
            for file_name in file_names:
                dam_files.add(path.relpath(path.join(root, file_name), dam_path))

        self.assertEqual(dam_files, {
            'test.txt',
            'modules/test/youpi.txt',
            'modules/test/foo',
            '.htaccess',
            'app/documentation/readme.md',
        })

    def test_freeze(self):
        c = Castor(self.test_root)
        c.apply()

        repo_dir = path.join(self.test_root, 'lodge')
        g = git.Git(repo_dir)
        g.checkout('master')

        modified_file = path.join(self.test_root, 'lodge', 'test.txt')
        with open(modified_file, 'w') as f:
            f.write('Saluton')

        r = git.Repo(repo_dir)
        r.index.add([modified_file])
        r.index.commit('Translated to Esperanto')
        r.create_tag('tag2')

        c.freeze()

        with open(path.join(self.test_root, 'Castorfile'), 'r') as f:
            cf = json.load(f)
            self.assertEqual(cf['lodge'][0]['version'], 'tag2')

        with open(path.join(self.test_root, 'dam', 'test.txt')) as f:
            self.assertEqual('Saluton', f.read())

    def test_post_freeze(self):
        c = Castor(self.test_root)
        c.apply()

        c.freeze()

        self.assertTrue(path.exists(path.join(self.test_root, 'dam', 'modules', 'test', 'foo')))

    def test_freeze_files(self):
        c = Castor(self.test_root)
        c.apply()
        c.freeze()
        self.assertTrue(path.exists(path.join(self.test_root, 'dam', '.htaccess')))
        self.assertTrue(path.exists(path.join(
            self.test_root,
            'dam',
            'app/documentation/readme.md'
        )))
