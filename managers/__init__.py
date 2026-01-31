"""
Managers Package
================

Coordination layer for AUTOSAR AE Data Studio.

Managers:
- CategoryManager: Category operations and configuration
- JSONLManager: JSONL file management
- FileManager: File system operations
"""

from .category_manager import CategoryManager
from .jsonl_manager import JSONLManager
from .file_manager import FileManager

__all__ = [
    'CategoryManager',
    'JSONLManager',
    'FileManager',
]
