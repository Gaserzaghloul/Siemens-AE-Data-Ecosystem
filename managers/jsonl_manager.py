"""
JSONL Manager
=============

Manages JSONL file operations.
Follows SRP: Only handles JSONL file reading/writing.
"""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime


class JSONLManager:
    """
    Manager responsible for JSONL file operations.
    
    Follows SRP: Only handles JSONL file I/O.
    """
    
    def read_jsonl(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Read JSONL file and return list of records.
        
        Args:
            filepath: Path to JSONL file
            
        Returns:
            List of dictionaries
        """
        records = []
        
        if not os.path.exists(filepath):
            return records
        
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON at line {line_num}: {e}")
                    continue
        
        return records
    
    def write_jsonl(
        self,
        records: List[Dict[str, Any]],
        filepath: str,
        mode: str = "w"
    ) -> int:
        """
        Write records to JSONL file.
        
        Args:
            records: List of dictionaries to write
            filepath: Path to JSONL file
            mode: File mode ('w' for overwrite, 'a' for append)
            
        Returns:
            Number of records written
        """
        with open(filepath, mode, encoding="utf-8") as f:
            for record in records:
                json_line = json.dumps(record, ensure_ascii=False)
                f.write(json_line + "\n")
        
        return len(records)
    
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
            Number of records appended
        """
        return self.write_jsonl(records, filepath, mode="a")
    
    def filter_by_category(
        self,
        records: List[Dict[str, Any]],
        category_id: int
    ) -> List[Dict[str, Any]]:
        """
        Filter records by category.
        
        Args:
            records: List of records
            category_id: Category to filter by
            
        Returns:
            Filtered list of records
        """
        return [r for r in records if r.get("category") == category_id]
    
    def update_generation_timestamp(self, filepath: str) -> None:
        """
        Update generation_timestamp in all records.
        
        Args:
            filepath: Path to JSONL file
        """
        if not os.path.exists(filepath):
            return
        
        # Read all records
        records = self.read_jsonl(filepath)
        
        # Update timestamp
        timestamp = datetime.now().isoformat()
        for record in records:
            record["generation_timestamp"] = timestamp
        
        # Write back
        self.write_jsonl(records, filepath, mode="w")
    
    def sync_organized_from_valid(
        self,
        valid_file: str,
        organized_file: str
    ) -> None:
        """
        Synchronize organized data from valid data.
        
        Args:
            valid_file: Source valid data file
            organized_file: Target organized data file
        """
        # Read valid data
        valid_records = self.read_jsonl(valid_file)
        
        # Write to organized file
        self.write_jsonl(valid_records, organized_file, mode="w")
    
    def insert_category_data(
        self,
        filepath: str,
        category_id: int,
        new_records: List[Dict[str, Any]],
        cat_config: Dict[str, Any]
    ) -> int:
        """
        Insert new records for a category into JSONL file.
        
        Args:
            filepath: Path to JSONL file
            category_id: Category identifier
            new_records: New records to insert
            cat_config: Category configuration
            
        Returns:
            Number of records inserted
        """
        # Read existing records
        existing_records = self.read_jsonl(filepath) if os.path.exists(filepath) else []
        
        # Add category metadata to new records
        # timestamp = datetime.now().isoformat()
        # for record in new_records:
        #     record["category"] = category_id
        #     record["generation_timestamp"] = timestamp
        
        # Combine and write
        all_records = existing_records + new_records
        self.write_jsonl(all_records, filepath, mode="w")
        
        return len(new_records)
    
    def count_records(self, filepath: str) -> int:
        """
        Count total records in JSONL file.
        
        Args:
            filepath: Path to JSONL file
            
        Returns:
            Number of records
        """
        if not os.path.exists(filepath):
            return 0
        
        count = 0
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    count += 1
        
        return count
