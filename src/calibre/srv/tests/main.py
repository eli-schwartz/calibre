# vim:fileencoding=utf-8
import os

from calibre.utils.run_tests import find_tests_in_dir, run_tests


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'



def find_tests():
    base = os.path.dirname(os.path.abspath(__file__))
    return find_tests_in_dir(base)


if __name__ == '__main__':
    try:
        import init_calibre  # noqa
    except ImportError:
        pass
    run_tests(find_tests)
