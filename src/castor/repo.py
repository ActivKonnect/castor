# vim: fileencoding=utf-8 tw=100 expandtab ts=4 sw=4 :
#
# Castor
# (c) 2015 ActivKonnect
# Rémy Sanchez <remy.sanchez@activkonnect.com>

import json
from shutil import copyfile
import jsonschema
import git

from git.exc import GitCommandError
from os import path, listdir, getcwd, mkdir, makedirs
from io import StringIO


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
                    'type': 'string',
                    'pattern': '((\w+://)(.+@)*([\w\d\.]+)(:[\d]+){0,1}/*(.*)|'
                               'file://(.*)|'
                               '(.+@)*([\w\d\.]+):(.*))',
                },
                'version': {
                    'type': 'string',
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
    pass


class Castor(object):
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

    def write_castorfile(self):
        try:
            jsonschema.validate(self.castorfile, CASTORFILE_SCHEMA)
            with open(self.castorfile_path, 'w') as f:
                json.dump(self.castorfile, f, indent=4)
        except jsonschema.ValidationError:
            raise CastorException('Trying to write an invalid Castorfile!')

    def target_path(self, target):
        return path.join(self.root, 'lodge', target['target'][1:])

    def apply(self):
        targets = {self.target_path(x): x for x in self.castorfile['lodge']}

        git_dirs = []
        files = []

        for target_path in sorted(targets.keys()):
            target = targets[target_path]

            if target['type'] == 'git':
                self.apply_git(target_path, target['repo'], target['version'])
                git_dirs.append(target_path)
            elif target['type'] == 'file':
                self.apply_file(target['source'], target_path)
                files.append(target_path)

        self.ignore_sub_repos(git_dirs)
        self.ignore_files(files, git_dirs)

    @staticmethod
    def apply_git(target_path, repo, version):
        if not path.exists(target_path):
            makedirs(path.dirname(target_path), exist_ok=True)
            try:
                git.Git().clone(repo, target_path)
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
        source_file = path.join(self.root, source)
        copyfile(source_file, target)

    @staticmethod
    def ignore_sub_repos(paths):
        for repo in paths:
            for sub in (x for x in paths if x.startswith(repo) and x != repo):
                ignore_path = '/' + path.relpath(sub, repo)
                ensure_line_in_file(path.join(repo, '.git', 'info', 'exclude'), ignore_path)

    @staticmethod
    def ignore_files(files, repos):
        for repo in repos:
            ignore_file = path.join(repo, '.git', 'info', 'exclude')
            for file in (x for x in files if x.startswith(repo)):
                ignore_path = '/' + path.relpath(file, repo)
                ensure_line_in_file(ignore_file, '{}'.format(ignore_path))

    def freeze(self):
        changed = False

        for target in self.castorfile['lodge']:
            if target['type'] == 'git':

                repo = git.Repo(self.target_path(target))
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

        if changed:
            self.write_castorfile()


def validate_repo(root):
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
    next_candidate = path.realpath(from_path)
    candidate = None

    while next_candidate != candidate:
        candidate = next_candidate

        if validate_repo(candidate) is not None:
            return candidate

        next_candidate = path.dirname(candidate)


def validate_castorfile(fp):
    contents = json.load(fp)
    try:
        jsonschema.validate(contents, CASTORFILE_SCHEMA)
        return True
    except jsonschema.ValidationError:
        return False


def init(root):
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
