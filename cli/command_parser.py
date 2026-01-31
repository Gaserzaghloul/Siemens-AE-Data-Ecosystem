"""
Command Parser
==============

Handles CLI argument parsing.
Follows SRP: Only handles command-line argument parsing.
"""

import argparse
from typing import Any


class CommandParser:
    """
    Parser for command-line arguments.
    
    Follows SRP: Only handles argument parsing.
    """
    
    def __init__(self):
        """Initialize command parser."""
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Create argument parser with all options.
        
        Returns:
            Configured ArgumentParser
        """
        parser = argparse.ArgumentParser(
            description="AUTOSAR AE Training Data Generator",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Generate 10 examples for category 6
  python auto_data.py --category 6 --count 10
  
  # Generate with custom seed
  python auto_data.py --category 3 --count 5 --seed 42
  
  # Display statistics
  python auto_data.py --stats
  
  # Sync organized data
  python auto_data.py --sync
            """
        )
        
        # Generation arguments
        parser.add_argument(
            "--category",
            type=int,
            help="Category ID to generate (3-16)"
        )
        
        parser.add_argument(
            "--count",
            type=int,
            default=1,
            help="Number of examples to generate (default: 1)"
        )
        
        parser.add_argument(
            "--seed",
            type=int,
            help="Random seed for reproducibility"
        )
        
        # Utility arguments
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Display category statistics"
        )
        
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Synchronize organized_valid_data_last.json from valid_data.jsonl"
        )
        
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Clean up duplicate XML files"
        )
        
        # File paths
        parser.add_argument(
            "--jsonl-file",
            default="valid_data.jsonl",
            help="JSONL file to use (default: valid_data.jsonl)"
        )
        
        parser.add_argument(
            "--organized-file",
            default="organized_valid_data_last.json",
            help="Organized data file (default: organized_valid_data_last.json)"
        )
        
        return parser
    
    def parse_args(self, args=None) -> Any:
        """
        Parse command-line arguments.
        
        Args:
            args: Arguments to parse (default: sys.argv)
            
        Returns:
            Parsed arguments namespace
        """
        return self.parser.parse_args(args)
    
    def validate_args(self, args: Any) -> bool:
        """
        Validate parsed arguments.
        
        Args:
            args: Parsed arguments namespace
            
        Returns:
            True if arguments are valid
        """
        # If generating, category is required
        if not any([args.stats, args.sync, args.cleanup]):
            if not args.category:
                print("Error: --category is required when generating data")
                return False
            
            if args.count < 1:
                print("Error: --count must be at least 1")
                return False
        
        return True
