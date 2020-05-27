import ntpath
import posixpath
from unittest import mock, TestCase

from mopack.types import *


class TestMaybe(TestCase):
    def test_basic(self):
        self.assertEqual(maybe(string)('field', None), None)
        self.assertEqual(maybe(string)('field', 'foo'), 'foo')

    def test_default(self):
        self.assertEqual(maybe(string, 'default')('field', None), 'default')
        self.assertEqual(maybe(string, 'default')('field', 'foo'), 'foo')

    def test_invalid(self):
        self.assertRaises(FieldError, maybe(string), 'field', 1)


class TestDefault(TestCase):
    def test_basic(self):
        self.assertEqual(default(string)('field', Unset), None)
        self.assertEqual(default(string)('field', 'foo'), 'foo')

    def test_default(self):
        self.assertEqual(default(string, 'default')('field', Unset), 'default')
        self.assertEqual(default(string, 'default')('field', 'foo'), 'foo')

    def test_invalid(self):
        self.assertRaises(FieldError, default(string), 'field', 1)


class TestOneOf(TestCase):
    def setUp(self):
        self.one_of = one_of(string, boolean, desc='str or bool')

    def test_valid(self):
        self.assertEqual(self.one_of('field', 'foo'), 'foo')
        self.assertEqual(self.one_of('field', True), True)

    def test_invalid(self):
        self.assertRaises(FieldError, self.one_of, 'field', 1)


class TestConstant(TestCase):
    def setUp(self):
        self.constant = constant('foo', 'bar')

    def test_valid(self):
        self.assertEqual(self.constant('field', 'foo'), 'foo')
        self.assertEqual(self.constant('field', 'bar'), 'bar')

    def test_invalid(self):
        self.assertRaises(FieldError, self.constant, 'field', 'baz')
        self.assertRaises(FieldError, self.constant, 'field', None)


class TestListOf(TestCase):
    def test_list(self):
        checker = list_of(string)
        self.assertEqual(checker('field', []), [])
        self.assertEqual(checker('field', ['foo']), ['foo'])
        self.assertEqual(checker('field', ['foo', 'bar']), ['foo', 'bar'])

    def test_listify(self):
        checker = list_of(string, listify=True)
        self.assertEqual(checker('field', []), [])
        self.assertEqual(checker('field', ['foo']), ['foo'])
        self.assertEqual(checker('field', ['foo', 'bar']), ['foo', 'bar'])
        self.assertEqual(checker('field', None), [])
        self.assertEqual(checker('field', 'foo'), ['foo'])

    def test_invalid(self):
        self.assertRaises(FieldError, list_of(string), 'field', None)
        self.assertRaises(FieldError, list_of(string), 'field', 'foo')
        self.assertRaises(FieldError, list_of(string), 'field', {})


class TestDictShape(TestCase):
    def setUp(self):
        self.dict_shape = dict_shape({'foo': string}, 'foo dict')

    def test_valid(self):
        self.assertEqual(self.dict_shape('field', {'foo': 'bar'}),
                         {'foo': 'bar'})

    def test_invalid_keys(self):
        self.assertRaises(FieldError, self.dict_shape, 'field', {})
        self.assertRaises(FieldError, self.dict_shape, 'field', {'bar': 'b'})
        self.assertRaises(FieldError, self.dict_shape, 'field',
                          {'foo': 'f', 'bar': 'b'})

    def test_invalid_values(self):
        self.assertRaises(FieldError, self.dict_shape, 'field', {'foo': 1})


class TestString(TestCase):
    def test_valid(self):
        self.assertEqual(string('field', 'foo'), 'foo')
        self.assertEqual(string('field', 'bar'), 'bar')

    def test_invalid(self):
        self.assertRaises(FieldError, string, 'field', 1)
        self.assertRaises(FieldError, string, 'field', None)


