#!/usr/bin/env  python2
# encoding: utf-8
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
A parser for search queries with a syntax very similar to that used by
the Google search engine.

For details on the search query syntax see :class:`SearchQueryParser`.
To use the parser, subclass :class:`SearchQueryParser` and implement the
methods :method:`SearchQueryParser.universal_set` and
:method:`SearchQueryParser.get_matches`. See for example :class:`Tester`.

If this module is run, it will perform a series of unit tests.
'''

import operator
import re
import sys
import weakref

from calibre import prints
from calibre.constants import preferred_encoding
from calibre.utils.icu import sort_key


'''
This class manages access to the preference holding the saved search queries.
It exists to ensure that unicode is used throughout, and also to permit
adding other fields, such as whether the search is a 'favorite'
'''


class SavedSearchQueries(object):
    queries = {}
    opt_name = ''

    def __init__(self, db, _opt_name):
        self.opt_name = _opt_name
        if db is not None:
            db = db.new_api
            self._db = weakref.ref(db)
            self.queries = db.pref(self.opt_name, {})
        else:
            self.queries = {}
            self._db = lambda : None

    @property
    def db(self):
        return self._db()

    def save_queries(self):
        db = self.db
        if db is not None:
            db.set_pref(self.opt_name, self.queries)

    def force_unicode(self, x):
        if not isinstance(x, str):
            x = x.decode(preferred_encoding, 'replace')
        return x

    def add(self, name, value):
        self.queries[self.force_unicode(name)] = self.force_unicode(value).strip()
        self.save_queries()

    def lookup(self, name):
        return self.queries.get(self.force_unicode(name), None)

    def delete(self, name):
        self.queries.pop(self.force_unicode(name), False)
        self.save_queries()

    def rename(self, old_name, new_name):
        self.queries[self.force_unicode(new_name)] = \
                    self.queries.get(self.force_unicode(old_name), None)
        self.queries.pop(self.force_unicode(old_name), False)
        self.save_queries()

    def set_all(self, smap):
        self.queries = smap
        self.save_queries()

    def names(self):
        return sorted(list(self.queries.keys()),key=sort_key)


'''
Create a global instance of the saved searches. It is global so that the searches
are common across all instances of the parser (devices, library, etc).
'''
ss = SavedSearchQueries(None, None)


def set_saved_searches(db, opt_name):
    global ss
    ss = SavedSearchQueries(db, opt_name)


def saved_searches():
    global ss
    return ss


def global_lookup_saved_search(name):
    return ss.lookup(name)


'''
Parse a search expression into a series of potentially recursive operations.

Note that the interpreter wants binary operators, not n-ary ops. This is why we
recurse instead of iterating when building sequences of the same op.

The syntax is more than a bit twisted. In particular, the handling of colons
in the base token requires semantic analysis.

Also note that the query string is lowercased before analysis. This is OK because
calibre's searches are all case-insensitive.

Grammar:

prog ::= or_expression

or_expression ::= and_expression [ 'or' or_expression ]

and_expression ::= not_expression [ [ 'and' ] and_expression ]

not_expression ::= [ 'not' ] location_expression

location_expression ::= base_token | ( '(' or_expression ')' )

