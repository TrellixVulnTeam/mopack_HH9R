import os
from pkg_resources import load_entry_point

from .. import types
from ..base_options import BaseOptions, OptionsSet
from ..freezedried import FreezeDried
from ..iterutils import listify
from ..package_defaults import DefaultResolver
from ..types import FieldError, try_load_config
from ..usage import Usage, make_usage


def _get_source_type(source, field='source'):
    try:
        return load_entry_point('mopack', 'mopack.sources', source)
    except ImportError:
        raise FieldError('unknown source {!r}'.format(source), field)


_submodule_dict = types.dict_shape({
    'names': types.one_of(types.list_of(types.string), types.constant('*'),
                          desc='a list of submodules'),
    'required': types.boolean,
}, desc='a list of submodules')


def submodules_type(field, value):
    if value is None:
        return None
    elif not isinstance(value, dict):
        value = {
            'names': value,
            'required': True,
        }
    return _submodule_dict(field, value)


@FreezeDried.fields(skip={'_options'},
                    skip_compare={'config_file', 'resolved', '_options'})
class Package(FreezeDried):
    _default_genus = 'source'
    _type_field = 'source'
    _get_type = _get_source_type

    Options = None

    def __init__(self, name, *, deploy=True, config_file):
        self.name = name
        self.should_deploy = types.boolean('deploy', deploy)
        self.config_file = config_file
        self.resolved = False

    @property
    def config_dir(self):
        return os.path.dirname(self.config_file)

    def _check_submodules(self, wanted_submodules):
        if self.submodules:
            if self.submodules['required'] and not wanted_submodules:
                raise ValueError('package {!r} requires submodules'
                                 .format(self.name))

            wanted_submodules = listify(wanted_submodules)
            if self.submodules['names'] != '*':
                for i in wanted_submodules:
                    if i not in self.submodules['names']:
                        raise ValueError(
                            'unrecognized submodule {!r} for package {!r}'
                            .format(i, self.name)
                        )
            return wanted_submodules
        elif wanted_submodules:
            raise ValueError('package {!r} has no submodules'
                             .format(self.name))
        return None

    @property
    def builder_types(self):
        return []

    def set_options(self, options):
        self._options = OptionsSet(options.common,
                                   options.sources.get(self.source))

    def clean_pre(self, pkgdir, new_package, quiet=False):
        return False

    def clean_post(self, pkgdir, new_package, quiet=False):
        return False

    def clean_all(self, pkgdir, new_package, quiet=False):
        return (self.clean_pre(pkgdir, new_package, quiet),
                self.clean_post(pkgdir, new_package, quiet))

    def fetch(self, pkgdir, parent_config):
        pass

    def get_usage(self, pkgdir, submodules):
        return self._get_usage(pkgdir, self._check_submodules(submodules))

    def __repr__(self):
        return '<{}({!r})>'.format(type(self).__name__, self.name)


@FreezeDried.fields(rehydrate={'usage': Usage})
class BinaryPackage(Package):
    def __init__(self, name, *, usage, submodules=types.Unset, symbols,
                 **kwargs):
        super().__init__(name, **kwargs)
        package_default = DefaultResolver(self, symbols, name)

        self.submodules = package_default(submodules_type)(
            'submodules', submodules
        )
        self.usage = make_usage(name, usage, submodules=self.submodules,
                                symbols=symbols)

    def set_options(self, options):
        self.usage.set_options(options)
        super().set_options(options)

    def _get_usage(self, pkgdir, submodules):
        return self.usage.get_usage(submodules, None, None)


class PackageOptions(FreezeDried, BaseOptions):
    _type_field = 'source'

    @property
    def _context(self):
        return 'while adding options for {!r} source'.format(self.source)

    @staticmethod
    def _get_type(source):
        return _get_source_type(source).Options


def make_package(name, config, **kwargs):
    fwd_config = config.copy()
    source = fwd_config.pop('source')
    return _get_source_type(source)(name, **fwd_config, **kwargs)


def try_make_package(name, config, **kwargs):
    context = 'while constructing package {!r}'.format(name)
    with try_load_config(config, context, config['source']):
        return make_package(name, config, **kwargs)


def make_package_options(source):
    opts = _get_source_type(source).Options
    return opts() if opts else None
