"""
Validators Package
==================

This package contains all XML validation logic:
- XSD schema validation
- Schematron rule validation  
- Python logical validation

Modules:
- validation_pipeline.py: Main validation orchestrator
- python_logical_validations.py: Python-based logical checks
- schematronValidator.py: Schematron validation implementation
"""

from .validation_pipeline import ValidationPipeline

__all__ = ['ValidationPipeline']
