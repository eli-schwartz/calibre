# vim:fileencoding=utf-8
import sys
import unittest
from contextlib import contextmanager

import calibre.utils.icu as icu


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'




@contextmanager
def make_collation_func(name, locale, numeric=True, template='_sort_key_template', func='strcmp'):
    c = icu._icu.Collator(locale)
    cname = '%s_test_collator%s' % (name, template)
    setattr(icu, cname, c)
    c.numeric = numeric
    yield icu._make_func(getattr(icu, template), name, collator=cname, collator_func='not_used_xxx', func=func)
    delattr(icu, cname)


class TestICU(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def setUp(self):
        icu.change_locale('en')

    def test_sorting(self):
        ' Test the various sorting APIs '
        german = '''Sonntag Montag Dienstag Januar Februar März Fuße Fluße Flusse flusse fluße flüße flüsse'''.split()
        german_good = '''Dienstag Februar flusse Flusse fluße Fluße flüsse flüße Fuße Januar März Montag Sonntag'''.split()
        french = '''dimanche lundi mardi janvier février mars déjà Meme deja même dejà bpef bœg Boef Mémé bœf boef bnef pêche pèché pêché pêche pêché'''.split()
        french_good = '''bnef boef Boef bœf bœg bpef deja dejà déjà dimanche février janvier lundi mardi mars Meme Mémé même pèché pêche pêche pêché pêché'''.split()  # noqa

        # Test corner cases
        sort_key = icu.sort_key
        s = '\\U0001f431'
        self.ae(sort_key(s), sort_key(s.encode(sys.getdefaultencoding())), 'UTF-8 encoded object not correctly decoded to generate sort key')
        self.ae(s.encode('utf-16'), s.encode('utf-16'), 'Undecodable bytestring not returned as itself')
        self.ae(b'', sort_key(None))
        self.ae(0, icu.strcmp(None, b''))
        self.ae(0, icu.strcmp(s, s.encode(sys.getdefaultencoding())))

        # Test locales
        with make_collation_func('dsk', 'de', func='sort_key') as dsk:
            self.ae(german_good, sorted(german, key=dsk))
            with make_collation_func('dcmp', 'de', template='_strcmp_template') as dcmp:
                for x in german:
                    for y in german:
                        self.ae(cmp(dsk(x), dsk(y)), dcmp(x, y))

        with make_collation_func('fsk', 'fr', func='sort_key') as fsk:
            self.ae(french_good, sorted(french, key=fsk))
            with make_collation_func('fcmp', 'fr', template='_strcmp_template') as fcmp:
                for x in french:
                    for y in french:
                        self.ae(cmp(fsk(x), fsk(y)), fcmp(x, y))

        with make_collation_func('ssk', 'es', func='sort_key') as ssk:
            self.assertNotEqual(ssk('peña'), ssk('pena'))
            with make_collation_func('scmp', 'es', template='_strcmp_template') as scmp:
                self.assertNotEqual(0, scmp('pena', 'peña'))

        for k, v in {'pèché': 'peche', 'flüße':'Flusse', 'Štepánek':'ŠtepaneK'}.items():
            self.ae(0, icu.primary_strcmp(k, v))

        # Test different types of collation
        self.ae(icu.primary_sort_key('Aä'), icu.primary_sort_key('aa'))
        self.assertLess(icu.numeric_sort_key('something 2'), icu.numeric_sort_key('something 11'))
        self.assertLess(icu.case_sensitive_sort_key('A'), icu.case_sensitive_sort_key('a'))
        self.ae(0, icu.strcmp('a', 'A'))
        self.ae(cmp('a', 'A'), icu.case_sensitive_strcmp('a', 'A'))
        self.ae(0, icu.primary_strcmp('ä', 'A'))

    def test_change_case(self):
        ' Test the various ways of changing the case '
        from calibre.utils.titlecase import titlecase
        # Test corner cases
        self.ae('A', icu.upper(b'a'))
        for x in ('', None, False, 1):
            self.ae(x, icu.capitalize(x))

        for x in ('a', 'Alice\'s code', 'macdonald\'s machIne', '02 the wars'):
            self.ae(icu.upper(x), x.upper())
            self.ae(icu.lower(x), x.lower())
            # ICU's title case algorithm is different from ours, when there are
            # capitals inside words
            self.ae(icu.title_case(x), titlecase(x).replace('machIne', 'Machine'))
            self.ae(icu.capitalize(x), x[0].upper() + x[1:].lower())
            self.ae(icu.swapcase(x), x.swapcase())

    def test_find(self):
        ' Test searching for substrings '
        self.ae((1, 1), icu.find(b'a', b'1ab'))
        self.ae((1, 1 if sys.maxunicode >= 0x10ffff else 2), icu.find('\\U0001f431', 'x\\U0001f431x'))
        self.ae((1 if sys.maxunicode >= 0x10ffff else 2, 1), icu.find('y', '\\U0001f431y'))
        self.ae((0, 4), icu.primary_find('pena', 'peña'))
        for k, v in {'pèché': 'peche', 'flüße':'Flusse', 'Štepánek':'ŠtepaneK'}.items():
            self.ae((1, len(k)), icu.primary_find(v, ' ' + k), 'Failed to find %s in %s' % (v, k))
        self.assertTrue(icu.startswith(b'abc', b'ab'))
        self.assertTrue(icu.startswith('abc', 'abc'))
        self.assertFalse(icu.startswith('xyz', 'a'))
        self.assertTrue(icu.startswith('xxx', ''))
        self.assertTrue(icu.primary_startswith('pena', 'peña'))
        self.assertTrue(icu.contains('\\U0001f431', '\\U0001f431'))
        self.assertTrue(icu.contains('something', 'some other something else'))
        self.assertTrue(icu.contains('', 'a'))
        self.assertTrue(icu.contains('', ''))
        self.assertFalse(icu.contains('xxx', 'xx'))
        self.assertTrue(icu.primary_contains('pena', 'peña'))

    def test_collation_order(self):
        'Testing collation ordering'
        for group in [
            ('Šaa', 'Smith', 'Solženicyn', 'Štepánek'),
            ('01', '1'),
        ]:
            last = None
            for x in group:
                order, length = icu.numeric_collator().collation_order(x)
                if last is not None:
                    self.ae(last, order, 'Order for %s not correct: %s != %s' % (x, last, order))
                last = order

        self.ae(dict(icu.partition_by_first_letter(['A1', '', 'a1', '\\U0001f431', '\\U0001f431x'])),
                {' ':[''], 'A':['A1', 'a1'], '\\U0001f431':['\\U0001f431', '\\U0001f431x']})

    def test_roundtrip(self):
        ' Test roundtripping '
        for r in ('xxx\0\\u2219\\U0001f431xxx', '\0', '', 'simple'):
            self.ae(r, icu._icu.roundtrip(r))
        for x, l in [('', 0), ('a', 1), ('\\U0001f431', 1)]:
            self.ae(icu._icu.string_length(x), l)
        for x, l in [('', 0), ('a', 1), ('\\U0001f431', 2)]:
            self.ae(icu._icu.utf16_length(x), l)
        self.ae(icu._icu.chr(0x1f431), '\\U0001f431')
        self.ae(icu._icu.ord_string('abc'*100), tuple(map(ord, 'abc'*100)))
        self.ae(icu._icu.ord_string('\\U0001f431'), (0x1f431,))

    def test_character_name(self):
        ' Test character naming '
        self.ae(icu.character_name('\\U0001f431'), 'CAT FACE')

    def test_contractions(self):
        ' Test contractions '
        self.skipTest('Skipping as this depends too much on ICU version')
        c = icu._icu.Collator('cs')
        self.ae(icu.contractions(c), frozenset({'Z\\u030c', 'z\\u030c', 'Ch',
            'C\\u030c', 'ch', 'cH', 'c\\u030c', 's\\u030c', 'r\\u030c', 'CH',
            'S\\u030c', 'R\\u030c'}))


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestICU)


class TestRunner(unittest.main):

    def createTests(self):
        self.test = find_tests()


def run(verbosity=4):
    TestRunner(verbosity=verbosity, exit=False)


def test_build():
    result = TestRunner(verbosity=0, buffer=True, catchbreak=True, failfast=True, argv=sys.argv[:1], exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)

if __name__ == '__main__':
    run(verbosity=4)
