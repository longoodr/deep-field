import logging
from typing import Dict, Iterable, Optional, Set, Tuple, Type

from deepfield.data.pages import InsertablePage, Link, Page

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ScrapeNode:
    """A node in the page dependency graph. The nodes are traversed via DFS."""
    
    _cached_nodes: Dict[Page, "ScrapeNode"] = {}
    
    @classmethod
    def from_page(cls, page: Page):
        """Factory method to create proper ScrapeNode subclass from page. Use
        this over the constructor.
        """
        if page in cls._cached_nodes:
            return cls._cached_nodes[page]
        new_node: ScrapeNode
        if isinstance(page, InsertablePage):
            new_node = InsertableScrapeNode(page)
        else:
            new_node = ScrapeNode(page)
        cls._cached_nodes[page] = new_node
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
            page = Page.from_link(link)
            num_scraped += ScrapeNode.from_page(page).scrape()
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
