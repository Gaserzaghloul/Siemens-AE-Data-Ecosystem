from lxml import etree
from lxml.isoschematron import Schematron
import os
import sys


def _load_schematron(sch_path: str) -> Schematron:
    if not os.path.exists(sch_path):
        raise FileNotFoundError(f"Schematron file not found: {sch_path}")
    schematron_doc = etree.parse(sch_path)
    return Schematron(schematron_doc)


def _print_svrl_errors(schematron: Schematron):
    # schematron.error_log often contains SVRL fragments; try to parse for nicer output
    try:
        for entry in schematron.error_log:
            msg = entry.message
            if isinstance(msg, bytes):
                try:
                    msg = msg.decode("utf-8", errors="replace")
                except Exception:
                    msg = str(msg)
            if msg and msg.strip().startswith("<"):
                try:
                    ev = etree.fromstring(
                        msg.encode("utf-8") if isinstance(msg, str) else msg
                    )
                    if ev.tag.endswith("failed-assert") or ev.tag.endswith(
                        "successful-report"
                    ):
                        loc = ev.attrib.get("location")
                        test = ev.attrib.get("test")
                        text_el = ev.find(".//{http://purl.oclc.org/dsdl/svrl}text")
                        text = (
                            text_el.text.strip()
                            if text_el is not None and text_el.text
                            else (ev.text or "").strip()
                        )
                        print(f"  - {loc}: {text}")
                    else:
                        print(f"  - {msg}")
                except Exception:
                    print(f"  - {msg}")
            elif msg:
                print(f"  - {msg}")
    except Exception as e:
        print(f"  - (unable to pretty-print schematron output) {e}")


def _print_svrl_report(schematron: Schematron):
    """Print all failed asserts from the SVRL validation report produced by lxml Schematron.

    This is more reliable than relying on error_log which may not include all failures.
    """
    try:
        report = schematron.validation_report
        if report is None:
            return

        ns = {"svrl": "http://purl.oclc.org/dsdl/svrl"}
        # failed-assert entries
        for f in report.findall(".//svrl:failed-assert", namespaces=ns):
            location = f.get("location", "")
            test = f.get("test", "")
            # Prefer svrl:text content if present
            text_el = f.find("svrl:text", namespaces=ns)
            message = (
                text_el.text.strip() if text_el is not None and text_el.text else ""
            )
            if not message:
                # Fallback to element text or compose a default message
                message = (f.text or "").strip() or f"Assertion failed (test: {test})"
            print(f"  - {location}: {message}")
    except Exception as e:
        print(f"  - (unable to read SVRL report) {e}")


def validate_file(sch_path: str, xml_path: str) -> int:
    """Validate a single XML file against the Schematron at sch_path."""
    try:
        schematron = _load_schematron(sch_path)
    except FileNotFoundError as e:
        print(str(e))
        return 1

    if not os.path.exists(xml_path):
        print(f"XML file not found: {xml_path}")
        return 1
    try:
        xml_doc = etree.parse(xml_path)
    except Exception as e:
        print(f"{os.path.basename(xml_path)}: XML parse error: {e}")
        return 1

    is_valid = schematron.validate(xml_doc)
    fname = os.path.basename(xml_path)
    if is_valid:
        print(f"[PASS] {fname}: Schematron PASSED")
        # Separator for readability
        print("-" * 80)
        return 0
    else:
        print(f"[FAIL] {fname}: Schematron FAILED")
        # Prefer printing the full SVRL report to include all failed-asserts
        _print_svrl_report(schematron)
        # Fallback to error_log if the report didn't yield anything
        _print_svrl_errors(schematron)
        print("-" * 80)
        return 2


def validate_directory(sch_path="rules.sch", xml_dir="sch_samples"):
    """Validate all .xml files in xml_dir against the Schematron at sch_path."""
    try:
        schematron = _load_schematron(sch_path)
    except FileNotFoundError as e:
        print(str(e))
        return 1
    if not os.path.isdir(xml_dir):
        print(f"XML samples directory not found: {xml_dir}")
        return 1

    total = 0
    invalid = 0
    for fname in sorted(os.listdir(xml_dir)):
        if not fname.lower().endswith(".xml"):
            continue
        total += 1
        path = os.path.join(xml_dir, fname)
        try:
            xml_doc = etree.parse(path)
        except Exception as e:
            print(f"{fname}: XML parse error: {e}")
            invalid += 1
            print("-" * 80)
            continue

        is_valid = schematron.validate(xml_doc)
        if is_valid:
            print(f"[PASS] {fname}: Schematron PASSED")
        else:
            print(f"[FAIL] {fname}: Schematron FAILED")
            _print_svrl_errors(schematron)
            invalid += 1
        print("-" * 80)

    print("\nSummary:")
    print(f"  Total files checked: {total}")
    print(f"  Files failed Schematron: {invalid}")
    return 0 if invalid == 0 else 2


if __name__ == "__main__":
    # CLI: python schematronValidator.py [schematron_file] [xml_file_or_directory]
    args = sys.argv[1:]
    sch = args[0] if len(args) > 0 else "rules.sch"
    target = args[1] if len(args) > 1 else "logical_samples"
    if os.path.isdir(target):
        sys.exit(validate_directory(sch, target))
    else:
        sys.exit(validate_file(sch, target))
