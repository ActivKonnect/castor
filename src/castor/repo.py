# vim: fileencoding=utf-8 tw=100 expandtab ts=4 sw=4 :
#
# Castor
# (c) 2015 ActivKonnect
# Rémy Sanchez <remy.sanchez@activkonnect.com>

import json
import shlex
import subprocess
from tarfile import TarFile
from tempfile import NamedTemporaryFile
from shutil import copyfile, rmtree
import jsonschema
import git

from git.exc import GitCommandError
from os import path, listdir, getcwd, mkdir, makedirs
from io import StringIO

LODGE_DIR = 'lodge'
DAM_DIR = 'dam'

CASTORFILE_NAME = 'Castorfile'
CASTORFILE_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'type': 'object',
    'properties': {
        'lodge': {
            'type': 'array',
            'items': {
                'anyOf': [
                    {
                        '$ref': '#/definitions/target_git',
                    },
                    {
                        '$ref': '#/definitions/target_file',
                    },
                ],
            },
        },
    },
    'required': ['lodge'],
    'additionalProperties': False,
    'definitions': {
        'abspath': {
            'type': 'string',
            'pattern': '^/',
        },
        'git_repo': {
            'type': 'string',
            'pattern': '((\w+://)(.+@)*([\w\d\.]+)(:[\d]+){0,1}/*(.*)|'
                       'file://(.*)|'
                       '(.+@)*([\w\d\.]+):(.*))',
        },
        'target_git': {
            'type': 'object',
            'properties': {
                'target': {
                    '$ref': '#/definitions/abspath',
                },
                'type': {
                    'type': 'string',
                    'pattern': '^git$',
                },
                'repo': {
                    '$ref': '#/definitions/git_repo'
                },
                'version': {
                    'type': 'string',
                },
                'post_freeze': {
                    'type': 'array',
                    'items': {
                        'type': 'string',
                    }
                },
            },
            'required': ['target', 'type', 'repo', 'version'],
            'additionalProperties': False,
        },
        'target_file': {
            'type': 'object',
            'properties': {
                'target': {
                    '$ref': '#/definitions/abspath',
                },
                'type': {
                    'type': 'string',
                    'pattern': '^file$',
                },
                'source': {
                    'type': 'string',
                },
            },
            'required': ['target', 'type', 'source'],
            'additionalProperties': False,
        },
    },
}

CASTORFILE_BASE = {
    'lodge': [],
}


class CastorException(Exception):
    """
    Emitted when something went wrong, holds the error message to be displayed to the user.
    """
    pass


