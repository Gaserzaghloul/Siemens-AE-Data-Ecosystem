"""
Generation Service
==================

Orchestrates XML generation workflow following Single Responsibility Principle.
Only handles generation orchestration - delegates validation, export, etc.
"""

import random
from typing import List, Dict, Optional, Tuple

from core.settings import CATEGORIES, SCHEMA_RULES
from core.xml_builder import (
    generate_complete_xml,
    generate_high_quality_cat3,
    apply_quick_schema_fixes,
    extract_prompt_metadata,
    apply_prompt_alignment,
)
from core.prompt_manager import generate_user_prompt


class GenerationService:
    """
    Service responsible for orchestrating XML generation process.
    
    Follows SRP: Only handles generation logic, delegates validation and export.
    """
    
    def __init__(self, validator=None, exporter=None):
        """
        Initialize generation service with optional dependencies.
        
        Args:
            validator: Validation service (dependency injection)
            exporter: Export service (dependency injection)
        """
        self.validator = validator
        self.exporter = exporter
    
    def generate_xml_for_category(
        self,
        category_id: int,
        key: str,
        rules: Dict,
        prompt_meta: Optional[Dict] = None
    ) -> str:
        """
        Generate a single XML document for a category.
        
        Args:
            category_id: Category identifier
            key: Configuration key
            rules: Schema rules
            prompt_meta: Prompt metadata
            
        Returns:
            Generated XML content
        """
        # Generate based on category
        if category_id == 3:
            xml_content = generate_high_quality_cat3(prompt_meta or {})
        else:
            xml_content = generate_complete_xml(
                key, category_id, rules, prompt_meta=prompt_meta
            )
        
        # Apply prefixes and alignment from prompt
        prefix = prompt_meta.get("prefix") if prompt_meta else None
        xml_content = apply_prompt_alignment(xml_content, prefix=prefix, metadata=prompt_meta)
        
        # Apply fixes
        xml_content = apply_quick_schema_fixes(xml_content, category_id)
        
        return xml_content
    
    def generate_prompt_and_xml(
        self,
        category_id: int,
        cat_config: Dict
    ) -> Tuple[str, str, Dict]:
        """
        Generate prompt and corresponding XML.
        
        Args:
            category_id: Category identifier
            cat_config: Category configuration
            
        Returns:
            Tuple of (prompt, xml_content, prompt_metadata)
        """
        # Select random key from category
        key = random.choice(cat_config["keys"])
        
        # Generate prompt
        raw_prompt = generate_user_prompt(key, cat_config)
        user_content, prompt_meta = extract_prompt_metadata(raw_prompt)
        
        # Extract size hint
        size_hint = prompt_meta.get("size")
        
        # Build rules
        rules = dict(SCHEMA_RULES.get(key, {}))
        if size_hint:
            rules["_size_hint"] = size_hint
        
        # Generate XML
        xml_content = self.generate_xml_for_category(
            category_id, key, rules, prompt_meta
        )
        
        return user_content, xml_content, prompt_meta
    
    def create_message_record(
        self,
        user_prompt: str,
        xml_content: str
    ) -> Dict:
        """
        Create a message record for JSONL export.
        
        Args:
            user_prompt: User prompt text
            xml_content: Generated XML content
            
        Returns:
            Message dictionary
        """
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an assistant that outputs XML following the AUTOSAR AE XSD schema for automotive system simulation.",
                },
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": xml_content},
            ],
        }
    
    def get_category_config(self, category_id: int) -> Optional[Dict]:
        """
        Get category configuration.
        
        Args:
            category_id: Category identifier
            
        Returns:
            Category configuration or None
        """
        return CATEGORIES.get(category_id)
    
    def validate_category_exists(self, category_id: int) -> bool:
        """
        Check if category exists.
        
        Args:
            category_id: Category identifier
            
        Returns:
            True if category exists
        """
        return category_id in CATEGORIES
