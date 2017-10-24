# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.dialogs.drm_error_ui import Ui_Dialog
from PyQt5.Qt import QDialog


class DRMErrorMessage(QDialog, Ui_Dialog):

    def __init__(self, parent=None, title=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        if title is not None:
            t = str(self.msg.text())
            self.msg.setText('<h2>%s</h2>%s'%(title, t))
        self.resize(self.sizeHint())