class Castor(object):
    """
    Main Castor class. Most actions of the CLI map to this class. Does all the actions on an
    existing Castor repo.
    """

    def __init__(self, root):
        fp = validate_repo(root)

        if fp is None:
            raise CastorException('"{}" is not a valid Castor root. Does it include a Castorfile'
                                  'and is it a Git root? Is the Castorfile valid?'.format(root))

        self.root = path.realpath(root)
        self.castorfile = json.load(fp)

    @property
    def castorfile_path(self):
        return path.join(self.root, CASTORFILE_NAME)

    @property
    def lodge_path(self):
        return path.join(self.root, LODGE_DIR)

    @property
    def dam_path(self):
        return path.join(self.root, DAM_DIR)

    @property
    def git_targets(self):
        for target in self.castorfile['lodge']:
            if target['type'] == 'git':
                yield target

    @property
    def git_targets_with_submodules(self):
        to_explore = list(self.git_targets)

        for target in to_explore:
            for submodule in git.Repo(self.target_lodge_path(target)).submodules:
                new_target = {
                    'type': 'git',
                    'target': '/' + path.relpath(submodule.abspath, self.lodge_path),
                }
                to_explore.append(new_target)

        yield from self.sorted_targets(to_explore)

    @staticmethod
    def sorted_targets(targets):
        targets = list(targets)
        for target_i, target_path in sorted(((i, x['target']) for i, x in enumerate(targets)),
                                            key=lambda x: x[1]):
            yield targets[target_i]

    def write_castorfile(self):
        """
        Validates then writes the current in-memory Castorfile to the disk.
        """
        try:
            jsonschema.validate(self.castorfile, CASTORFILE_SCHEMA)
            with open(self.castorfile_path, 'w') as f:
                json.dump(self.castorfile, f, indent=4)
        except jsonschema.ValidationError:
            raise CastorException('Trying to write an invalid Castorfile!')

    def abs_path(self, rel_path):
        """
        Returns an absolute path to the specified relative path
        """

        return path.join(self.root, rel_path)

    def target_lodge_path(self, target):
        """
        Returns the absolute path of a target's lodge
        """
        return self.abs_path(path.join(LODGE_DIR, target['target'][1:]))

    def target_dam_path(self, target):
        """
        Returns the absolute path of a target's dam
        """
        return self.abs_path(path.join(DAM_DIR, target['target'][1:]))

    def exec_post_freeze(self, target, is_apply=False):

        if is_apply:
            dir_target = self.target_lodge_path(target)
        else:
            dir_target = self.target_dam_path(target)

        print('Executing post freeze for target {}'.format(target['target']))

        for cl in target['post_freeze']:
            print(cl)
            subprocess.Popen(shlex.split(cl), cwd=dir_target).wait()

    def apply(self, exec_post_freeze=False):
        """
        For each existing target, checkout/copy the target at the right version.
        """

        targets = {self.target_lodge_path(x): x for x in self.castorfile['lodge']}

        git_dirs = []
        files = []

        for target_path in sorted(targets.keys()):
            target = targets[target_path]

            if target['type'] == 'git':
                self.apply_git(target_path, target['repo'], target['version'])
                git_dirs.append(target_path)

                if 'post_freeze' in target and exec_post_freeze:
                    self.exec_post_freeze(target, is_apply=True)

            elif target['type'] == 'file':
                self.apply_file(target['source'], target_path)
                files.append(target_path)

        self.ignore_sub_repos(git_dirs)
        self.ignore_files(files, git_dirs)

    @staticmethod
    def apply_git(target_path, repo, version):
        """
        Put a Git target to the right version.
        :param target_path: path to checkout the Git repo
        :param repo: URL to the Git repo
        :param version: version (commit or tag) to put the repository at
        :return:
        """
        if not path.exists(target_path):
            makedirs(path.dirname(target_path), exist_ok=True)
            try:
                git.Git().clone(repo, target_path)
                repo = git.Repo(target_path)

                for submodule in repo.submodules:
                    submodule.update(recursive=True, init=True)
            except GitCommandError:
                raise CastorException('Unable to clone "{}"'.format(repo))
        elif not path.exists(path.join(target_path, '.git')):
            raise CastorException('"{}" is not a git root. Supposed to be a clone of "{}".'
                                  .format(target_path, repo))

        g = git.Git(target_path)

        try:
            g.checkout(version)
        except GitCommandError:
            g.fetch('origin')

            try:
                g.checkout(version)
            except GitCommandError:
                raise CastorException('Could not checkout version "{}" of "{}". Most likely because'
                                      ' it does not exist or because your repo is dirty.'
                                      .format(version, repo))

        repo = git.Repo(target_path)
        if not repo.head.is_detached:
            g.pull('origin')

    def apply_file(self, source, target):
        """
        Copies a file to its target
        """

        source_file = path.join(self.root, source)

        if not path.exists(path.dirname(target)):
            makedirs(path.dirname(target), exist_ok=True)

        copyfile(source_file, target)

    @staticmethod
    def ignore_sub_repos(paths):
        """
        Changes the git info/exclude file in order that all repos ignore each other without needing
        to touch the .gitignore file.
        :param paths: Paths of all the Git repos
        """

        for repo in paths:
            for sub in (x for x in paths if x.startswith(repo) and x != repo):
                ignore_path = '/' + path.relpath(sub, repo)
                ensure_line_in_file(path.join(repo, '.git', 'info', 'exclude'), ignore_path)

    @staticmethod
    def ignore_files(files, repos):
        """
        Ignore the given list of files from within the given list of repos. Same as ignore_sub_repos
        but for files, basically.
        """

        for repo in repos:
            ignore_file = path.join(repo, '.git', 'info', 'exclude')
            for file in (x for x in files if x.startswith(repo)):
                ignore_path = '/' + path.relpath(file, repo)
                ensure_line_in_file(ignore_file, '{}'.format(ignore_path))

    def update_versions(self):
        """
        Look at the current version of the targets, and update the in-memory Castorfile
        accordingly.

        This will return True if a change was detected.
        """

        changed = False

        for target in self.git_targets:
            repo = git.Repo(self.target_lodge_path(target))
            commit = repo.head.commit.hexsha

            if commit != target['version']:
                found = False
                tag = commit

                for ref in repo.refs:
                    if ref.commit.hexsha == commit:
                        if isinstance(ref, git.TagReference):
                            tag = ref.name

                        if ref.name == target['version']:
                            found = True
                            break

                if not found:
                    target['version'] = tag
                    changed = True

        return changed

    def gather_dam(self):
        """
        Replaces the current dam (if it exists) with a copy if the lodge's current version (but NOT
        the current state of lodge on the disk, instead it checks out the HEAD of all git repos).
        """

        if path.exists(self.dam_path):
            rmtree(self.dam_path)

        for target in self.git_targets_with_submodules:
            repo = git.Repo(self.target_lodge_path(target))
            dam_target = self.target_dam_path(target)
            makedirs(dam_target, exist_ok=True)

            with NamedTemporaryFile('wb') as f:
                repo.archive(f, format='tar')

                with TarFile(f.name, 'r') as t:
                    t.extractall(dam_target, members=(x for x in t.getmembers()
                                                      if path.basename(x.name) != '.gitignore'))

        for target in self.sorted_targets(self.castorfile['lodge']):
            if target['type'] == 'file':
                self.apply_file(target['source'], self.target_dam_path(target))

        for target in self.git_targets:
            if 'post_freeze' in target:
                self.exec_post_freeze(target)

    def freeze(self):
        """
        The goal is to update current versions to the current Git HEADs, and gather all the files
        in the dam directory.
        If any change is detected, the Castorfile will be written on disk and the changes will be
        added to the Git index.
        """

        def path_in_dam(to_test):
            return path.join(self.root, to_test).startswith(path.join(self.dam_path, ''))

        changed = self.update_versions()

        if changed or True:
            self.gather_dam()
            self.write_castorfile()

            repo = git.Repo(self.root)
            staged = {CASTORFILE_NAME}

            for diff in repo.index.diff(None):
                is_interesting = ((diff.b_path is not None and path_in_dam(diff.b_path)) or
                                  (diff.a_path is not None and path_in_dam(diff.a_path)))

                if is_interesting:
                    if diff.a_path is not None:
                        staged.add(diff.a_path)

                    if diff.b_path is not None:
                        staged.add(diff.b_path)

            for file_name in repo.untracked_files:
                if path_in_dam(file_name):
                    staged.add(file_name)

            for p in staged:
                repo.git.add(p)


