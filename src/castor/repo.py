# vim: fileencoding=utf-8 tw=100 expandtab ts=4 sw=4 :
#
# Castor
# (c) 2015 ActivKonnect
# Rémy Sanchez <remy.sanchez@activkonnect.com>

import json
import jsonschema

from os import path


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


class Castor:
    pass


def find_repo(from_path):
    next_candidate = path.realpath(from_path)
    candidate = None

    while next_candidate != candidate:
        candidate = next_candidate
        castorfile_path = path.join(candidate, 'Castorfile')
        git_dir = path.join(candidate, '.git')

        if path.exists(castorfile_path) \
                and path.isfile(castorfile_path) \
                and path.exists(git_dir) \
                and path.isdir(git_dir):
            with open(castorfile_path, 'r') as f:
                if validate_castorfile(f):
                    return candidate

        next_candidate = path.dirname(candidate)


def validate_castorfile(fp):
    contents = json.load(fp)
    try:
        jsonschema.validate(contents, CASTORFILE_SCHEMA)
        return True
    except jsonschema.ValidationError:
        return False
