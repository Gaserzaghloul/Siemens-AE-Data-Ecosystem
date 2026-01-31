# ==============================================================================
# VALIDATOR PIPELINE
# ==============================================================================

import os
import tempfile
import xml.etree.ElementTree as ET

# Import validation dependencies
try:
    import xmlschema
    XMLSCHEMA_AVAILABLE = True
except ImportError:
    XMLSCHEMA_AVAILABLE = False
    xmlschema = None

try:
    from validators.validation_pipeline import ValidationPipeline
    LOGICAL_VALIDATOR_AVAILABLE = True
except ImportError:
    LOGICAL_VALIDATOR_AVAILABLE = False
    ValidationPipeline = None

from core.settings import BASE_DIR, XSD_SCHEMA_FILE, SCHEMATRON_RULES_FILE

# Load XML schema for validation
SCHEMA = None
SCHEMA_VALIDATION_AVAILABLE = False

if XMLSCHEMA_AVAILABLE:
    try:
        SCHEMA = xmlschema.XMLSchema(XSD_SCHEMA_FILE)
        SCHEMA_VALIDATION_AVAILABLE = True
    except Exception as e:
        print(f"Warning: XML Schema validation not available: {e}")


def validate_xml_schema(xml_content):
    """Return a conservative result for schema validation. If a real SCHEMA
    object is available, use it. Otherwise, perform a lightweight well-formed
    check by ensuring basic XML markers exist.
    """
    if SCHEMA_VALIDATION_AVAILABLE and SCHEMA:
        try:
            # Parse string content to an XML Element before schema validation
            if isinstance(xml_content, (bytes, bytearray)):
                xml_content = xml_content.decode("utf-8", errors="replace")
            if isinstance(xml_content, str):
                try:
                    root = ET.fromstring(xml_content)
                except Exception as e:
                    return {
                        "valid": False,
                        "error": f"XML parse error before XSD validation: {e}",
                    }
            else:
                # Allow Element or file-like objects to pass through
                root = xml_content

            # Validate with xmlschema using the parsed Element
            SCHEMA.validate(root)
            return {"valid": True}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    # Fallback: simple sanity checks
    if (
        not isinstance(xml_content, str)
        or "<" not in xml_content
        or ">" not in xml_content
    ):
        return {"valid": False, "error": "Not well-formed (simple fallback)"}
    return {"valid": True, "note": "fallback-pass"}


def validate_xml_logical(xml_content):
    """Run the full ValidationPipeline (XSD + Schematron + Python) to match the GUI behavior."""
    if not LOGICAL_VALIDATOR_AVAILABLE or not ValidationPipeline:
        return {"valid": False, "error": "validation_pipeline_unavailable"}
    try:
        # Write XML to a temporary file for pipeline validation
        with tempfile.NamedTemporaryFile(
            "w", delete=False, suffix=".xml", encoding="utf-8"
        ) as tmp:
            tmp.write(xml_content)
            tmp_path = tmp.name

        # Use the same pipeline as the GUI; enable filesystem checks to match behavior
        pipeline = ValidationPipeline(
            xsd_file=XSD_SCHEMA_FILE,
            schematron_file=SCHEMATRON_RULES_FILE,
            check_filesystem=True,
        )
        vres = pipeline.validate_file(tmp_path)

        report = {
            "xsd_passed": vres.xsd_passed,
            "schematron_passed": vres.schematron_passed,
            "python_passed": vres.python_passed,
            "errors": {
                "xsd": vres.xsd_errors,
                "schematron": vres.schematron_errors,
                "python": vres.python_errors,
            },
        }
        is_valid = vres.is_valid()

        try:
            os.remove(tmp_path)
        except Exception:
            pass

        return {"valid": is_valid, "report": report}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def validate_xml_complete(xml_content):
    """Validate XML content using both schema and logical validators"""
    schema_result = validate_xml_schema(xml_content)
    logical_result = validate_xml_logical(xml_content)

    # Both validations must pass
    is_valid = schema_result.get("valid", False) and logical_result.get("valid", False)

    return {"valid": is_valid, "schema": schema_result, "logical": logical_result}
