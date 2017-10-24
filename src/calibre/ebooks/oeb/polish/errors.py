# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from calibre.ebooks import DRMError as _DRMError


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'



class InvalidBook(ValueError):
    pass


class DRMError(_DRMError):

    def __init__(self):
        super(DRMError, self).__init__(_('This file is locked with DRM. It cannot be edited.'))


class MalformedMarkup(ValueError):
    pass
