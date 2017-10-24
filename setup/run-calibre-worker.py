# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys

from calibre.utils.ipc.worker import main


sys.setup_dir = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(os.path.dirname(sys.setup_dir), 'src'))
sys.path.insert(0, SRC)
sys.running_from_setup = True

sys.exit(main())