class TestBoolean(TestCase):
    def test_valid(self):
        self.assertEqual(boolean('field', True), True)
        self.assertEqual(boolean('field', False), False)

    def test_invalid(self):
        self.assertRaises(FieldError, boolean, 'field', 1)
        self.assertRaises(FieldError, boolean, 'field', None)


class TestInnerPath(TestCase):
    def test_valid(self):
        self.assertEqual(inner_path('field', 'path'), 'path')
        self.assertEqual(inner_path('field', 'path/..'), '.')
        self.assertEqual(inner_path('field', 'foo/../bar'), 'bar')

    def test_outer(self):
        self.assertRaises(FieldError, inner_path, 'field', '../path')
        self.assertRaises(FieldError, inner_path, 'field', 'path/../..')

    def test_absolute_posix(self):
        with mock.patch('os.path', posixpath):
            self.assertRaises(FieldError, inner_path, 'field', '/path')

    def test_absolute_nt(self):
        with mock.patch('os.path', ntpath):
            self.assertRaises(FieldError, inner_path, 'field', '/path')
            self.assertRaises(FieldError, inner_path, 'field', 'C:path')
            self.assertRaises(FieldError, inner_path, 'field', 'C:\\path')
            self.assertRaises(FieldError, inner_path, 'field', 'C:')


class TestAbsOrInnerPath(TestCase):
    def test_inner(self):
        self.assertEqual(abs_or_inner_path('field', 'path'), 'path')
        self.assertEqual(abs_or_inner_path('field', 'path/..'), '.')
        self.assertEqual(abs_or_inner_path('field', 'foo/../bar'), 'bar')

    def test_outer(self):
        self.assertRaises(FieldError, abs_or_inner_path, 'field', '../path')
        self.assertRaises(FieldError, abs_or_inner_path, 'field', 'path/../..')

    def test_absolute_posix(self):
        with mock.patch('os.path', posixpath):
            self.assertEqual(abs_or_inner_path('field', '/path'), '/path')

    def test_absolute_nt(self):
        with mock.patch('os.path', ntpath):
            self.assertEqual(abs_or_inner_path('field', '/path'), '\\path')
            self.assertEqual(abs_or_inner_path('field', 'C:\\path'),
                             'C:\\path')
            self.assertEqual(abs_or_inner_path('field', 'C:'), 'C:')
            self.assertRaises(FieldError, inner_path, 'field', 'C:path')


class TestAnyPath(TestCase):
    def test_relative(self):
        self.assertEqual(any_path()('field', 'path'), 'path')
        self.assertEqual(any_path()('field', '../path'), '../path')
        self.assertEqual(any_path()('field', 'foo/../bar'), 'bar')
        self.assertEqual(any_path('/base')('field', 'path'), '/base/path')

    def test_absolute(self):
        self.assertEqual(any_path()('field', '/path'), '/path')
        self.assertEqual(any_path('/base')('field', '/path'), '/path')


class TestShellArgs(TestCase):
    def test_single(self):
        self.assertEqual(shell_args()('field', 'foo'), ['foo'])

    def test_multiple(self):
        self.assertEqual(shell_args()('field', 'foo bar baz'),
                         ['foo', 'bar', 'baz'])

    def test_quote(self):
        self.assertEqual(shell_args()('field', 'foo "bar baz"'),
                         ['foo', 'bar baz'])
        self.assertEqual(shell_args()('field', 'foo"bar baz"'), ['foobar baz'])

    def test_type(self):
        self.assertEqual(shell_args(type=tuple)('field', 'foo bar baz'),
                         ('foo', 'bar', 'baz'))

    def test_escapes(self):
        self.assertEqual(shell_args()('field', 'foo\\ bar'), ['foo\\', 'bar'])
        self.assertEqual(shell_args(escapes=True)('field', 'foo\\ bar'),
                         ['foo bar'])

    def test_invalid(self):
        self.assertRaises(FieldError, shell_args(), 'field', 1)