base_token ::= a sequence of letters and colons, perhaps quoted
'''


class Parser(object):

    def __init__(self):
        self.current_token = 0
        self.tokens = None

    OPCODE = 1
    WORD = 2
    QUOTED_WORD = 3
    EOF = 4

    # Had to translate named constants to numeric values
    lex_scanner = re.Scanner([
            (r'[()]', lambda x,t: (1, t)),
            (r'@.+?:[^")\s]+', lambda x,t: (2, str(t))),
            (r'[^"()\s]+', lambda x,t: (2, str(t))),
            (r'".*?((?<!\\)")', lambda x,t: (3, t[1:-1])),
            (r'\s+',              None)
    ], flags=re.DOTALL)

    def token(self, advance=False):
        if self.is_eof():
            return None
        res = self.tokens[self.current_token][1]
        if advance:
            self.current_token += 1
        return res

    def lcase_token(self, advance=False):
        if self.is_eof():
            return None
        res = self.tokens[self.current_token][1]
        if advance:
            self.current_token += 1
        return icu_lower(res)

    def token_type(self):
        if self.is_eof():
            return self.EOF
        return self.tokens[self.current_token][0]

    def is_eof(self):
        return self.current_token >= len(self.tokens)

    def advance(self):
        self.current_token += 1

    def parse(self, expr, locations):
        self.locations = locations

        # Strip out escaped backslashes, quotes and parens so that the
        # lex scanner doesn't get confused. We put them back later.
        expr = expr.replace('\\\\', '\x01').replace('\\"', '\x02')
        expr = expr.replace('\\(', '\x03').replace('\\)', '\x04')
        self.tokens = self.lex_scanner.scan(expr)[0]
        for (i,tok) in enumerate(self.tokens):
            tt, tv = tok
            if tt == self.WORD or tt == self.QUOTED_WORD:
                self.tokens[i] = (tt,
                    tv.replace('\x01', '\\').replace('\x02', '"').
                    replace('\x03', '(').replace('\x04', ')'))

        self.current_token = 0
        prog = self.or_expression()
        if not self.is_eof():
            raise ParseException(_('Extra characters at end of search'))
        # prints(self.tokens, '\n', prog)
        return prog

    def or_expression(self):
        lhs = self.and_expression()
        if self.lcase_token() == 'or':
            self.advance()
            return ['or', lhs, self.or_expression()]
        return lhs

    def and_expression(self):
        lhs = self.not_expression()
        if self.lcase_token() == 'and':
            self.advance()
            return ['and', lhs, self.and_expression()]

        # Account for the optional 'and'
        if (self.token_type() in [self.WORD, self.QUOTED_WORD] and
                        self.lcase_token() != 'or'):
            return ['and', lhs, self.and_expression()]
        return lhs

    def not_expression(self):
        if self.lcase_token() == 'not':
            self.advance()
            return ['not', self.not_expression()]
        return self.location_expression()

    def location_expression(self):
        if self.token_type() == self.OPCODE and self.token() == '(':
            self.advance()
            res = self.or_expression()
            if self.token_type() != self.OPCODE or self.token(advance=True) != ')':
                raise ParseException(_('missing )'))
            return res
        if self.token_type() not in (self.WORD, self.QUOTED_WORD):
            raise ParseException(_('Invalid syntax. Expected a lookup name or a word'))

        return self.base_token()

    def base_token(self):
        if self.token_type() == self.QUOTED_WORD:
            return ['token', 'all', self.token(advance=True)]

        words = self.token(advance=True).split(':')

        # The complexity here comes from having colon-separated search
        # values. That forces us to check that the first "word" in a colon-
        # separated group is a valid location. If not, then the token must
        # be reconstructed. We also have the problem that locations can be
        # followed by quoted strings that appear as the next token. and that
        # tokens can be a sequence of colons.

        # We have a location if there is more than one word and the first
        # word is in locations. This check could produce a "wrong" answer if
        # the search string is something like 'author: "foo"' because it
        # will be interpreted as 'author:"foo"'. I am choosing to accept the
        # possible error. The expression should be written '"author:" foo'
        if len(words) > 1 and words[0].lower() in self.locations:
            loc = words[0].lower()
            words = words[1:]
            if len(words) == 1 and self.token_type() == self.QUOTED_WORD:
                return ['token', loc, self.token(advance=True)]
            return ['token', icu_lower(loc), ':'.join(words)]

        return ['token', 'all', ':'.join(words)]


class ParseException(Exception):

    @property
    def msg(self):
        if len(self.args) > 0:
            return self.args[0]
        return ""


class SearchQueryParser(object):
    '''
    Parses a search query.

    A search query consists of tokens. The tokens can be combined using
    the `or`, `and` and `not` operators as well as grouped using parentheses.
    When no operator is specified between two tokens, `and` is assumed.

    Each token is a string of the form `location:query`. `location` is a string
    from :member:`DEFAULT_LOCATIONS`. It is optional. If it is omitted, it is assumed to
    be `all`. `query` is an arbitrary string that must not contain parentheses.
    If it contains whitespace, it should be quoted by enclosing it in `"` marks.

    Examples::

      * `Asimov` [search for the string "Asimov" in location `all`]
      * `comments:"This is a good book"` [search for "This is a good book" in `comments`]
      * `author:Asimov tag:unread` [search for books by Asimov that have been tagged as unread]
      * `author:Asimov or author:Hardy` [search for books by Asimov or Hardy]
      * `(author:Asimov or author:Hardy) and not tag:read` [search for unread books by Asimov or Hardy]
    '''

    @staticmethod
    def run_tests(parser, result, tests):
        failed = []
        for test in tests:
            prints('\tTesting:', test[0], end=' ')
            res = parser.parseString(test[0])
            if list(res.get(result, None)) == test[1]:
                print('OK')
            else:
                print('FAILED:', 'Expected:', test[1], 'Got:', list(res.get(result, None)))
                failed.append(test[0])
        return failed

    def __init__(self, locations, test=False, optimize=False, lookup_saved_search=None, parse_cache=None):
        self.sqp_initialize(locations, test=test, optimize=optimize)
        self.parser = Parser()
        self.lookup_saved_search = global_lookup_saved_search if lookup_saved_search is None else lookup_saved_search
        self.sqp_parse_cache = parse_cache

    def sqp_change_locations(self, locations):
        self.sqp_initialize(locations, optimize=self.optimize)
        if self.sqp_parse_cache is not None:
            self.sqp_parse_cache.clear()

    def sqp_initialize(self, locations, test=False, optimize=False):
        self.locations = locations
        self._tests_failed = False
        self.optimize = optimize

    def parse(self, query, candidates=None):
        # empty the list of searches used for recursion testing
        self.recurse_level = 0
        self.searches_seen = set([])
        candidates = self.universal_set()
        return self._parse(query, candidates=candidates)

    # this parse is used internally because it doesn't clear the
    # recursive search test list. However, we permit seeing the
    # same search a few times because the search might appear within
    # another search.
    def _parse(self, query, candidates=None):
        self.recurse_level += 1
        try:
            res = self.sqp_parse_cache.get(query, None)
        except AttributeError:
            res = None
        if res is None:
            try:
                res = self.parser.parse(query, self.locations)
            except RuntimeError:
                raise ParseException(_('Failed to parse query, recursion limit reached: %s')%repr(query))
            if self.sqp_parse_cache is not None:
                self.sqp_parse_cache[query] = res
        if candidates is None:
            candidates = self.universal_set()
        t = self.evaluate(res, candidates)
        self.recurse_level -= 1
        return t

    def method(self, group_name):
        return getattr(self, 'evaluate_'+group_name)

    def evaluate(self, parse_result, candidates):
        return self.method(parse_result[0])(parse_result[1:], candidates)

    def evaluate_and(self, argument, candidates):
        # RHS checks only those items matched by LHS
        # returns result of RHS check: RHmatches(LHmatches(c))
        #  return self.evaluate(argument[0]).intersection(self.evaluate(argument[1]))
        l = self.evaluate(argument[0], candidates)
        return l.intersection(self.evaluate(argument[1], l))

    def evaluate_or(self, argument, candidates):
        # RHS checks only those elements not matched by LHS
        # returns LHS union RHS: LHmatches(c) + RHmatches(c-LHmatches(c))
        #  return self.evaluate(argument[0]).union(self.evaluate(argument[1]))
        l = self.evaluate(argument[0], candidates)
        return l.union(self.evaluate(argument[1], candidates.difference(l)))

    def evaluate_not(self, argument, candidates):
        # unary op checks only candidates. Result: list of items matching
        # returns: c - matches(c)
        #  return self.universal_set().difference(self.evaluate(argument[0]))
        return candidates.difference(self.evaluate(argument[0], candidates))

#     def evaluate_parenthesis(self, argument, candidates):
#         return self.evaluate(argument[0], candidates)

    def evaluate_token(self, argument, candidates):
        location = argument[0]
        query = argument[1]
        if location.lower() == 'search':
            if query.startswith('='):
                query = query[1:]
            try:
                if query in self.searches_seen:
                    raise ParseException(_('Recursive saved search: {0}').format(query))
                if self.recurse_level > 5:
                    self.searches_seen.add(query)
                ss = self.lookup_saved_search(query)
                if ss is None:
                    raise ParseException(_('Unknown saved search: {}').format(query))
                return self._parse(ss, candidates)
            except ParseException as e:
                raise e
            except:  # convert all exceptions (e.g., missing key) to a parse error
                import traceback
                traceback.print_exc()
                raise ParseException(_('Unknown error in saved search: {0}').format(query))
        return self._get_matches(location, query, candidates)

    def _get_matches(self, location, query, candidates):
        if self.optimize:
            return self.get_matches(location, query, candidates=candidates)
        else:
            return self.get_matches(location, query)

    def get_matches(self, location, query, candidates=None):
        '''
        Should return the set of matches for :param:'location` and :param:`query`.

        The search must be performed over all entries if :param:`candidates` is
        None otherwise only over the items in candidates.

        :param:`location` is one of the items in :member:`SearchQueryParser.DEFAULT_LOCATIONS`.
        :param:`query` is a string literal.
        :return: None or a subset of the set returned by :meth:`universal_set`.
        '''
        return set([])

    def universal_set(self):
        '''
        Should return the set of all matches.
        '''
        return set([])

# Testing {{{


class Tester(SearchQueryParser):

    texts = {
 1: ['Eugenie Grandet', 'Honor\xe9 de Balzac', 'manybooks.net', 'lrf'],
 2: ['Fanny Hill', 'John Cleland', 'manybooks.net', 'lrf'],
 3: ['Persuasion', 'Jane Austen', 'manybooks.net', 'lrf'],
 4: ['Psmith, Journalist', 'P. G. Wodehouse', 'Some Publisher', 'lrf'],
 5: ['The Complete Works of William Shakespeare',
     'William Shakespeare',
     'manybooks.net',
     'lrf'],
 6: ['The History of England, Volume I',
     'David Hume',
     'manybooks.net',
     'lrf'],
 7: ['Someone Comes to Town, Someone Leaves Town',
     'Cory Doctorow',
     'Tor Books',
     'lrf'],
 8: ['Stalky and Co.', 'Rudyard Kipling', 'manybooks.net', 'lrf'],
 9: ['A Game of Thrones', 'George R. R. Martin', None, 'lrf,rar'],
 10: ['A Clash of Kings', 'George R. R. Martin', None, 'lrf,rar'],
 11: ['A Storm of Swords', 'George R. R. Martin', None, 'lrf,rar'],
 12: ['Biggles - Pioneer Air Fighter', 'W. E. Johns', None, 'lrf,rtf'],
 13: ['Biggles of the Camel Squadron',
      'W. E. Johns',
      'London:Thames, (1977)',
      'lrf,rtf'],
 14: ['A Feast for Crows', 'George R. R. Martin', None, 'lrf,rar'],
 15: ['Cryptonomicon', 'Neal Stephenson', None, 'lrf,rar'],
 16: ['Quicksilver', 'Neal Stephenson', None, 'lrf,zip'],
 17: ['The Comedies of William Shakespeare',
      'William Shakespeare',
      None,
      'lrf'],
 18: ['The Histories of William Shakespeare',
      'William Shakespeare',
      None,
      'lrf'],
 19: ['The Tragedies of William Shakespeare',
      'William Shakespeare',
      None,
      'lrf'],
 20: ['An Ideal Husband', 'Oscar Wilde', 'manybooks.net', 'lrf'],
 21: ['Flight of the Nighthawks', 'Raymond E. Feist', None, 'lrf,rar'],
 22: ['Into a Dark Realm', 'Raymond E. Feist', None, 'lrf,rar'],
 23: ['The Sundering', 'Walter Jon Williams', None, 'lrf,rar'],
 24: ['The Praxis', 'Walter Jon Williams', None, 'lrf,rar'],
 25: ['Conventions of War', 'Walter Jon Williams', None, 'lrf,rar'],
 26: ['Banewreaker', 'Jacqueline Carey', None, 'lrf,rar'],
 27: ['Godslayer', 'Jacqueline Carey', None, 'lrf,rar'],
 28: ["Kushiel's Scion", 'Jacqueline Carey', None, 'lrf,rar'],
 29: ['Underworld', 'Don DeLillo', None, 'lrf,rar'],
 30: ['Genghis Khan and The Making of the Modern World',
      'Jack Weatherford Orc',
      'Three Rivers Press',
      'lrf,zip'],
 31: ['The Best and the Brightest',
      'David Halberstam',
      'Modern Library',
      'lrf,zip'],
 32: ['The Killer Angels', 'Michael Shaara', None, 'html,lrf'],
 33: ['Band Of Brothers', 'Stephen E Ambrose', None, 'lrf,txt'],
 34: ['The Gates of Rome', 'Conn Iggulden', None, 'lrf,rar'],
 35: ['The Death of Kings', 'Conn Iggulden', 'Bantam Dell', 'lit,lrf'],
 36: ['The Field of Swords', 'Conn Iggulden', None, 'lrf,rar'],
 37: ['Masterman Ready', 'Marryat, Captain Frederick', None, 'lrf'],
 38: ['With the Lightnings',
      'David Drake',
      'Baen Publishing Enterprises',
      'lit,lrf'],
 39: ['Lt. Leary, Commanding',
      'David Drake',
      'Baen Publishing Enterprises',
      'lit,lrf'],
 40: ['The Far Side of The Stars',
      'David Drake',
      'Baen Publishing Enterprises',
      'lrf,rar'],
 41: ['The Way to Glory',
      'David Drake',
      'Baen Publishing Enterprises',
      'lrf,rar'],
 42: ['Some Golden Harbor', 'David Drake', 'Baen Books', 'lrf,rar'],
 43: ['Harry Potter And The Half-Blood Prince',
      'J. K. Rowling',
      None,
      'lrf,rar'],
 44: ['Harry Potter and the Order of the Phoenix',
      'J. K. Rowling',
      None,
      'lrf,rtf'],
 45: ['The Stars at War', 'David Weber , Steve White', None, 'lrf,rtf'],
 46: ['The Stars at War II',
      'Steve White',
      'Baen Publishing Enterprises',
      'lrf,rar'],
 47: ['Exodus', 'Steve White,Shirley Meier', 'Baen Books', 'lrf,rar'],
 48: ['Harry Potter and the Goblet of Fire',
      'J. K. Rowling',
      None,
      'lrf,rar'],
 49: ['Harry Potter and the Prisoner of Azkaban',
      'J. K. Rowling',
      None,
      'lrf,rtf'],
 50: ['Harry Potter and the Chamber of Secrets',
      'J. K. Rowling',
      None,
      'lit,lrf'],
 51: ['Harry Potter and the Deathly Hallows',
      'J.K. Rowling',
      None,
      'lit,lrf,pdf'],
 52: ["His Majesty's Dragon", 'Naomi Novik', None, 'lrf,rar'],
 53: ['Throne of Jade', 'Naomi Novik', 'Del Rey', 'lit,lrf'],
 54: ['Black Powder War', 'Naomi Novik', 'Del Rey', 'lrf,rar'],
 55: ['War and Peace', 'Leo Tolstoy', 'gutenberg.org', 'lrf,txt'],
 56: ['Anna Karenina', 'Leo Tolstoy', 'gutenberg.org', 'lrf,txt'],
 57: ['A Shorter History of Rome',
      'Eugene Lawrence,Sir William Smith',
      'gutenberg.org',
      'lrf,zip'],
 58: ['The Name of the Rose', 'Umberto Eco', None, 'lrf,rar'],
 71: ["Wind Rider's Oath", 'David Weber', 'Baen', 'lrf'],
 74: ['Rally Cry', 'William R Forstchen', None, 'htm,lrf'],
 86: ['Empire of Ivory', 'Naomi Novik', None, 'lrf,rar'],
 87: ["Renegade's Magic", 'Robin Hobb', None, 'lrf,rar'],
 89: ['Master and commander',
      "Patrick O'Brian",
      'Fontana,\n1971',
      'lit,lrf'],
 91: ['A Companion to Wolves',
      'Sarah Monette,Elizabeth Beär',
      None,
      'lrf,rar'],
 92: ['The Lions of al-Rassan', 'Guy Gavriel Kay', 'Eos', 'lit,lrf'],
 93: ['Gardens of the Moon', 'Steven Erikson', 'Tor Fantasy', 'lit,lrf'],
 95: ['The Master and Margarita',
      'Mikhail Bulgakov',
      'N.Y. : Knopf, 1992.',
      'lrf,rtf'],
 120: ['Deadhouse Gates',
       'Steven Erikson',
       'London : Bantam Books, 2001.',
       'lit,lrf'],
 121: ['Memories of Ice', 'Steven Erikson', 'Bantam Books', 'lit,lrf'],
 123: ['House of Chains', 'Steven Erikson', 'Bantam Books', 'lit,lrf'],
 125: ['Midnight Tides', 'Steven Erikson', 'Bantam Books', 'lit,lrf'],
 126: ['The Bonehunters', 'Steven Erikson', 'Bantam Press', 'lit,lrf'],
 129: ['Guns, germs, and steel: the fates of human societies',
       'Jared Diamond',
       'New York : W.W. Norton, c1997.',
       'lit,lrf'],
 136: ['Wildcards', 'George R. R. Martin', None, 'html,lrf'],
 138: ['Off Armageddon Reef', 'David Weber', 'Tor Books', 'lit,lrf'],
 144: ['Atonement',
       'Ian McEwan',
       'New York : Nan A. Talese/Doubleday, 2002.',
       'lrf,rar'],
 146: ['1632', 'Eric Flint', 'Baen Books', 'lit,lrf'],
 147: ['1633', 'David Weber,Eric Flint,Dru Blair', 'Baen', 'lit,lrf'],
 148: ['1634: The Baltic War',
       'David Weber,Eric Flint',
       'Baen',
       'lit,lrf'],
 150: ['The Dragonbone Chair', 'Tad Williams', 'DAW Trade', 'lrf,rtf'],
 152: ['The Little Book That Beats the Market',
       'Joel Greenblatt',
       'Wiley',
       'epub,lrf'],
 153: ['Pride of Carthage', 'David Anthony Durham', 'Anchor', 'lit,lrf'],
 154: ['Stone of farewell',
       'Tad Williams',
       'New York : DAW Books, 1990.',
       'lrf,txt'],
 166: ['American Gods', 'Neil Gaiman', 'HarperTorch', 'lit,lrf'],
 176: ['Pillars of the Earth',
       'Ken Follett',
       'New American Library',
       'lit,lrf'],
 182: ['The Eye of the world',
       'Robert Jordan',
       'New York : T. Doherty Associates, c1990.',
       'lit,lrf'],
 188: ['The Great Hunt', 'Robert Jordan', 'ATOM', 'lrf,zip'],
 189: ['The Dragon Reborn', 'Robert Jordan', None, 'lit,lrf'],
 190: ['The Shadow Rising', 'Robert Jordan', None, 'lit,lrf'],
 191: ['The Fires of Heaven',
       'Robert Jordan',
       'Time Warner Books Uk',
       'lit,lrf'],
 216: ['Lord of chaos',
       'Robert Jordan',
       'New York : TOR, c1994.',
       'lit,lrf'],
 217: ['A Crown of Swords', 'Robert Jordan', None, 'lit,lrf'],
 236: ['The Path of Daggers', 'Robert Jordan', None, 'lit,lrf'],
 238: ['The Client',
       'John Grisham',
       'New York : Island, 1994, c1993.',
       'lit,lrf'],
 240: ["Winter's Heart", 'Robert Jordan', None, 'lit,lrf'],
 242: ['In the Beginning was the Command Line',
       'Neal Stephenson',
       None,
       'lrf,txt'],
 249: ['Crossroads of Twilight', 'Robert Jordan', None, 'lit,lrf'],
 251: ['Caves of Steel', 'Isaac Asimov', 'Del Rey', 'lrf,zip'],
 253: ["Hunter's Run",
       'George R. R. Martin,Gardner Dozois,Daniel Abraham',
       'Eos',
       'lrf,rar'],
 257: ['Knife of Dreams', 'Robert Jordan', None, 'lit,lrf'],
 258: ['Saturday',
       'Ian McEwan',
       'London : Jonathan Cape, 2005.',
       'lrf,txt'],
 259: ['My name is Red',
       'Orhan Pamuk; translated from the Turkish by Erda\\u011f G\xf6knar',
       'New York : Alfred A. Knopf, 2001.',
       'lit,lrf'],
 265: ['Harbinger', 'David Mack', 'Star Trek', 'lit,lrf'],
 267: ['Summon the Thunder',
       'Dayton Ward,Kevin Dilmore',
       'Pocket Books',
       'lit,lrf'],
 268: ['Shalimar the Clown',
       'Salman Rushdie',
       'New York : Random House, 2005.',
       'lit,lrf'],
 269: ['Reap the Whirlwind', 'David Mack', 'Star Trek', 'lit,lrf'],
 272: ['Mistborn', 'Brandon Sanderson', 'Tor Fantasy', 'lrf,rar'],
 273: ['The Thousandfold Thought',
       'R. Scott Bakker',
       'Overlook TP',
       'lrf,rtf'],
 276: ['Elantris',
       'Brandon Sanderson',
       'New York : Tor, 2005.',
       'lrf,rar'],
 291: ['Sundiver',
       'David Brin',
       'New York : Bantam Books, 1995.',
       'lit,lrf'],
 299: ['Imperium', 'Robert Harris', 'Arrow', 'lrf,rar'],
 300: ['Startide Rising', 'David Brin', 'Bantam', 'htm,lrf'],
 301: ['The Uplift War', 'David Brin', 'Spectra', 'lit,lrf'],
 304: ['Brightness Reef', 'David Brin', 'Orbit', 'lrf,rar'],
 305: ["Infinity's Shore", 'David Brin', 'Spectra', 'txt'],
 306: ["Heaven's Reach", 'David Brin', 'Spectra', 'lrf,rar'],
 325: ["Foundation's Triumph", 'David Brin', 'Easton Press', 'lit,lrf'],
 327: ['I am Charlotte Simmons', 'Tom Wolfe', 'Vintage', 'htm,lrf'],
 335: ['The Currents of Space', 'Isaac Asimov', None, 'lit,lrf'],
 340: ['The Other Boleyn Girl',
       'Philippa Gregory',
       'Touchstone',
       'lit,lrf'],
 341: ["Old Man's War", 'John Scalzi', 'Tor', 'htm,lrf'],
 342: ['The Ghost Brigades',
       'John Scalzi',
       'Tor Science Fiction',
       'html,lrf'],
 343: ['The Last Colony', 'John S"calzi', 'Tor Books', 'html,lrf'],
 344: ['Gossip Girl', 'Cecily von Ziegesar', 'Warner Books', 'lrf,rtf'],
 347: ['Little Brother', 'Cory Doctorow', 'Tor Teen', 'lrf'],
 348: ['The Reality Dysfunction',
       'Peter F. Hamilton',
       'Pan MacMillan',
       'lit,lrf'],
 353: ['A Thousand Splendid Suns',
       'Khaled Hosseini',
       'Center Point Large Print',
       'lit,lrf'],
 354: ['Amsterdam', 'Ian McEwan', 'Anchor', 'lrf,txt'],
 355: ['The Neutronium Alchemist',
       'Peter F. Hamilton',
       'Aspect',
       'lit,lrf'],
 356: ['The Naked God', 'Peter F. Hamilton', 'Aspect', 'lit,lrf'],
 421: ['A Shadow in Summer', 'Daniel Abraham', 'Tor Fantasy', 'lrf,rar'],
 427: ['Lonesome Dove', 'Larry M\\cMurtry', None, 'lit,lrf'],
 440: ['Ghost', 'John Ringo', 'Baen', 'lit,lrf'],
 441: ['Kildar', 'John Ringo', 'Baen', 'lit,lrf'],
 443: ['Hidden Empire ', 'Kevin J. Anderson', 'Aspect', 'lrf,rar'],
 444: ['The Gun Seller',
       'Hugh Laurie',
       'Washington Square Press',
       'lrf,rar']
 }

    tests = {
             'Dysfunction' : set([348]),
             'title:Dysfunction' : set([348]),
             'Title:Dysfunction' : set([348]),
             'title:Dysfunction OR author:Laurie': set([348, 444]),
             '(tag:txt or tag:pdf)': set([33, 258, 354, 305, 242, 51, 55, 56, 154]),
             '(tag:txt OR tag:pdf) and author:Tolstoy': set([55, 56]),
             'Tolstoy txt': set([55, 56]),
             'Hamilton Amsterdam' : set([]),
             'Beär' : set([91]),
             'dysfunc or tolstoy': set([348, 55, 56]),
             'tag:txt AND NOT tolstoy': set([33, 258, 354, 305, 242, 154]),
             'not tag:lrf' : set([305]),
             'london:thames': set([13]),
             'publisher:london:thames': set([13]),
             '"(1977)"': set([13]),
             'jack weatherford orc': set([30]),
             'S\\"calzi': {343},
             'author:S\\"calzi': {343},
             '"S\\"calzi"': {343},
             'M\\\\cMurtry': {427},
             }
    fields = {'title':0, 'author':1, 'publisher':2, 'tag':3}

    _universal_set = set(texts.keys())

    def universal_set(self):
        return self._universal_set

    def get_matches(self, location, query, candidates=None):
        location = location.lower()
        if location in list(self.fields.keys()):
            getter = operator.itemgetter(self.fields[location])
        elif location == 'all':
            getter = lambda y: ''.join(x if x else '' for x in y)
        else:
            getter = lambda x: ''

        if not query:
            return set([])
        query = query.lower()
        if candidates:
            return set(key for key, val in list(self.texts.items())
                if key in candidates and query and query
                        in getattr(getter(val), 'lower', lambda : '')())
        else:
            return set(key for key, val in list(self.texts.items())
                if query and query in getattr(getter(val), 'lower', lambda : '')())

    def run_tests(self):
        failed = []
        for query in list(self.tests.keys()):
            prints('Testing query:', query, end=' ')
            res = self.parse(query)
            if res != self.tests[query]:
                print('FAILED', 'Expected:', self.tests[query], 'Got:', res)
                failed.append(query)
            else:
                print('OK')
        return failed


def main(args=sys.argv):
    print('testing unoptimized')
    tester = Tester(['authors', 'author', 'series', 'formats', 'format',
        'publisher', 'rating', 'tags', 'tag', 'comments', 'comment', 'cover',
        'isbn', 'ondevice', 'pubdate', 'size', 'date', 'title', '#read',
        'all', 'search'], test=True)
    failed = tester.run_tests()
    if tester._tests_failed or failed:
        print('>>>>>>>>>>>>>> Tests Failed <<<<<<<<<<<<<<<')
        return 1

    print('\n\ntesting optimized')
    tester = Tester(['authors', 'author', 'series', 'formats', 'format',
        'publisher', 'rating', 'tags', 'tag', 'comments', 'comment', 'cover',
        'isbn', 'ondevice', 'pubdate', 'size', 'date', 'title', '#read',
        'all', 'search'], test=True, optimize=True)
    failed = tester.run_tests()
    if tester._tests_failed or failed:
        print('>>>>>>>>>>>>>> Tests Failed <<<<<<<<<<<<<<<')
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())

# }}}
