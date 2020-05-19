from unittest import TestCase

from mopack import iterutils


class TestIsIterable(TestCase):
    def test_list(self):
        self.assertTrue(iterutils.isiterable([]))

    def test_dict(self):
        self.assertFalse(iterutils.isiterable({}))

    def test_generator(self):
        gen = (i for i in range(10))
        self.assertTrue(iterutils.isiterable(gen))

    def test_string(self):
        self.assertFalse(iterutils.isiterable('foo'))

    def test_none(self):
        self.assertFalse(iterutils.isiterable(None))


class TestIsMapping(TestCase):
    def test_list(self):
        self.assertFalse(iterutils.ismapping([]))

    def test_dict(self):
        self.assertTrue(iterutils.ismapping({}))

    def test_string(self):
        self.assertFalse(iterutils.ismapping('foo'))

    def test_none(self):
        self.assertFalse(iterutils.ismapping(None))


class TestIterate(TestCase):
    def test_none(self):
        self.assertEqual(list(iterutils.iterate(None)), [])

    def test_one(self):
        self.assertEqual(list(iterutils.iterate('foo')), ['foo'])

    def test_many(self):
        self.assertEqual(list(iterutils.iterate(['foo', 'bar'])),
                         ['foo', 'bar'])


class TestListify(TestCase):
    def test_none(self):
        self.assertEqual(iterutils.listify(None), [])

    def test_one(self):
        self.assertEqual(iterutils.listify('foo'), ['foo'])

    def test_many(self):
        x = ['foo', 'bar']
        res = iterutils.listify(x)
        self.assertEqual(res, x)
        self.assertTrue(x is res)

    def test_always_copy(self):
        x = ['foo', 'bar']
        res = iterutils.listify(x, always_copy=True)
        self.assertEqual(res, x)
        self.assertTrue(x is not res)

    def test_no_scalar(self):
        self.assertEqual(iterutils.listify(['foo'], scalar_ok=False), ['foo'])
        self.assertEqual(iterutils.listify(['foo'], always_copy=True,
                                           scalar_ok=False), ['foo'])
        self.assertRaises(TypeError, iterutils.listify, 1, scalar_ok=False)
        self.assertRaises(TypeError, iterutils.listify, 'foo', scalar_ok=False)

    def test_type(self):
        x = 'foo'
        res = iterutils.listify(x, type=tuple)
        self.assertEqual(res, ('foo',))

        y = ['foo', 'bar']
        res = iterutils.listify(y, type=tuple)
        self.assertEqual(res, ('foo', 'bar'))


class TestMergeIntoDict(TestCase):
    def test_merge_empty(self):
        d = {}
        iterutils.merge_into_dict(d, {})
        self.assertEqual(d, {})

        d = {}
        iterutils.merge_into_dict(d, {'foo': 1})
        self.assertEqual(d, {'foo': 1})

        d = {'foo': 1}
        iterutils.merge_into_dict(d, {})
        self.assertEqual(d, {'foo': 1})

    def test_merge(self):
        d = {'foo': 1}
        iterutils.merge_into_dict(d, {'bar': 2})
        self.assertEqual(d, {'foo': 1, 'bar': 2})

        d = {'foo': 1}
        iterutils.merge_into_dict(d, {'foo': 2})
        self.assertEqual(d, {'foo': 2})

    def test_merge_several(self):
        d = {'foo': 1}
        iterutils.merge_into_dict(d, {'bar': 2}, {'baz': 3})
        self.assertEqual(d, {'foo': 1, 'bar': 2, 'baz': 3})

        d = {'foo': 1}
        iterutils.merge_into_dict(d, {'foo': 2}, {'foo': 3})
        self.assertEqual(d, {'foo': 3})

    def test_merge_lists(self):
        d = {'foo': [1]}
        iterutils.merge_into_dict(d, {'foo': [2]})
        self.assertEqual(d, {'foo': [1, 2]})


class TestMergeDicts(TestCase):
    def test_merge_empty(self):
        self.assertEqual(iterutils.merge_dicts({}, {}), {})
        self.assertEqual(iterutils.merge_dicts({}, {'foo': 1}), {'foo': 1})
        self.assertEqual(iterutils.merge_dicts({'foo': 1}, {}), {'foo': 1})

    def test_merge_none(self):
        self.assertEqual(iterutils.merge_dicts({'foo': None}, {'foo': 1}),
                         {'foo': 1})
        self.assertEqual(iterutils.merge_dicts({'foo': 1}, {'foo': None}),
                         {'foo': 1})

        self.assertEqual(iterutils.merge_dicts({'foo': None}, {'bar': 1}),
                         {'foo': None, 'bar': 1})
        self.assertEqual(iterutils.merge_dicts({'foo': 1}, {'bar': None}),
                         {'foo': 1, 'bar': None})

    def test_merge_single(self):
        self.assertEqual(iterutils.merge_dicts({'foo': 1}, {'foo': 2}),
                         {'foo': 2})

    def test_merge_list(self):
        self.assertEqual(iterutils.merge_dicts({'foo': [1]}, {'foo': [2]}),
                         {'foo': [1, 2]})

    def test_merge_dict(self):
        self.assertEqual(iterutils.merge_dicts(
            {'foo': {'bar': [1], 'baz': 2}},
            {'foo': {'bar': [2], 'quux': 3}}
        ), {'foo': {'bar': [1, 2], 'baz': 2, 'quux': 3}})

    def test_merge_incompatible(self):
        merge_dicts = iterutils.merge_dicts
        self.assertRaises(TypeError, merge_dicts, {'foo': 1}, {'foo': [2]})
        self.assertRaises(TypeError, merge_dicts, {'foo': [1]}, {'foo': 2})
        self.assertRaises(TypeError, merge_dicts, {'foo': {}}, {'foo': 2})
        self.assertRaises(TypeError, merge_dicts, {'foo': 1}, {'foo': {}})

    def test_merge_several(self):
        merge_dicts = iterutils.merge_dicts
        self.assertEqual(merge_dicts({}, {}, {}), {})
        self.assertEqual(merge_dicts({'foo': 1}, {'bar': 2}, {'baz': 3}),
                         {'foo': 1, 'bar': 2, 'baz': 3})
        self.assertEqual(merge_dicts({'foo': 1}, {'foo': 2, 'bar': 3},
                                     {'baz': 4}),
                         {'foo': 2, 'bar': 3, 'baz': 4})

    def test_merge_makes_copies(self):
        d = {'foo': [1]}
        self.assertEqual(iterutils.merge_dicts({}, d, {'foo': [2]}),
                         {'foo': [1, 2]})
        self.assertEqual(d, {'foo': [1]})
