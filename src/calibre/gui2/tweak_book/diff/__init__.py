# vim:fileencoding=utf-8
from calibre.constants import plugins


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'



def load_patience_module():
    p, err = plugins['_patiencediff_c']
    if err:
        raise ImportError('Failed to import the PatienceDiff C module with error: %r' % err)
    return p


def get_sequence_matcher():
    return load_patience_module().PatienceSequenceMatcher_c
