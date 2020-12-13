from unittest import TestCase

from mopack.objutils import *


class TestMemoize(TestCase):
    def test_memoize_0_args(self):
        i = 0

        @memoize
        def f():
            nonlocal i
            i += 1
            return i

        self.assertEqual(f(), 1)
        self.assertEqual(f(), 1)

    def test_memoize_1_arg(self):
        i = 0

        @memoize
        def f(j):
            nonlocal i
            i += 1
            return i + j

        self.assertEqual(f(0), 1)
        self.assertEqual(f(1), 3)
        self.assertEqual(f(0), 1)

    def test_memoize_reset(self):
        i = 0

        @memoize
        def f(j):
            nonlocal i
            i += 1
            return i + j

        self.assertEqual(f(0), 1)
        self.assertEqual(f(1), 3)
        f._reset()
        self.assertEqual(f(0), 3)
        self.assertEqual(f(1), 5)


class TestMemoizeMethod(TestCase):
    def test_memoize_0_args(self):
        class Foo:
            def __init__(self, i):
                self.i = i

            @memoize_method
            def fn(self):
                self.i += 1
                return self.i

        f = Foo(0)
        self.assertEqual(f.fn(), 1)
        self.assertEqual(f.fn(), 1)
        g = Foo(1)
        self.assertEqual(g.fn(), 2)
        self.assertEqual(g.fn(), 2)
        del g
        h = Foo(2)
        self.assertEqual(h.fn(), 3)
        self.assertEqual(h.fn(), 3)

    def test_memoize_1_arg(self):
        class Foo:
            def __init__(self, i):
                self.i = i

            @memoize_method
            def fn(self, j):
                self.i += 1
                return self.i + j

        f = Foo(0)
        self.assertEqual(f.fn(0), 1)
        self.assertEqual(f.fn(1), 3)
        self.assertEqual(f.fn(0), 1)
        g = Foo(1)
        self.assertEqual(g.fn(0), 2)
        self.assertEqual(g.fn(1), 4)
        self.assertEqual(g.fn(0), 2)
        del g
        h = Foo(2)
        self.assertEqual(h.fn(0), 3)
        self.assertEqual(h.fn(1), 5)
        self.assertEqual(h.fn(0), 3)

    def test_memoize_reset(self):
        class Foo:
            def __init__(self, i):
                self.i = i

            @memoize_method
            def fn(self, j):
                self.i += 1
                return self.i + j

        f = Foo(0)
        Foo.fn._reset(f)

        self.assertEqual(f.fn(0), 1)
        self.assertEqual(f.fn(1), 3)
        self.assertEqual(f.fn(0), 1)
        g = Foo(1)
        self.assertEqual(g.fn(0), 2)
        self.assertEqual(g.fn(1), 4)
        self.assertEqual(g.fn(0), 2)

        Foo.fn._reset(f)
        self.assertEqual(f.fn(0), 3)
        self.assertEqual(f.fn(1), 5)
        self.assertEqual(f.fn(0), 3)

        self.assertEqual(g.fn(0), 2)
        self.assertEqual(g.fn(1), 4)
        self.assertEqual(g.fn(0), 2)
