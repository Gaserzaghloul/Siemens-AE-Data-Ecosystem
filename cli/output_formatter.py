"""
Output Formatter
================

Handles console output formatting.
Follows SRP: Only handles output formatting.
"""

import sys
from typing import Dict, Any


class OutputFormatter:
    """
    Formatter for console output.
    
    Follows SRP: Only handles output formatting.
    """
    
    def print_header(self, title: str) -> None:
        """
        Print formatted header.
        
        Args:
            title: Header title
        """
        print("\n" + "=" * 80)
        print(f" {title}")
        print("=" * 80)
    
    def print_progress(
        self,
        current: int,
        total: int,
        prefix: str = "Progress"
    ) -> None:
        """
        Print progress indicator.
        
        Args:
            current: Current count
            total: Total count
            prefix: Progress message prefix
        """
        percent = (current / total * 100) if total > 0 else 0
        bar_length = 50
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "" * filled + "-" * (bar_length - filled)
        
        print(f"\r{prefix}: |{bar}| {current}/{total} ({percent:.1f}%)", end="", flush=True)
        
        if current == total:
            print()  # New line when complete
    
    def print_generation_start(
        self,
        category_id: int,
        category_name: str,
        count: int
    ) -> None:
        """
        Print generation start message.
        
        Args:
            category_id: Category identifier
            category_name: Category name
            count: Number to generate
        """
        self.print_header(f"Generating Category {category_id}: {category_name}")
        print(f"Target count: {count} examples")
        print()
    
    def print_generation_summary(
        self,
        generated: int,
        attempted: int,
        valid: int
    ) -> None:
        """
        Print generation summary.
        
        Args:
            generated: Number generated
            attempted: Number attempted
            valid: Number valid
        """
        print()
        print("-" * 80)
        print("Generation Summary:")
        print(f"  Generated: {generated}")
        print(f"  Attempted: {attempted}")
        print(f"  Valid: {valid}")
        
        if attempted > 0:
            success_rate = (valid / attempted * 100)
            print(f"  Success Rate: {success_rate:.1f}%")
        
        print("=" * 80)
    
    def print_statistics_table(self, stats_text: str) -> None:
        """
        Print statistics table.
        
        Args:
            stats_text: Formatted statistics text
        """
        print(stats_text)
    
    def print_error(self, message: str) -> None:
        """
        Print error message.
        
        Args:
            message: Error message
        """
        print(f"ERROR: {message}", file=sys.stderr)
    
    def print_warning(self, message: str) -> None:
        """
        Print warning message.
        
        Args:
            message: Warning message
        """
        print(f"WARNING: {message}", file=sys.stderr)
    
    def print_success(self, message: str) -> None:
        """
        Print success message.
        
        Args:
            message: Success message
        """
        print(f"✓ {message}")
    
    def print_info(self, message: str) -> None:
        """
        Print info message.
        
        Args:
            message: Info message
        """
        print(f"ℹ {message}")
