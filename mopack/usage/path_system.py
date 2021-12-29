import os
import re
import subprocess
from itertools import chain

from . import preferred_path_base, Usage
from . import submodules as submod
from .. import types
from ..commands import Metadata
from ..environment import get_pkg_config
from ..freezedried import DictFreezeDryer, FreezeDried, ListFreezeDryer
from ..iterutils import ismapping, listify
from ..package_defaults import DefaultResolver
from ..path import file_outdated, isfile, Path
from ..pkg_config import generated_pkg_config_dir, write_pkg_config
from ..platforms import package_library_name
from ..shell import ShellArguments, split_paths
from ..types import dependency_string, Unset


# XXX: Getting build configuration like this from the environment is a bit
# hacky. Maybe there's a better way?

def _system_include_path(env=os.environ):
    return [Path(i) for i in split_paths(env.get('MOPACK_INCLUDE_PATH'))]


def _system_lib_path(env=os.environ):
    return [Path(i) for i in split_paths(env.get('MOPACK_LIB_PATH'))]


def _system_lib_names(env=os.environ):
    return split_paths(env.get('MOPACK_LIB_NAMES'))


def _library(field, value):
    try:
        return types.string(field, value)
    except types.FieldError:
        value = types.dict_shape({
            'type': types.constant('library', 'guess', 'framework'),
            'name': types.string
        }, desc='library')(field, value)
        if value['type'] == 'library':
            return value['name']
        return value


def _list_of_paths(base):
    return types.list_of(types.abs_or_inner_path(base), listify=True)


_version_def = types.one_of(
    types.maybe(types.string),
    types.dict_shape({
        'type': types.constant('regex'),
        'file': types.string,
        'regex': types.list_of(
            types.one_of(
                types.string,
                types.list_of_length(types.string, 2),
                desc='string or pair of strings'
            )
        ),
    }, desc='version finder'),
    desc='version definition'
)

_list_of_headers = types.list_of(types.string, listify=True)
_list_of_libraries = types.list_of(_library, listify=True)

_PathListFD = ListFreezeDryer(Path)


class _SubmoduleMapping(FreezeDried):
    def __init__(self, symbols, path_bases, *, include_path=None,
                 library_path=None, headers=None, libraries=None,
                 compile_flags=None, link_flags=None):
        # Just check that we can fill submodule values correctly.
        self._fill(locals(), symbols, path_bases)

        # Since we need to delay evaluating symbols until we know what the
        # selected submodule is, just store these values unevaluated. We'll
        # evaluate them later during `mopack usage` via the fill() function.
        self.include_path = include_path
        self.library_path = library_path
        self.headers = headers
        self.libraries = libraries
        self.compile_flags = compile_flags
        self.link_flags = link_flags

    def _fill(self, context, symbols, path_bases, submodule_name='SUBMODULE'):
        def P(other):
            return types.placeholder_fill(other, submod.placeholder,
                                          submodule_name)

        srcbase = preferred_path_base('srcdir', path_bases)
        buildbase = preferred_path_base('builddir', path_bases)
        symbols = symbols.augment(symbols=submod.expr_symbols)

        result = type(self).__new__(type(self))
        T = types.TypeCheck(context, symbols, dest=result)
        T.include_path(P(_list_of_paths(srcbase)))
        T.library_path(P(_list_of_paths(buildbase)))
        T.headers(P(_list_of_headers))
        T.libraries(P(_list_of_libraries))
        T.compile_flags(P(types.shell_args(none_ok=True)))
        T.link_flags(P(types.shell_args(none_ok=True)))
        return result

    def fill(self, symbols, path_bases, submodule_name):
        return self._fill(self.__dict__, symbols, path_bases, submodule_name)


def _submodule_map(symbols, path_bases):
    def check_item(field, value):
        with types.wrap_field_error(field):
            return _SubmoduleMapping(symbols, path_bases, **value)

    def check(field, value):
        try:
            value = {'*': {
                'libraries': types.placeholder_string(field, value)
            }}
        except types.FieldError:
            pass

        return types.dict_of(types.string, check_item)(field, value)

    return check


