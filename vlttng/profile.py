# The MIT License (MIT)
#
# Copyright (c) 2016 Philippe Proulx <eepp.ca>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import yaml
import copy


class UnknownSourceFormat(Exception):
    def __init__(self, source):
        self._source = source

    @property
    def source(self):
        return self._source


class InvalidProfile(Exception):
    pass


class ParseError(Exception):
    pass


class GitSource:
    def __init__(self, clone_url, checkout):
        self._clone_url = clone_url
        self._checkout = checkout

    @property
    def clone_url(self):
        return self._clone_url

    @property
    def checkout(self):
        return self._checkout


class HttpFtpSource:
    def __init__(self, url):
        self._url = url

    @property
    def url(self):
        return self._url


class Project:
    def __init__(self, name, source, configure, build_env):
        self._name = name
        self._source = source
        self._configure = configure
        self._build_env = build_env

    @property
    def name(self):
        return self._name

    @property
    def source(self):
        return self._source

    @property
    def configure(self):
        return self._configure

    @property
    def build_env(self):
        return self._build_env


class Profile:
    def __init__(self, env, projects):
        self._env = env
        self._projects = projects

    @property
    def env(self):
        return self._env

    @property
    def projects(self):
        return self._projects


def _source_from_project_node(project_node):
    source = project_node['source']

    if source.startswith('git://') or source.endswith('.git'):
        checkout = 'master'

        if 'checkout' in project_node:
            checkout_node = project_node['checkout']

            if checkout_node is not None:
                checkout = checkout_node

        return GitSource(source, checkout)

    if source.startswith('http://') or source.startswith('https://') or source.startswith('ftp://'):
        return HttpFtpSource(source)

    raise UnknownSourceFormat(source)


def _merge_envs(enva, envb):
    env = copy.deepcopy(enva)
    env.update(envb)

    return env


def _project_from_project_node(name, project_node, base_env):
    source = _source_from_project_node(project_node)
    configure = ''
    build_env = {}

    if 'configure' in project_node:
        configure_node = project_node['configure']

        if configure_node is not None:
            configure = str(configure_node)

    if 'build-env' in project_node:
        build_env_node = project_node['build-env']

        if build_env_node is not None:
            build_env = _merge_envs(base_env, build_env_node)
    else:
        build_env = copy.deepcopy(base_env)

    return Project(name, source, configure, build_env)


def _validate_projects(projects):
    valid_project_names = (
        'lttng-tools',
        'lttng-ust',
        'lttng-modules',
        'babeltrace',
        'urcu',
    )

    for name in projects:
        if name not in valid_project_names:
            raise InvalidProfile('Unknown project name: "{}"'.format(name))

    if 'lttng-tools' in projects or 'lttng-ust' in projects:
        if 'urcu' not in projects:
            raise InvalidProfile('"urcu" project is needed by "lttng-tools" or "lttng-ust" project')


def _merge_nodes(base, patch):
    if isinstance(base, dict) and isinstance(patch, dict):
        for k, v in patch.items():
            if isinstance(v, dict) and k in base:
                _merge_nodes(base[k], v)
            else:
                if k == 'configure' and type(v) is str:
                    if k not in base:
                        base[k] = ''

                    base[k] += ' {}'.format(v)
                else:
                    base[k] = v


def _from_yaml_files(paths, ignored_projects, verbose):
    root_node = {}

    for path in paths:
        with open(path) as f:
            patch_root_node = yaml.load(f)
            _merge_nodes(root_node, patch_root_node)

    if verbose:
        print('Effective profile:')
        print()
        print(yaml.dump(root_node, explicit_start=True, explicit_end=True,
                        indent=2, default_flow_style=False))

    base_env = root_node.get('env', {})
    projects = {}

    for name, project_node in root_node['projects'].items():
        if name in ignored_projects:
            continue

        if project_node is None:
            continue

        project = _project_from_project_node(name, project_node, base_env)
        projects[name] = project

    _validate_projects(projects)

    return Profile(base_env, projects)


def from_yaml_files(paths, ignored_projects, verbose):
    try:
        return _from_yaml_files(paths, ignored_projects, verbose)
    except (UnknownSourceFormat, InvalidProfile):
        raise
    except Exception as e:
        raise ParseError() from e
