import json
import os

from mopack.path import pushd
from mopack.platforms import platform_name

from . import *


class TestCustomBuilder(IntegrationTest):
    def setUp(self):
        self.stage = stage_dir('custom-builder')

    def test_resolve(self):
        config = os.path.join(test_data_dir, 'mopack-custom-builder.yml')
        self.assertPopen(['mopack', 'resolve', config])
        self.assertExists('mopack/src/hello/hello-bfg/build.bfg')
        self.assertExists('mopack/build/hello/')
        self.assertExists('mopack/logs/hello.log')
        self.assertExists('mopack/mopack.json')

        output = json.loads(self.assertPopen([
            'mopack', 'usage', 'hello', '--json'
        ]))
        self.assertEqual(output, {
            'name': 'hello',
            'type': 'pkg-config',
            'path': os.path.join(self.stage, 'mopack', 'build', 'hello',
                                 'pkgconfig'),
            'pcfiles': ['hello'],
            'extra_args': [],
        })

        output = json.loads(slurp('mopack/mopack.json'))
        self.assertEqual(output['metadata'], {
            'options': {
                'common': {
                    'target_platform': platform_name(),
                    'env': AlwaysEqual(),
                    'deploy_paths': {},
                },
                'builders': [],
                'sources': [],
            },
            'packages': [{
                'name': 'hello',
                'config_file': config,
                'resolved': True,
                'source': 'tarball',
                'url': None,
                'path': {'base': 'cfgdir', 'path': 'hello-bfg.tar.gz'},
                'files': [],
                'srcdir': None,
                'guessed_srcdir': 'hello-bfg',
                'patch': None,
                'submodules': None,
                'should_deploy': True,
                'builder': {
                    'type': 'custom',
                    'name': 'hello',
                    'build_commands': [
                        ['bfg9000', 'configure',
                         {'base': 'builddir', 'path': ''}],
                        ['ninja', '-C',
                         [{'base': 'builddir', 'path': ''}, '/.']],
                    ],
                    'deploy_commands': [
                        ['ninja', 'install'],
                    ],
                    'usage': {
                        'type': 'pkg-config',
                        'path': {'base': 'builddir', 'path': 'pkgconfig'},
                        'pcfile': 'hello',
                        'extra_args': [],
                    },
                },
            }],
        })


class TestCustomBuilderDeploy(IntegrationTest):
    def setUp(self):
        self.stage = stage_dir('custom-builder-deploy')
        self.prefix = stage_dir('custom-builder-install', chdir=False)

    def test_resolve(self):
        config = os.path.join(test_data_dir, 'mopack-custom-builder.yml')
        self.assertPopen(['mopack', 'resolve', config,
                          '-Pprefix=' + self.prefix])
        self.assertExists('mopack/src/hello/hello-bfg/build.bfg')
        self.assertExists('mopack/build/hello/')
        self.assertExists('mopack/logs/hello.log')
        self.assertExists('mopack/mopack.json')

        output = json.loads(self.assertPopen([
            'mopack', 'usage', 'hello', '--json'
        ]))
        self.assertEqual(output, {
            'name': 'hello',
            'type': 'pkg-config',
            'path': os.path.join(self.stage, 'mopack', 'build', 'hello',
                                 'pkgconfig'),
            'pcfiles': ['hello'],
            'extra_args': [],
        })

        output = json.loads(slurp('mopack/mopack.json'))
        self.assertEqual(output['metadata'], {
            'options': {
                'common': {
                    'target_platform': platform_name(),
                    'env': AlwaysEqual(),
                    'deploy_paths': {
                        'prefix': self.prefix
                    },
                },
                'builders': [],
                'sources': [],
            },
            'packages': [{
                'name': 'hello',
                'config_file': config,
                'resolved': True,
                'source': 'tarball',
                'url': None,
                'path': {'base': 'cfgdir', 'path': 'hello-bfg.tar.gz'},
                'files': [],
                'srcdir': None,
                'guessed_srcdir': 'hello-bfg',
                'patch': None,
                'submodules': None,
                'should_deploy': True,
                'builder': {
                    'type': 'custom',
                    'name': 'hello',
                    'build_commands': [
                        ['bfg9000', 'configure',
                         {'base': 'builddir', 'path': ''},
                         ['--prefix=', {'base': 'absolute',
                                        'path': self.prefix}]],
                        ['ninja', '-C',
                         [{'base': 'builddir', 'path': ''}, '/.']],
                    ],
                    'deploy_commands': [
                        ['ninja', 'install'],
                    ],
                    'usage': {
                        'type': 'pkg-config',
                        'path': {'base': 'builddir', 'path': 'pkgconfig'},
                        'pcfile': 'hello',
                        'extra_args': [],
                    },
                },
            }],
        })

        self.assertPopen(['mopack', '--debug', 'deploy'])
        include_prefix = '' if platform_name() == 'windows' else 'include/'
        lib_prefix = '' if platform_name() == 'windows' else 'lib/'
        with pushd(self.prefix):
            self.assertExists(include_prefix + 'hello.hpp')
            self.assertExists(lib_prefix + 'pkgconfig/hello.pc')