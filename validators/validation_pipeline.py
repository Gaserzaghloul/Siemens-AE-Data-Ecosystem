"""
validation_pipeline.py

Orchestrates complete AE validation: XSD → Schematron → Python logical validation.

This pipeline provides comprehensive coverage of AE rules by combining:
1. XSD validation - Structural and type constraints
2. Schematron validation - Fast local XPath checks (Rules 1-82 where applicable)
3. Python validation - Complex semantic checks (e.g., 24,25,31,32,38,39,40,44,46,58,64,70,71,74-82,90)

- Notes:
- Rule 40: PRE-BUILT-APPLICATION PATH must exist/be executable (filesystem checks are ON by default; use --no-check-filesystem to disable).
- Rule 90: InterfaceReference must resolve to existing SENDER-RECEIVER-INTERFACE.

Usage:
    # Validate single file
    python validation_pipeline.py logical_samples/coreid_mapping.xml

    # Validate directory
    python validation_pipeline.py logical_samples/

    # Filesystem checks are ENABLED by default (affects Rule 40 PATH validation)
    # Disable filesystem checks if needed
    python validation_pipeline.py logical_samples/ --no-check-filesystem

    # Generate report
    python validation_pipeline.py logical_samples/ --report validation_report.md
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple
import re

# Prefer the same XSD engine used by validate_xml.py
try:
    import xmlschema  # python-xmlschema
except Exception:  # pragma: no cover
    xmlschema = None

from . import python_logical_validations


class ValidationResult:
    """Holds validation results for a single file."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.xsd_passed = False
        self.xsd_errors = []
        self.schematron_passed = False
        self.schematron_errors = []
        self.python_passed = False
        self.python_errors = []

    def is_valid(self) -> bool:
        """Returns True if file passed all validation stages."""
        return self.xsd_passed and self.schematron_passed and self.python_passed

    def total_errors(self) -> int:
        """Returns total count of errors across all validators."""
        return (
            len(self.xsd_errors) + len(self.schematron_errors) + len(self.python_errors)
        )


