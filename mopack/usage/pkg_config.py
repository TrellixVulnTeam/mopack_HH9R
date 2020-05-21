import os

from . import Usage
from .. import types


class PkgConfigUsage(Usage):
    type = 'pkg-config'

    def __init__(self, name, *, path='pkgconfig'):
        self.path = types.inner_path('path', path)

    def get_usage(self, srcdir, builddir):
        if builddir is None:
            # XXX: It would probably be better to do this during construction.
            raise ValueError('unable to use `pkg-config` usage with ' +
                             'this package type; try `system` usage')

        path = os.path.abspath(os.path.join(builddir, self.path))
        return self._usage(path=path)
