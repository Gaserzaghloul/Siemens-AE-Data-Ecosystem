"""
Category Manager
================

Manages category configuration and operations.
Follows SRP: Only handles category-related logic.
"""

from typing import Dict, List, Optional

from core.settings import CATEGORIES


class CategoryManager:
    """
    Manager responsible for category operations.
    
    Follows SRP: Only handles category configuration and queries.
    """
    
    def __init__(self, categories: Dict = None):
        """
        Initialize category manager.
        
        Args:
            categories: Category configuration dictionary (default: from settings)
        """
        self.categories = categories if categories is not None else CATEGORIES
    
    def get_category(self, category_id: int) -> Optional[Dict]:
        """
        Get category configuration.
        
        Args:
            category_id: Category identifier
            
        Returns:
            Category configuration dictionary or None
        """
        return self.categories.get(category_id)
    
    def get_category_name(self, category_id: int) -> str:
        """
        Get category name.
        
        Args:
            category_id: Category identifier
            
        Returns:
            Category name or "Unknown"
        """
        cat_config = self.get_category(category_id)
        return cat_config.get("name", "Unknown") if cat_config else "Unknown"
    
    def get_category_keys(self, category_id: int) -> List[str]:
        """
        Get list of keys for a category.
        
        Args:
            category_id: Category identifier
            
        Returns:
            List of configuration keys
        """
        cat_config = self.get_category(category_id)
        return cat_config.get("keys", []) if cat_config else []
    
    def validate_category_id(self, category_id: int) -> bool:
        """
        Check if category ID is valid.
        
        Args:
            category_id: Category identifier
            
        Returns:
            True if category exists
        """
        return category_id in self.categories
    
    def get_all_category_ids(self) -> List[int]:
        """
        Get list of all category IDs.
        
        Returns:
            List of category IDs
        """
        return sorted(self.categories.keys())
    
    def get_category_count(self) -> int:
        """
        Get total number of categories.
        
        Returns:
            Number of categories
        """
        return len(self.categories)
    
    def get_prompt_style(self, category_id: int) -> str:
        """
        Get prompt style for category.
        
        Args:
            category_id: Category identifier
            
        Returns:
            Prompt style identifier
        """
        cat_config = self.get_category(category_id)
        if cat_config and isinstance(cat_config, dict):
            return cat_config.get("user_prompt_style", "generate_core")
        return "generate_core"