@FreezeDried.fields(rehydrate={
    'include_path': _PathListFD, 'library_path': _PathListFD,
    'compile_flags': ShellArguments, 'link_flags': ShellArguments,
    'submodule_map': DictFreezeDryer(value_type=_SubmoduleMapping),
})
class PathUsage(Usage):
    type = 'path'
    _version = 1

    @staticmethod
    def upgrade(config, version):
        return config

    def __init__(self, pkg, *, auto_link=Unset, version=Unset,
                 include_path=Unset, library_path=Unset, headers=Unset,
                 libraries=Unset, compile_flags=Unset, link_flags=Unset,
                 submodule_map=Unset, inherit_defaults=False):
        super().__init__(pkg, inherit_defaults=inherit_defaults)

        path_bases = pkg.path_bases(builder=True)
        symbols = self._options.expr_symbols.augment(paths=path_bases)
        pkg_default = DefaultResolver(self, symbols, inherit_defaults,
                                      pkg.name)
        srcbase = preferred_path_base('srcdir', path_bases)
        buildbase = preferred_path_base('builddir', path_bases)

        T = types.TypeCheck(locals(), symbols)
        # XXX: Maybe have the compiler tell *us* if it supports auto-linking,
        # instead of us telling it?
        T.auto_link(pkg_default(types.boolean, default=False))

        T.version(pkg_default(_version_def), dest_field='explicit_version')

        # XXX: These specify the *possible* paths to find headers/libraries.
        # Should there be a way of specifying paths that are *always* passed to
        # the compiler?
        T.include_path(pkg_default(_list_of_paths(srcbase)))
        T.library_path(pkg_default(_list_of_paths(buildbase)))

        T.headers(pkg_default(_list_of_headers))

        if self.auto_link or pkg.submodules and pkg.submodules['required']:
            # If auto-linking or if submodules are required, default to an
            # empty list of libraries, since we likely don't have a "base"
            # library that always needs linking to.
            libs_checker = types.maybe(_list_of_libraries, default=[])
        else:
            libs_checker = pkg_default(
                _list_of_libraries, default={'type': 'guess', 'name': pkg.name}
            )
        T.libraries(libs_checker)
        T.compile_flags(types.shell_args(none_ok=True))
        T.link_flags(types.shell_args(none_ok=True))

        if pkg.submodules:
            T.submodule_map(pkg_default(
                types.maybe(_submodule_map(symbols, path_bases)),
                default=pkg.name + '_$submodule',
                extra_symbols=submod.expr_symbols
            ), evaluate=False)

    def _get_submodule_mapping(self, symbols, path_bases, submodule):
        try:
            mapping = self.submodule_map[submodule]
        except KeyError:
            mapping = self.submodule_map['*']
        return mapping.fill(symbols, path_bases, submodule)

    def _get_library(self, lib):
        if ismapping(lib) and lib['type'] == 'guess':
            return package_library_name(
                self._common_options.target_platform, lib['name']
            )
        return lib

    @staticmethod
    def _link_library(lib):
        if isinstance(lib, str):
            return ['-l' + lib]

        assert lib['type'] == 'framework'
        return ['-framework', lib['name']]

    @staticmethod
    def _filter_path(fn, path, files, kind):
        filtered = {}
        for f in files:
            for p in path:
                if fn(p, f):
                    filtered[p] = True
                    break
            else:
                raise ValueError('unable to find {} {!r}'.format(kind, f))
        return list(filtered.keys())

    @classmethod
    def _include_dirs(cls, headers, include_path, path_vars):
        headers = listify(headers, scalar_ok=False)
        include_path = (listify(include_path, scalar_ok=False) or
                        _system_include_path())
        return cls._filter_path(
            lambda p, f: isfile(p.append(f), path_vars),
            include_path, headers, 'header'
        )

    @classmethod
    def _library_dirs(cls, auto_link, libraries, library_path, path_vars):
        library_path = (listify(library_path, scalar_ok=False)
                        or _system_lib_path())
        if auto_link:
            # When auto-linking, we can't determine the library dirs that are
            # actually used, so include them all.
            return library_path

        lib_names = _system_lib_names()
        return cls._filter_path(
            lambda p, f: any(isfile(p.append(i.format(f)), path_vars)
                             for i in lib_names),
            library_path, (i for i in libraries if isinstance(i, str)),
            'library'
        )

    @staticmethod
    def _match_line(ex, line):
        if isinstance(ex, str):
            m = re.search(ex, line)
            line = m.group(1) if m else None
            return line is not None, line
        else:
            return True, re.sub(ex[0], ex[1], line)

    def _get_version(self, pkg, pkgdir, include_dirs, path_vars):
        if ismapping(self.explicit_version):
            version = self.explicit_version
            for path in include_dirs:
                header = path.append(version['file'])
                try:
                    with open(header.string(**path_vars)) as f:
                        for line in f:
                            for ex in version['regex']:
                                found, line = self._match_line(ex, line)
                                if not found:
                                    break
                            else:
                                return line
                except FileNotFoundError:
                    pass
            return None
        elif self.explicit_version is not None:
            return self.explicit_version
        else:
            return pkg.guessed_version(pkgdir)

    def version(self, pkg, pkgdir):
        path_values = pkg.path_values(pkgdir, builder=True)
        try:
            include_dirs = self._include_dirs(
                self.headers, self.include_path, path_values
            )
        except ValueError:  # pragma: no cover
            # XXX: This is a hack to work around the fact that we currently
            # require the build system to pass include dirs during `usage` (and
            # really, during `list-packages` too). We should handle this in a
            # smarter way and then remove this.
            include_dirs = []

        return self._get_version(pkg, pkgdir, include_dirs, path_values)

    def _write_pkg_config(self, pkg, submodule, pkgdir, requires=[],
                          mappings=None):
        if mappings is None:
            mappings = [self]

        def chain_attr(key):
            for i in mappings:
                yield from getattr(i, key)

        path_values = pkg.path_values(pkgdir, builder=True)
        pkgconfdir = generated_pkg_config_dir(pkgdir)
        pcname = dependency_string(pkg.name, listify(submodule))
        pcpath = os.path.join(pkgconfdir, pcname + '.pc')

        metadata_path = os.path.join(pkgdir, Metadata.metadata_filename)
        if file_outdated(pcpath, metadata_path):
            # Generate the pkg-config data...
            include_dirs = self._include_dirs(
                chain_attr('headers'), chain_attr('include_path'), path_values
            )
            libraries = [self._get_library(i) for i in chain_attr('libraries')]
            library_dirs = self._library_dirs(
                self.auto_link, libraries, chain_attr('library_path'),
                path_values
            )

            cflags = (
                [('-I', i) for i in include_dirs] +
                ShellArguments(chain_attr('compile_flags'))
            )
            libs = (
                [('-L', i) for i in library_dirs] +
                ShellArguments(chain_attr('link_flags')) +
                chain.from_iterable(self._link_library(i) for i in libraries)
            )
            version = self._get_version(pkg, pkgdir, include_dirs, path_values)

            # ... and write it.
            os.makedirs(pkgconfdir, exist_ok=True)
            with open(pcpath, 'w') as f:
                write_pkg_config(f, pcname, version=version or '',
                                 requires=requires, cflags=cflags, libs=libs,
                                 variables=path_values)
        return pcname

    def get_usage(self, pkg, submodules, pkgdir):
        if submodules and self.submodule_map:
            if pkg.submodules['required']:
                # Don't make a base .pc file; just include the data from the
                # base in each submodule's .pc file.
                mappings = [self]
                requires = []
            else:
                mappings = []
                requires = [self._write_pkg_config(pkg, None, pkgdir)]

            path_bases = pkg.path_bases(builder=True)
            symbols = self._options.expr_symbols.augment(paths=path_bases)

            pcnames = []
            for i in submodules:
                mapping = self._get_submodule_mapping(symbols, path_bases, i)
                pcnames.append(self._write_pkg_config(
                    pkg, i, pkgdir, requires, mappings + [mapping]
                ))
        else:
            pcnames = [self._write_pkg_config(pkg, None, pkgdir)]

        return self._usage(
            pkg, submodules, generated=True, auto_link=self.auto_link,
            path=[generated_pkg_config_dir(pkgdir)], pcfiles=pcnames
        )


class SystemUsage(PathUsage):
    type = 'system'

    def __init__(self, pkg, **kwargs):
        super().__init__(pkg, **kwargs)
        self.pcfile = pkg.name

    def version(self, pkg, pkgdir):
        pkg_config = get_pkg_config(self._common_options.env)
        try:
            return subprocess.run(
                pkg_config + [self.pcfile, '--modversion'], check=True,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                universal_newlines=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return super().version(pkg, pkgdir)

    def get_usage(self, pkg, submodules, pkgdir):
        pkg_config = get_pkg_config(self._common_options.env)
        try:
            subprocess.run(pkg_config + [self.pcfile], check=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            return self._usage(pkg, submodules, path=[], pcfiles=[self.pcfile],
                               extra_args=[])
        except (OSError, subprocess.CalledProcessError):
            return super().get_usage(pkg, submodules, pkgdir)
