"""
Validation Service
==================

Orchestrates validation workflow following Single Responsibility Principle.
Only handles validation orchestration.
"""

from typing import Dict, Any

from core.validator_pipeline import (
    validate_xml_schema,
    validate_xml_logical,
    validate_xml_complete,
)


class ValidationService:
    """
    Service responsible for orchestrating validation process.
    
    Follows SRP: Only handles validation logic.
    """
    
    def __init__(self, pipeline=None):
        """
        Initialize validation service.
        
        Args:
            pipeline: Validation pipeline (dependency injection)
        """
        self.pipeline = pipeline
    
    def validate_xml(self, xml_content: str) -> Dict[str, Any]:
        """
        Perform complete XML validation.
        
        Args:
            xml_content: XML content to validate
            
        Returns:
            Validation result dictionary with 'valid', 'schema', 'logical' keys
        """
        return validate_xml_complete(xml_content)
    
    def validate_schema_only(self, xml_content: str) -> Dict[str, Any]:
        """
        Perform XSD schema validation only.
        
        Args:
            xml_content: XML content to validate
            
        Returns:
            Schema validation result
        """
        return validate_xml_schema(xml_content)
    
    def validate_logical_only(self, xml_content: str) -> Dict[str, Any]:
        """
        Perform logical validation only.
        
        Args:
            xml_content: XML content to validate
            
        Returns:
            Logical validation result
        """
        return validate_xml_logical(xml_content)
    
    def is_valid(self, validation_result: Dict[str, Any]) -> bool:
        """
        Check if validation result indicates valid XML.
        
        Args:
            validation_result: Result from validate_xml()
            
        Returns:
            True if XML is valid
        """
        return validation_result.get("valid", False)
    
    def get_error_summary(self, validation_result: Dict[str, Any]) -> str:
        """
        Get human-readable error summary.
        
        Args:
            validation_result: Result from validate_xml()
            
        Returns:
            Error summary string
        """
        if self.is_valid(validation_result):
            return "No errors"
        
        errors = []
        
        # Schema errors
        schema = validation_result.get("schema", {})
        if not schema.get("valid", True):
            schema_error = schema.get("error", "Unknown schema error")
            errors.append(f"Schema: {schema_error}")
        
        # Logical errors
        logical = validation_result.get("logical", {})
        if not logical.get("valid", True):
            report = logical.get("report", {})
            if isinstance(report, dict):
                error_dict = report.get("errors", {})
                for error_type, error_list in error_dict.items():
                    if error_list:
                        errors.append(f"{error_type.capitalize()}: {len(error_list)} errors")
        
        return "; ".join(errors) if errors else "Validation failed"
