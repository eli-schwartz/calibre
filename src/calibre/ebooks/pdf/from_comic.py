import sys
from functools import partial

from calibre.ebooks.lrf.comic.convert_from import (
	config, do_convert, main as _main, option_parser
)


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'Convert a comic in CBR/CBZ format to pdf'


convert = partial(do_convert, output_format='pdf')
main    = partial(_main, output_format='pdf')

if __name__ == '__main__':
    sys.exit(main())

if False:
    option_parser
    config
