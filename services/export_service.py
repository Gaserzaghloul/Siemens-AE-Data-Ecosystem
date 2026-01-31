"""
Export Service
==============

Handles all file export operations following Single Responsibility Principle.
Only handles file writing and export logic.
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any

from core.settings import GENERATED_XML_DIR, MESSAGES_DIR


class ExportService:
    """
    Service responsible for exporting generated data to files.
    
    Follows SRP: Only handles export operations.
    """
    
    def __init__(self):
        """Initialize export service."""
        self.xml_dir = GENERATED_XML_DIR
        self.messages_dir = MESSAGES_DIR
    
    def export_xml_to_file(
        self,
        xml_content: str,
        category_id: int,
        example_num: int
    ) -> str:
        """
        Export XML content to file with automatic numbering.
        
        Args:
            xml_content: XML content to export
            category_id: Category identifier
            example_num: Example number (hint, actual may differ)
            
        Returns:
            Path to exported file
        """
        # Ensure directory exists
        os.makedirs(self.xml_dir, exist_ok=True)
        
        # Generate timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Find next available number
        import glob
        pattern = os.path.join(self.xml_dir, f"category_{category_id}_example_*.xml")
        existing_files = glob.glob(pattern)
        
        existing_numbers = set()
        for file_path in existing_files:
            filename = os.path.basename(file_path)
            import re
            match = re.search(r"category_\d+_example_(\d+)", filename)
            if match:
                existing_numbers.add(int(match.group(1)))
        
        next_num = 1
        while next_num in existing_numbers:
            next_num += 1
        
        # Create filename
        filename = os.path.join(
            self.xml_dir,
            f"category_{category_id}_example_{next_num}_{timestamp}.xml"
        )
        
        # Write file
        with open(filename, "w", encoding="utf-8") as f:
            f.write(xml_content)
        
        return filename
    
    def save_messages_to_category_folder(
        self,
        category_id: int,
        messages: List[str]
    ) -> str:
        """
        Save messages to category-specific JSONL file.
        
        Args:
            category_id: Category identifier
            messages: List of JSON-encoded message strings
            
        Returns:
            Path to saved file
        """
        # Create category directory
        cat_dir = os.path.join(self.messages_dir, f"Category{category_id}")
        os.makedirs(cat_dir, exist_ok=True)
        
        output_file = os.path.join(cat_dir, "messages.jsonl")
        
        # Append to file
        with open(output_file, "a", encoding="utf-8") as f:
            for msg in messages:
                f.write(msg + "\n")
        
        return output_file
    
    def append_to_jsonl(
        self,
        records: List[Dict[str, Any]],
        filepath: str
    ) -> int:
        """
        Append records to JSONL file.
        
        Args:
            records: List of dictionaries to append
            filepath: Path to JSONL file
            
        Returns:
            Number of records written
        """
        mode = "a" if os.path.exists(filepath) else "w"
        
        with open(filepath, mode, encoding="utf-8") as f:
            for record in records:
                json_line = json.dumps(record, ensure_ascii=False)
                f.write(json_line + "\n")
        
        return len(records)
    
    def ensure_directory_exists(self, directory: str) -> None:
        """
        Ensure a directory exists, create if necessary.
        
        Args:
            directory: Directory path
        """
        os.makedirs(directory, exist_ok=True)
    
    def get_output_filepath(
        self,
        base_name: str,
        extension: str = ".jsonl"
    ) -> str:
        """
        Get standardized output filepath.
        
        Args:
            base_name: Base filename without extension
            extension: File extension (default: .jsonl)
            
        Returns:
            Full filepath
        """
        if not extension.startswith("."):
            extension = "." + extension
        return base_name + extension
