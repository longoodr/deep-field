from abc import ABC, abstractmethod

class DependencyResolver(ABC):
    """Verifies whether records already exist in a database."""
    
    @abstractmethod
    def is_url_resolved(self, url: str) -> bool:
        """Returns whether the page associated with the URL already exists."""
        pass
    
class IgnoreDependencies(DependencyResolver):
    """Ignores dependencies by returning True for any given URL."""
    
    def is_url_resolved(self, url: str) -> bool:
        return True