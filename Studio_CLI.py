#!/usr/bin/env python3
"""
AUTOSAR AE Data Studio - CLI Entry Point
=========================================

Professional command-line interface following SOLID principles.
This file is intentionally minimal, delegating all logic to specialized services.

Architecture:
- Services: Business logic (generation, validation, export, statistics)
- Managers: Coordination (category, JSONL, file operations)
- CLI: User interface (parsing, formatting)
- Core: Reusable components
- Validators: Validation engine

Usage:
    python Studio_CLI.py --category 6 --count 10
    python Studio_CLI.py --stats
    python Studio_CLI.py --sync
"""

import sys
import random

# Service layer
from services import (
    GenerationService,
    ValidationService,
    ExportService,
    StatisticsService,
)

# Manager layer
from managers import (
    CategoryManager,
    JSONLManager,
    FileManager,
)

# CLI layer
from cli import CommandParser, OutputFormatter


def generate_category_data(
    category_id: int,
    count: int,
    seed: int = None,
    jsonl_file: str = "valid_data.jsonl"
) -> None:
    """
    Generate training data for a category.
    
    Args:
        category_id: Category identifier
        count: Number of examples to generate
        seed: Random seed for reproducibility
        jsonl_file: JSONL file to save to
    """
    # Initialize services (dependency injection)
    gen_service = GenerationService()
    val_service = ValidationService()
    export_service = ExportService()
    stats_service = StatisticsService()
    
    # Initialize managers
    cat_manager = CategoryManager()
    jsonl_manager = JSONLManager()
    
    # Initialize CLI
    formatter = OutputFormatter()
    
    # Set seed if provided
    if seed is not None:
        random.seed(seed)
    
    # Validate category
    if not cat_manager.validate_category_id(category_id):
        formatter.print_error(f"Invalid category ID: {category_id}")
        valid_ids = cat_manager.get_all_category_ids()
        formatter.print_info(f"Valid categories: {valid_ids}")
        sys.exit(1)
    
    # Get category configuration
    cat_config = cat_manager.get_category(category_id)
    cat_name = cat_manager.get_category_name(category_id)
    
    # Print generation start
    formatter.print_generation_start(category_id, cat_name, count)
    
    # Generation loop
    valid_examples = []
    attempted = 0
    max_attempts = count * 50  # Allow up to 50x attempts, matching reference
    
    while len(valid_examples) < count and attempted < max_attempts:
        attempted += 1
        
        try:
            # Generate prompt and XML
            user_prompt, xml_content, prompt_meta = gen_service.generate_prompt_and_xml(
                category_id, cat_config
            )
            
            # Validate
            validation_result = val_service.validate_xml(xml_content)
            
            if val_service.is_valid(validation_result):
                # Create message record
                message = gen_service.create_message_record(user_prompt, xml_content)
                valid_examples.append(message)
                
                # Export XML
                export_service.export_xml_to_file(xml_content, category_id, len(valid_examples))
                
                # Update progress
                formatter.print_progress(len(valid_examples), count, "Generating")
            else:
                # Log validation errors (optional)
                pass
                
        except Exception as e:
            formatter.print_warning(f"Generation error: {e}")
            continue
    
    # Save to JSONL
    if valid_examples:
        jsonl_manager.insert_category_data(
            jsonl_file, category_id, valid_examples, cat_config
        )
        
        # Save to category folder
        json_lines = [gen_service.create_message_record(
            ex["messages"][1]["content"],
            ex["messages"][2]["content"]
        ) for ex in valid_examples]
        
        import json
        category_messages = [json.dumps(msg, ensure_ascii=False) for msg in json_lines]
        export_service.save_messages_to_category_folder(category_id, category_messages)
    
    # Print summary
    formatter.print_generation_summary(len(valid_examples), attempted, len(valid_examples))
    
    if len(valid_examples) < count:
        formatter.print_warning(
            f"Only generated {len(valid_examples)}/{count} examples after {attempted} attempts"
        )


def display_statistics(jsonl_file: str = "valid_data.jsonl") -> None:
    """
    Display category statistics.
    
    Args:
        jsonl_file: JSONL file to analyze
    """
    stats_service = StatisticsService()
    formatter = OutputFormatter()
    
    formatter.print_header("Category Statistics")
    
    stats = stats_service.get_category_statistics(jsonl_file)
    table = stats_service.format_statistics_table(stats)
    
    formatter.print_statistics_table(table)


def sync_organized_data(
    valid_file: str = "valid_data.jsonl",
    organized_file: str = "organized_valid_data_last.json"
) -> None:
    """
    Synchronize organized data from valid data.
    
    Args:
        valid_file: Source valid data file
        organized_file: Target organized data file
    """
    jsonl_manager = JSONLManager()
    formatter = OutputFormatter()
    
    formatter.print_info(f"Synchronizing {organized_file} from {valid_file}")
    
    try:
        jsonl_manager.sync_organized_from_valid(valid_file, organized_file)
        formatter.print_success("Synchronization complete")
    except Exception as e:
        formatter.print_error(f"Synchronization failed: {e}")
        sys.exit(1)


def cleanup_duplicate_files() -> None:
    """Clean up duplicate XML files."""
    file_manager = FileManager()
    formatter = OutputFormatter()
    
    formatter.print_info("Cleaning up duplicate XML files...")
    
    from core.settings import GENERATED_XML_DIR
    removed = file_manager.cleanup_duplicates(GENERATED_XML_DIR, "*.xml")
    
    formatter.print_success(f"Removed {removed} duplicate files")


def main() -> None:
    """Main entry point for CLI."""
    # Parse arguments
    parser = CommandParser()
    args = parser.parse_args()
    formatter = OutputFormatter()
    
    # Validate arguments
    if not parser.validate_args(args):
        sys.exit(1)
    
    # Execute command
    try:
        if args.stats:
            display_statistics(args.jsonl_file)
        elif args.sync:
            sync_organized_data(args.jsonl_file, args.organized_file)
        elif args.cleanup:
            cleanup_duplicate_files()
        else:
            # Generate data
            generate_category_data(
                args.category,
                args.count,
                args.seed,
                args.jsonl_file
            )
    except KeyboardInterrupt:
        formatter.print_warning("\\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        formatter.print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
