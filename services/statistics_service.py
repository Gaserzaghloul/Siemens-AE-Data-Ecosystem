"""
Statistics Service
==================

Provides statistics and reporting following Single Responsibility Principle.
Only handles data analysis and statistics.
"""

import os
import json
import glob
from typing import Dict, List
from collections import defaultdict

from core.settings import CATEGORIES, GENERATED_XML_DIR


class StatisticsService:
    """
    Service responsible for generating statistics and reports.
    
    Follows SRP: Only handles statistics and reporting.
    """
    
    def __init__(self):
        """Initialize statistics service."""
        self.categories = CATEGORIES
        self.xml_dir = GENERATED_XML_DIR
    
    def count_xml_files_per_category(self) -> Dict[int, int]:
        """
        Count XML files for each category.
        
        Returns:
            Dictionary mapping category_id to count
        """
        category_counts = {}
        
        for cat_id in sorted(self.categories.keys()):
            pattern = os.path.join(self.xml_dir, f"category_{cat_id}_example_*.xml")
            files = glob.glob(pattern)
            category_counts[cat_id] = len(files)
        
        return category_counts
    
    def count_messages_per_category(self, jsonl_file: str) -> Dict[int, int]:
        """
        Count messages per category in JSONL file.
        
        Args:
            jsonl_file: Path to JSONL file
            
        Returns:
            Dictionary mapping category_id to message count
        """
        category_counts = defaultdict(int)
        
        if not os.path.exists(jsonl_file):
            return dict(category_counts)
        
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    try:
                        record = json.loads(line)
                        cat_id = record.get("category")
                        if cat_id:
                            category_counts[cat_id] += 1
                        else:
                             # Handle uncategorized records (missing 'category' field)
                             category_counts[0] += 1 # Use 0 for uncategorized
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Warning: Could not read {jsonl_file}: {e}")
        
        return dict(category_counts)
    
    def get_category_statistics(self, jsonl_file: str) -> Dict:
        """
        Get comprehensive category statistics.
        
        Args:
            jsonl_file: Path to JSONL file
            
        Returns:
            Statistics dictionary
        """
        stats = {
            "total_categories": len(self.categories),
            "xml_counts": self.count_xml_files_per_category(),
            "jsonl_counts": self.count_messages_per_category(jsonl_file),
            "category_names": {
                cat_id: config["name"]
                for cat_id, config in self.categories.items()
            },
        }
        
        # Calculate totals
        stats["total_xml_files"] = sum(stats["xml_counts"].values())
        stats["total_jsonl_records"] = sum(stats["jsonl_counts"].values())
        
        return stats
    
    def format_statistics_table(self, stats: Dict) -> str:
        """
        Format statistics as readable table.
        
        Args:
            stats: Statistics dictionary from get_category_statistics()
            
        Returns:
            Formatted table string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("Category Statistics")
        lines.append("=" * 80)
        lines.append(f"{'ID':<4} {'Name':<30} {'XML Files':<12} {'JSONL Records':<15}")
        lines.append("-" * 80)
        
        for cat_id in sorted(self.categories.keys()):
            name = stats["category_names"].get(cat_id, "Unknown")
            xml_count = stats["xml_counts"].get(cat_id, 0)
            jsonl_count = stats["jsonl_counts"].get(cat_id, 0)
            
            lines.append(
                f"{cat_id:<4} {name:<30} {xml_count:<12} {jsonl_count:<15}"
            )
        
        # Handle uncategorized
        if 0 in stats["jsonl_counts"] and stats["jsonl_counts"][0] > 0:
             lines.append(
                f"{'N/A':<4} {'Uncategorized':<30} {'-':<12} {stats['jsonl_counts'][0]:<15}"
            )
            
        lines.append("-" * 80)
        lines.append(
            f"{'TOTAL':<4} {'':<30} {stats['total_xml_files']:<12} {stats['total_jsonl_records']:<15}"
        )
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def get_generation_summary(
        self,
        category_id: int,
        generated_count: int,
        attempted_count: int,
        valid_count: int
    ) -> str:
        """
        Get formatted generation summary.
        
        Args:
            category_id: Category identifier
            generated_count: Number generated
            attempted_count: Number attempted
            valid_count: Number valid
            
        Returns:
            Formatted summary string
        """
        cat_name = self.categories.get(category_id, {}).get("name", "Unknown")
        success_rate = (valid_count / attempted_count * 100) if attempted_count > 0 else 0
        
        summary = f"""
Generation Summary:
-------------------
Category ID: {category_id}
Category Name: {cat_name}
Generated: {generated_count}
Attempted: {attempted_count}
Valid: {valid_count}
Success Rate: {success_rate:.1f}%
"""
        return summary
