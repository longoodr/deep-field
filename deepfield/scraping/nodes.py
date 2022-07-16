import logging

from deepfield.scraping.bbref_pages import MissingPlayDataError
from deepfield.scraping.pages import InsertablePage, Page

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ScrapeNode:
    """A node in the page dependency graph. The nodes are traversed via DFS."""
    
    @classmethod
    def from_page(cls, page: Page):
        """Factory method to create proper ScrapeNode subclass from page. Use
        this over the constructor.
        """
        new_node: ScrapeNode
        if isinstance(page, InsertablePage):
            new_node = InsertableScrapeNode(page)
        else:
            new_node = ScrapeNode(page)
        return new_node
    
    def __init__(self, page: Page):
        self._page = page

    def scrape(self) -> int:
        """Scrapes the page corresponding to this node. Returns the total
        number of pages that were scraped during the process.
        """
        logger.info(f"Starting scrape for {self._page}")
        num_scraped = self._visit_children()
        logger.info(f"Finished scraping {self._page}")
        return num_scraped + 1
        
    def _visit_children(self) -> int:
        num_scraped = 0
        for link in self._page.get_links():
            if link.exists_in_db():
                continue
            try:
                page = Page.from_link(link)
                num_scraped += ScrapeNode.from_page(page).scrape()
            except MissingPlayDataError:
                logger.warning(f"{page} is missing play data, skipping.")
            except Exception:
                logger.exception(f"Could not scrape {page}, skipping.")
        return num_scraped
            
class InsertableScrapeNode(ScrapeNode):
    """A node in the page dependency graph that performs database insertion
    once all its children have been visited.
    """
    
    def __init__(self, page: InsertablePage):
        self._page = page
        
    def scrape(self) -> int:
        num_scraped = self._visit_children()
        self._page.update_db() # type: ignore
        logger.info(f"Finished scraping {self._page}")
        return num_scraped + 1
