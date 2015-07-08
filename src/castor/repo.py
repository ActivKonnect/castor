# vim: fileencoding=utf-8 tw=100 expandtab ts=4 sw=4 :
#
# Castor
# (c) 2015 ActivKonnect
# Rémy Sanchez <remy.sanchez@activkonnect.com>

import json
import jsonschema
import git

from os import path, listdir
from io import StringIO


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

        self.root = root
        self.castorfile = json.load(fp)


def validate_repo(root):
    castorfile_path = path.join(root, 'Castorfile')
    git_dir = path.join(root, '.git')

    if path.exists(castorfile_path) \
            and path.isfile(castorfile_path) \
            and path.exists(git_dir) \
            and path.isdir(git_dir):
        with open(castorfile_path, 'r') as f:
            s = StringIO(f.read())
            s.seek(0)
            if validate_castorfile(s):
                s.seek(0)
                return s


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
    if not path.exists(root) or not path.isdir(root):
        raise CastorException('"{}" does not exist or is not a directory'.format(root))

    if len(listdir(root)):
        raise CastorException('"{}" is not an empty directory')

    # noinspection PyBroadException
    try:
        repo = git.Repo.init(root)
    except:
        raise CastorException('Git repo could not be initialized')

    castorfile = path.join(root, 'Castorfile')
    with open(castorfile, 'w') as f:
        json.dump(CASTORFILE_BASE, f)

    repo.index.add([castorfile])
    repo.index.commit('Initial Castor Commit')
