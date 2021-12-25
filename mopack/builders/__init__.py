import os
import shutil
from pkg_resources import load_entry_point

from ..base_options import BaseOptions, OptionsHolder
from ..freezedried import FreezeDried
from ..path import Path
from ..placeholder import placeholder
from ..types import FieldValueError, wrap_field_error


def _get_builder_type(type, field='type'):
    try:
        return load_entry_point('mopack', 'mopack.builders', type)
    except ImportError:
        raise FieldValueError('unknown builder {!r}'.format(type), field)


class Builder(OptionsHolder):
    _options_type = 'builders'
    _type_field = 'type'
    _get_type = _get_builder_type

    Options = None

    def __init__(self, pkg):
        super().__init__(pkg._options)
        self.name = pkg.name

    def _expr_symbols(self, path_bases):
        path_vars = {i: placeholder(Path('', i)) for i in path_bases}
        return {**self._options.expr_symbols, **path_vars}

    def path_bases(self):
        return ('builddir',)

    def path_values(self, pkgdir):
        return {'builddir': self._builddir(pkgdir)}

    def filter_usage(self, usage):
        return usage

    def _builddir(self, pkgdir):
        return os.path.abspath(os.path.join(pkgdir, 'build', self.name))

    def clean(self, pkgdir):
        shutil.rmtree(self._builddir(pkgdir), ignore_errors=True)

    def __repr__(self):
        return '<{}({!r})>'.format(type(self).__name__, self.name)


class BuilderOptions(FreezeDried, BaseOptions):
    _type_field = 'type'

    @property
    def _context(self):
        return 'while adding options for {!r} builder'.format(self.type)

    @staticmethod
    def _get_type(type):
        return _get_builder_type(type).Options


def make_builder(pkg, config, *, field='build', **kwargs):
    if config is None:
        raise TypeError('builder not specified')

    if isinstance(config, str):
        type_field = ()
        type = config
        config = {}
    else:
        type_field = 'type'
        config = config.copy()
        type = config.pop('type')

    with wrap_field_error(field, type):
        return _get_builder_type(type, type_field)(pkg, **config, **kwargs)


def make_builder_options(type):
    opts = _get_builder_type(type).Options
    return opts() if opts else None
