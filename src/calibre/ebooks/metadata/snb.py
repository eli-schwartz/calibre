'''Read meta information from SNB files'''

import os
from io import StringIO

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.snb.snbfile import SNBFile
from lxml import etree


__license__   = 'GPL v3'
__copyright__ = '2010, Li Fanxi <lifanxi@freemindworld.com>'



def get_metadata(stream, extract_cover=True):
    """ Return metadata as a L{MetaInfo} object """
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    snbFile = SNBFile()

    try:
        if not hasattr(stream, 'write'):
            snbFile.Parse(StringIO(stream), True)
        else:
            stream.seek(0)
            snbFile.Parse(stream, True)

        meta = snbFile.GetFileStream('snbf/book.snbf')

        if meta is not None:
            meta = etree.fromstring(meta)
            mi.title = meta.find('.//head/name').text
            mi.authors = [meta.find('.//head/author').text]
            mi.language = meta.find('.//head/language').text.lower().replace('_', '-')
            mi.publisher = meta.find('.//head/publisher').text

            if extract_cover:
                cover = meta.find('.//head/cover')
                if cover is not None and cover.text is not None:
                    root, ext = os.path.splitext(cover.text)
                    if ext == '.jpeg':
                        ext = '.jpg'
                    mi.cover_data = (ext[-3:], snbFile.GetFileStream('snbc/images/' + cover.text))

    except Exception:
        import traceback
        traceback.print_exc()

    return mi
