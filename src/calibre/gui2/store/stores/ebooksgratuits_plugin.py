
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult
from calibre.utils.filenames import ascii_text


store_version = 1  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2012, Florent FAYOLLE <florent.fayolle69@gmail.com>'
__docformat__ = 'restructuredtext en'



class EbooksGratuitsStore(BasicStoreConfig, OpenSearchOPDSStore):

    open_search_url = 'http://www.ebooksgratuits.com/opds/opensearch.xml'
    web_url = 'http://www.ebooksgratuits.com/'

    def strip_accents(self, s):
        return ascii_text(s)

    def search(self, query, max_results=10, timeout=60):
        query = self.strip_accents(str(query))
        for s in OpenSearchOPDSStore.search(self, query, max_results, timeout):
            if s.downloads:
                s.drm = SearchResult.DRM_UNLOCKED
                s.price = '$0.00'
                yield s
