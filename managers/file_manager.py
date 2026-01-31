"""
File Manager
============

Manages file system operations.
Follows SRP: Only handles file system utilities.
"""

import os
import glob
import re
from typing import List, Optional
from pathlib import Path


class FileManager:
    """
    Manager responsible for file system operations.
    
    Follows SRP: Only handles file operations.
    """
    
    def ensure_directory(self, directory: str) -> None:
        """
        Ensure directory exists, create if necessary.
        
        Args:
            directory: Directory path
        """
        os.makedirs(directory, exist_ok=True)
    
    def file_exists(self, filepath: str) -> bool:
        """
        Check if file exists.
        
        Args:
            filepath: Path to file
            
        Returns:
            True if file exists
        """
        return os.path.exists(filepath) and os.path.isfile(filepath)
    
    def directory_exists(self, directory: str) -> bool:
        """
        Check if directory exists.
        
        Args:
            directory: Directory path
            
        Returns:
            True if directory exists
        """
        return os.path.exists(directory) and os.path.isdir(directory)
    
    def get_next_file_number(
        self,
        directory: str,
        pattern: str
    ) -> int:
        """
        Find next available file number based on pattern.
        
        Args:
            directory: Directory to search
            pattern: Glob pattern with number placeholder
            
        Returns:
            Next available number
        """
        existing_files = glob.glob(os.path.join(directory, pattern))
        
        existing_numbers = set()
        for filepath in existing_files:
            filename = os.path.basename(filepath)
            # Extract all numbers from filename
            numbers = re.findall(r'\d+', filename)
            if numbers:
                existing_numbers.add(int(numbers[0]))
        
        next_num = 1
        while next_num in existing_numbers:
            next_num += 1
        
        return next_num
    
    def list_files(
        self,
        directory: str,
        pattern: str = "*"
    ) -> List[str]:
        """
        List files in directory matching pattern.
        
        Args:
            directory: Directory to search
            pattern: Glob pattern (default: all files)
            
        Returns:
            List of matching file paths
        """
        if not self.directory_exists(directory):
            return []
        
        search_pattern = os.path.join(directory, pattern)
        return glob.glob(search_pattern)
    
    def count_files(
        self,
        directory: str,
        pattern: str = "*"
    ) -> int:
        """
        Count files matching pattern.
        
        Args:
            directory: Directory to search
            pattern: Glob pattern
            
        Returns:
            Number of matching files
        """
        return len(self.list_files(directory, pattern))
    
    def cleanup_duplicates(
        self,
        directory: str,
        pattern: str
    ) -> int:
        """
        Remove duplicate files based on pattern.
        
        Args:
            directory: Directory to clean
            pattern: Pattern to match duplicates
            
        Returns:
            Number of files removed
        """
        files = self.list_files(directory, pattern)
        
        # Group by base name (without timestamp)
        groups = {}
        for filepath in files:
            filename = os.path.basename(filepath)
            # Extract base name without timestamp
            base = re.sub(r'_\d{8}_\d{6}', '', filename)
            if base not in groups:
                groups[base] = []
            groups[base].append(filepath)
        
        removed = 0
        for base, file_list in groups.items():
            if len(file_list) > 1:
                # Sort by modification time, keep newest
                file_list.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                for filepath in file_list[1:]:  # Remove all but newest
                    try:
                        os.remove(filepath)
                        removed += 1
                    except Exception as e:
                        print(f"Warning: Could not remove {filepath}: {e}")
        
        return removed
    
    def get_file_size(self, filepath: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            filepath: Path to file
            
        Returns:
            File size in bytes (0 if not exists)
        """
        if self.file_exists(filepath):
            return os.path.getsize(filepath)
        return 0
    
    def get_file_size_mb(self, filepath: str) -> float:
        """
        Get file size in megabytes.
        
        Args:
            filepath: Path to file
            
        Returns:
            File size in MB
        """
        return self.get_file_size(filepath) / (1024 * 1024)