def validate_repo(root):
    """
    Returns a read-only file-like object to the Castorfile if the repo is valid, or None otherwise.
    """

    castorfile_path = path.join(root, CASTORFILE_NAME)
    git_dir = path.join(root, '.git')

    if path.exists(castorfile_path) \
            and path.isfile(castorfile_path) \
            and path.exists(git_dir) \
            and path.isdir(git_dir):
        with open(castorfile_path, 'r') as f:
            s = StringIO(f.read())
            s.seek(0)
            if not validate_castorfile(s):
                return

            # noinspection PyBroadException
            try:
                git.Repo(root)
                s.seek(0)
                return s
            except:
                return


def find_repo(from_path):
    """
    Finds the nearest repo root in the hierarchy starting at and above from_path.
    """

    next_candidate = path.realpath(from_path)
    candidate = None

    while next_candidate != candidate:
        candidate = next_candidate

        if validate_repo(candidate) is not None:
            return candidate

        next_candidate = path.dirname(candidate)


def validate_castorfile(fp):
    """
    Returns True if the given file-like object points to a valid Castorfile, false otherwise.
    """

    contents = json.load(fp)
    try:
        jsonschema.validate(contents, CASTORFILE_SCHEMA)
        return True
    except jsonschema.ValidationError:
        return False


def init(root):
    """
    Creates an empty Castor project in the given repository.
    """

    root = path.normpath(path.join(getcwd(), root))
    parent = path.normpath(path.join(root, '..'))

    dir_invalid = not path.exists(root) or not path.isdir(root)
    parent_invalid = not path.exists(parent) or not path.isdir(parent)

    if dir_invalid and parent_invalid:
        raise CastorException('"{}" does not exist or is not a directory'.format(root))
    elif parent_invalid:
        raise CastorException('"{}"\'s parent directory does not exist or is invalid'.format(root))

    if dir_invalid:
        if not path.exists(root):
            mkdir(root)
        else:
            raise CastorException('"{}" exists and is not a directory'.format(root))

    if len(listdir(root)):
        raise CastorException('"{}" is not an empty directory')

    # noinspection PyBroadException
    try:
        repo = git.Repo.init(root)
    except:
        raise CastorException('Git repo could not be initialized')

    castorfile = path.join(root, CASTORFILE_NAME)
    with open(castorfile, 'w') as f:
        json.dump(CASTORFILE_BASE, f, indent=4)

    ignorefile = path.join(root, '.gitignore')
    with open(ignorefile, 'w') as f:
        f.write('/lodge\n')

    repo.index.add([castorfile, ignorefile])
    repo.index.commit('Initial Castor Commit')


def ensure_line_in_file(file_path, line):
    """
    Ensure that the line exists in the file at file_path. If the line has no line feed at the end,
    one is automatically appended.
    """

    l = ''
    c = 0

    with open(file_path, 'r') as f:
        for l in f.readlines():
            c += 1
            if l.strip() == line.strip():
                return

    with open(file_path, 'a') as f:
        if not l.endswith('\n') and c > 0:
            f.write('\n')

        f.write(line)

        if not line.endswith('\n'):
            f.write('\n')
