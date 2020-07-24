import os
import shutil
from io import BytesIO
from urllib.request import urlopen

from . import Package, submodules_type
from .. import archive, log, types
from ..builders import Builder, make_builder
from ..config import ChildConfig
from ..log import LogFile
from ..path import filter_glob, pushd


class SDistPackage(Package):
    _rehydrate_fields = {'builder': Builder}
    _skip_compare_fields = (Package._skip_compare_fields +
                            ('pending_usage',))

    def __init__(self, name, *, build=None, usage=None, submodules=types.Unset,
                 **kwargs):
        super().__init__(name, **kwargs)
        if build is None:
            self.builder = None
            self.pending_usage = usage
            if submodules is not types.Unset:
                self.submodules = submodules_type('submodules', submodules)
        else:
            self.submodules = self._package_default(submodules_type, name)(
                'submodules', submodules
            )
            self.builder = make_builder(name, build, usage=usage,
                                        submodules=self.submodules)

    @property
    def builder_types(self):
        if self.builder is None:
            raise TypeError('cannot get builder types until builder is ' +
                            'finalized')
        return [self.builder.type]

    def set_options(self, options):
        self.builder.set_options(options)
        super().set_options(options)

    def dehydrate(self):
        if hasattr(self, 'pending_usage'):
            raise TypeError('cannot dehydrate until `pending_usage` is ' +
                            'finalized')
        return super().dehydrate()

    def _find_mopack(self, srcdir, parent_config):
        mopack = os.path.join(srcdir, 'mopack.yml')
        if os.path.exists(mopack):
            config = ChildConfig([mopack], parent=parent_config)
            if self.builder is None:
                if not hasattr(self, 'submodules'):
                    self.submodules = submodules_type('submodules',
                                                      config.submodules)
                usage = self.pending_usage or config.usage
                self.builder = make_builder(
                    self.name, config.build, usage=usage,
                    submodules=self.submodules
                )
                del self.pending_usage
            return config
        return None

    def clean_post(self, pkgdir, new_package):
        if self == new_package:
            return False

        log.pkg_clean(self.name)
        self.builder.clean(pkgdir)
        return True

    def _resolve(self, pkgdir, srcdir, deploy_paths):
        log.pkg_resolve(self.name)
        self.builder.build(pkgdir, srcdir, deploy_paths)

    def deploy(self, pkgdir):
        log.pkg_deploy(self.name)
        self.builder.deploy(pkgdir)


class DirectoryPackage(SDistPackage):
    source = 'directory'

    def __init__(self, name, *, path, **kwargs):
        super().__init__(name, **kwargs)
        self.path = types.any_path(self.config_dir)('path', path)

    def fetch(self, pkgdir, parent_config):
        log.pkg_fetch(self.name, 'from {}'.format(self.source))
        return self._find_mopack(self.path, parent_config)

    def resolve(self, pkgdir, deploy_paths):
        return self._resolve(pkgdir, self.path, deploy_paths)

    def _get_usage(self, pkgdir, submodules):
        return self.builder.get_usage(pkgdir, submodules, self.path)


class TarballPackage(SDistPackage):
    source = 'tarball'
    _skip_compare_fields = (SDistPackage._skip_compare_fields +
                            ('guessed_srcdir',))

    def __init__(self, name, *, url=None, path=None, files=None, srcdir=None,
                 patch=None, **kwargs):
        super().__init__(name, **kwargs)

        if (url is None) == (path is None):
            raise TypeError('exactly one of `url` or `path` must be specified')
        self.url = url
        self.path = types.maybe(types.any_path(self.config_dir))('path', path)
        self.files = types.list_of(types.string, listify=True)('files', files)
        self.srcdir = types.maybe(types.inner_path)('srcdir', srcdir)
        self.patch = types.maybe(types.any_path(self.config_dir))(
            'patch', patch
        )
        self.guessed_srcdir = None  # Set in fetch().

    def _base_srcdir(self, pkgdir):
        return os.path.join(pkgdir, 'src', self.name)

    def _srcdir(self, pkgdir):
        return os.path.join(self._base_srcdir(pkgdir),
                            self.srcdir or self.guessed_srcdir)

    def _urlopen(self, url):
        with urlopen(url) as f:
            return BytesIO(f.read())

    def clean_pre(self, pkgdir, new_package):
        if self.equal(new_package, skip_fields=('builder',)):
            # Since both package objects have the same configuration, pass the
            # guessed srcdir on to the new package instance. That way, we don't
            # have to re-extract the tarball to get the guessed srcdir.
            new_package.guessed_srcdir = self.guessed_srcdir
            return False

        log.pkg_clean(self.name, 'sources')
        shutil.rmtree(self._base_srcdir(pkgdir), ignore_errors=True)
        return True

    def fetch(self, pkgdir, parent_config):
        base_srcdir = self._base_srcdir(pkgdir)
        if os.path.exists(base_srcdir):
            log.pkg_fetch(self.name, 'already fetched')
        else:
            where = self.url or self.path
            log.pkg_fetch(self.name, 'from {}'.format(where))

            with (self._urlopen(self.url) if self.url else
                  open(self.path, 'rb')) as f:
                with archive.open(f) as arc:
                    names = arc.getnames()
                    self.guessed_srcdir = (names[0].split('/', 1)[0] if names
                                           else None)
                    if self.files:
                        for i in filter_glob(self.files, names):
                            arc.extract(i, base_srcdir)
                    else:
                        arc.extractall(base_srcdir)

            if self.patch:
                log.pkg_patch(self.name, 'with {}'.format(self.patch))
                with LogFile.open(pkgdir, self.name + '-patch') as logfile, \
                     open(self.patch) as f, \
                     pushd(self._srcdir(pkgdir)):  # noqa
                    logfile.check_call(['patch', '-p1'], stdin=f)

        return self._find_mopack(self.srcdir or self.guessed_srcdir,
                                 parent_config)

    def resolve(self, pkgdir, deploy_paths):
        return self._resolve(pkgdir, self._srcdir(pkgdir), deploy_paths)

    def _get_usage(self, pkgdir, submodules):
        return self.builder.get_usage(pkgdir, submodules, self._srcdir(pkgdir))