class ValidationPipeline:
    """Orchestrates XSD → Schematron → Python validation pipeline."""

    def __init__(
        self,
        xsd_file: str = "AE_XSD_schema.xsd.xml",
        schematron_file: str = "SchematronRules.sch",
        check_filesystem: bool = True,
    ):
        """
        Initialize validation pipeline.

        Args:
            xsd_file: Path to XSD schema
            schematron_file: Path to Schematron rules
            check_filesystem: Enable filesystem checks in Python validator
        """
        base_dir = Path(__file__).resolve().parent
        self._base_dir = base_dir

        def _resolve_path(candidate: Path) -> Path:
            if candidate.is_absolute():
                return candidate
            search_roots = [base_dir, base_dir.parent, base_dir.parent.parent]
            for root in search_roots:
                resolved = (root / candidate).resolve()
                if resolved.exists():
                    return resolved
            return (base_dir / candidate).resolve()

        self.xsd_file = str(_resolve_path(Path(xsd_file)))
        self.schematron_file = str(_resolve_path(Path(schematron_file)))
        self.check_filesystem = check_filesystem
        self.results: Dict[str, ValidationResult] = {}

        # Load XSD schema using xmlschema (same as validate_xml.py)
        self.xsd_schema = None
        if xmlschema is None:
            print(
                "⚠️ Warning: xmlschema library not available; XSD validation will be skipped.\n   Install it with: pip install xmlschema"
            )
        else:
            try:
                self.xsd_schema = xmlschema.XMLSchema(self.xsd_file)
            except Exception as e:
                print(f"⚠️ Warning: Could not load XSD schema via xmlschema: {e}")
                self.xsd_schema = None

    def validate_file(self, xml_file: str) -> ValidationResult:
        """
        Run complete validation pipeline on a single file.

        Args:
            xml_file: Path to XML file

        Returns:
            ValidationResult object
        """
        result = ValidationResult(xml_file)

        # Stage 1: XSD validation
        print(f"  [1/3] XSD validation...", end=" ")
        result.xsd_passed, result.xsd_errors = self._validate_xsd(xml_file)
        print("✅ PASS" if result.xsd_passed else f"❌ FAIL")

        # Stage 2: Schematron validation
        print(f"  [2/3] Schematron validation...", end=" ")
        result.schematron_passed, result.schematron_errors = self._validate_schematron(
            xml_file
        )
        print("✅ PASS" if result.schematron_passed else f"❌ FAIL")

        # Stage 3: Python logical validation
        print(f"  [3/3] Python validation...", end=" ")
        result.python_passed, result.python_errors = self._validate_python(xml_file)
        # Force fail if any errors are present
        if result.python_errors:
            result.python_passed = False
        print("✅ PASS" if result.python_passed else f"❌ FAIL")

        return result

    def _validate_xsd(self, xml_file: str) -> Tuple[bool, List[str]]:
        """Validate XML against XSD schema using xmlschema (python-xmlschema)."""
        if not self.xsd_schema:
            return True, []  # Skip if schema not loaded

        try:
            if self.xsd_schema.is_valid(xml_file):
                return True, []
            else:
                errors: List[str] = []
                for err in self.xsd_schema.iter_errors(xml_file):
                    path = getattr(err, "path", "")
                    reason = getattr(err, "reason", str(err))
                    prefix = f"At {path}:" if path else "At <unknown>:"
                    errors.append(f"{prefix} {reason}")
                return False, errors or ["Unknown XSD validation error"]
        except Exception as e:
            return False, [f"XSD validation error: {str(e)}"]

    def _validate_schematron(self, xml_file: str) -> Tuple[bool, List[str]]:
        """Run Schematron validation."""
        try:
            # Use existing schematronValidator.py
            venv_python = Path(".venv/Scripts/python.exe")
            if not venv_python.exists():
                venv_python = Path("python")  # Fallback to system Python

            validator_path = (self._base_dir / "schematronValidator.py").resolve()
            cmd = [
                str(venv_python),
                str(validator_path),
                self.schematron_file,
                xml_file,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # Parse output to determine pass/fail
            output = (result.stdout or "") + (result.stderr or "")
            passed_tokens = ("[PASS]" in output) or ("PASSED" in output)
            failed_tokens = ("[FAIL]" in output) or ("FAILED" in output)

            # Prefer return code from validator: 0=pass, 2=fail (our validator); non-zero generally means failure
            if result.returncode == 0 and passed_tokens and not failed_tokens:
                return True, []

            # If return code non-zero or failed tokens present, collect errors
            if result.returncode != 0 or failed_tokens:
                errors: List[str] = []

                # 1) Try to capture bullet-style lines produced by some validators
                for line in output.split("\n"):
                    s = line.strip()
                    if s.startswith("- "):
                        errors.append(s[2:])
                    elif s.startswith("-") and len(s) > 1 and s[1] != "-":
                        errors.append(s[1:].lstrip())

                # 2) Try to extract SVRL failed-assert messages: location + text
                if not errors:
                    # Namespaced form: <svrl:failed-assert location="..."><svrl:text>...</svrl:text>
                    svrl_ns_matches = re.findall(
                        r"<svrl:failed-assert[^>]*location=\"([^\"]+)\"[^>]*>.*?<svrl:text>(.*?)</svrl:text>",
                        output,
                        flags=re.DOTALL,
                    )
                    for loc, txt in svrl_ns_matches:
                        msg = re.sub(r"\s+", " ", txt).strip()
                        errors.append(f"{loc} — {msg}")

                if not errors:
                    # Non-namespaced form: <failed-assert location="..."><text>...</text>
                    svrl_matches = re.findall(
                        r"<failed-assert[^>]*location=\"([^\"]+)\"[^>]*>.*?<text>(.*?)</text>",
                        output,
                        flags=re.DOTALL,
                    )
                    for loc, txt in svrl_matches:
                        msg = re.sub(r"\s+", " ", txt).strip()
                        errors.append(f"{loc} — {msg}")

                # 3) If validator prints bracketed fails
                if not errors:
                    for line in output.split("\n"):
                        if line.strip().startswith("[FAIL]"):
                            errors.append(line.strip())

                # 4) Final fallback: include a concise tail of the raw output for visibility
                if not errors:
                    interesting = []
                    for line in output.splitlines():
                        s = line.strip()
                        if any(
                            tok in s.lower()
                            for tok in [
                                "fail",
                                "failed-assert",
                                "error",
                                "assert",
                                "schematron",
                            ]
                        ):
                            interesting.append(s)
                    # Limit to last 20 interesting lines to avoid noise
                    if interesting:
                        errors.extend(interesting[-20:])

                return False, errors if errors else [
                    "Schematron validation failed (no parsable messages; raw output suppressed)"
                ]

            # Ambiguous output but no explicit failure and return code 0
            return True, []

        except subprocess.TimeoutExpired:
            return False, ["Schematron validation timed out"]
        except Exception as e:
            return False, [f"Schematron validation error: {str(e)}"]

    def _validate_python(self, xml_file: str) -> Tuple[bool, List[str]]:
        """Run Python logical validation."""
        try:
            errors = python_logical_validations.validate_file(
                xml_file, self.check_filesystem
            )
            if errors:
                error_messages = [str(err) for err in errors]
                return False, error_messages
            else:
                return True, []
        except Exception as e:
            return False, [f"Python validation error: {str(e)}"]

    def validate_directory(self, directory: str) -> Dict[str, ValidationResult]:
        """
        Validate all XML files in directory.

        Args:
            directory: Path to directory containing XML files

        Returns:
            Dictionary mapping file paths to ValidationResult objects
        """
        xml_files = []
        dir_path = Path(directory)

        if dir_path.is_file():
            xml_files = [dir_path]
        else:
            xml_files = list(dir_path.glob("*.xml"))

        print(f"\n{'=' * 80}")
        print(f"Validating {len(xml_files)} XML files from {directory}")
        print(f"{'=' * 80}\n")

        for xml_file in xml_files:
            print(f"Validating: {xml_file.name}")
            result = self.validate_file(str(xml_file))
            self.results[str(xml_file)] = result
            print()

        return self.results

    def generate_report(self, output_file: str = None):
        """
        Generate validation report.

        Args:
            output_file: Path to output markdown file (prints to stdout if None)
        """
        report_lines = []
        report_lines.append("# AE Validation Pipeline Report")
        report_lines.append("")
        report_lines.append(f"**Total files validated:** {len(self.results)}")

        passed = sum(1 for r in self.results.values() if r.is_valid())
        failed = len(self.results) - passed

        report_lines.append(f"**✅ Passed:** {passed}")
        report_lines.append(f"**❌ Failed:** {failed}")
        report_lines.append("")

        # Summary by validator
        report_lines.append("## Validation Stage Summary")
        report_lines.append("")

        xsd_passed = sum(1 for r in self.results.values() if r.xsd_passed)
        schematron_passed = sum(1 for r in self.results.values() if r.schematron_passed)
        python_passed = sum(1 for r in self.results.values() if r.python_passed)

        report_lines.append(f"- **XSD:** {xsd_passed}/{len(self.results)} passed")
        report_lines.append(
            f"- **Schematron:** {schematron_passed}/{len(self.results)} passed"
        )
        report_lines.append(f"- **Python:** {python_passed}/{len(self.results)} passed")
        report_lines.append("")

        # Per-file results
        report_lines.append("## Per-file Results")
        report_lines.append("")

        for file_path, result in sorted(self.results.items()):
            file_name = Path(file_path).name
            status = (
                "✅ PASS"
                if result.is_valid()
                else f"❌ FAIL ({result.total_errors()} errors)"
            )

            report_lines.append(f"### {file_name} — {status}")
            report_lines.append("")

            # XSD errors
            if not result.xsd_passed:
                report_lines.append("**XSD Errors:**")
                for err in result.xsd_errors:
                    report_lines.append(f"- {err}")
                report_lines.append("")

            # Schematron errors
            if not result.schematron_passed:
                report_lines.append("**Schematron Errors:**")
                for err in result.schematron_errors:
                    report_lines.append(f"- {err}")
                report_lines.append("")

            # Python errors
            if not result.python_passed:
                report_lines.append("**Python Logical Errors:**")
                for err in result.python_errors:
                    report_lines.append(f"- {err}")
                report_lines.append("")

        # Output report
        report_text = "\n".join(report_lines)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report_text)
            print(f"\n📄 Report saved to: {output_file}")
        else:
            print("\n" + "=" * 80)
            print(report_text)
            print("=" * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(
            "Usage: python validation_pipeline.py <xml_file_or_directory> [--check-filesystem] [--report output.md]"
        )
        print("\nExamples:")
        print("  python validation_pipeline.py logical_samples/coreid_mapping.xml")
        print("  python validation_pipeline.py logical_samples/")
        print(
            "  python validation_pipeline.py logical_samples/ --report validation_report.md"
        )
        print(
            "  python validation_pipeline.py logical_samples/ --no-check-filesystem    # disable filesystem checks (ON by default)"
        )
        sys.exit(1)

    target = sys.argv[1]
    # Filesystem checks default to True; allow explicit override via flags
    if "--no-check-filesystem" in sys.argv:
        check_fs = False
    elif "--check-filesystem" in sys.argv:
        check_fs = True
    else:
        check_fs = True

    # Parse report output option
    report_file = None
    if "--report" in sys.argv:
        report_idx = sys.argv.index("--report")
        if report_idx + 1 < len(sys.argv):
            report_file = sys.argv[report_idx + 1]

    # Initialize pipeline
    pipeline = ValidationPipeline(check_filesystem=check_fs)

    # Run validation
    if Path(target).is_file():
        result = pipeline.validate_file(target)
        pipeline.results[target] = result
    else:
        pipeline.validate_directory(target)

    # Generate report
    pipeline.generate_report(report_file)

    # Exit with appropriate code
    all_passed = all(r.is_valid() for r in pipeline.results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
