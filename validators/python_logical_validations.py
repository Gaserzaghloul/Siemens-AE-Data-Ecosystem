import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from lxml import etree


class ValidationError:
    """Represents a single validation error."""

    def __init__(
        self,
        rule_number: int,
        severity: str,
        message: str,
        xpath: str = "",
        line_number: int = 0,
    ):
        self.rule_number = rule_number
        self.severity = severity  # 'error', 'warning'
        self.message = message
        self.xpath = xpath
        self.line_number = line_number

    def __repr__(self):
        return f"Rule {self.rule_number} [{self.severity}]: {self.message} (at {self.xpath})"


class PythonLogicalValidator:
    # ============================================================================
    # Rule 75: Each CPU cluster running Nucleus OS must be mapped to a runnable
    # ============================================================================
    def _validate_rule_75(self):
        """
        Rule 75: Each CPU cluster running Nucleus OS must be mapped to a runnable.
        For every CPU_Cluster with Nucleus_RTOS, check if there is a Core-Runnable-Mapping for that cluster.
        """
        # Find all clusters running Nucleus_RTOS
        nucleus_clusters = self.root.xpath(
            "//CPU_Cluster[Operating-System/Nucleus_RTOS]"
        )
        # Build set of cluster names that are referenced by Core-Runnable-Mapping via the parent HW-SW-MAPPING/@ClusterRef
        mapped_cluster_names = set()

        for hw_sw_mapping in self.root.xpath("//HW-SW-MAPPING[@ClusterRef]"):
            cluster_ref = (hw_sw_mapping.get("ClusterRef") or "").strip()
            if not cluster_ref:
                continue
            # If this HW-SW-MAPPING contains at least one Core-Runnable-Mapping child, consider the cluster mapped
            core_mappings = hw_sw_mapping.xpath(
                "Core-Runnable-Mapping | CoreRunnableMapping"
            )
            if core_mappings:
                # Normalize the cluster short-name as the final path segment
                parts = [p for p in cluster_ref.split("/") if p]
                if parts:
                    mapped_cluster_names.add(parts[-1])

        for cluster in nucleus_clusters:
            # Get cluster short name (search anywhere under the CPU_Cluster element)
            short_name_nodes = cluster.xpath(".//SHORT-NAME/@name")
            if not short_name_nodes:
                continue
            cluster_short = short_name_nodes[0]

            if cluster_short not in mapped_cluster_names:
                xpath = self.tree.getpath(cluster)
                self.errors.append(
                    ValidationError(
                        rule_number=75,
                        severity="error",
                        message=f"CPU_Cluster '{cluster_short}' running Nucleus_RTOS is not mapped to any runnable.",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 33: Inter-Chiplet Provider must be 'host' UCIe mode
    # ============================================================================
    def _validate_rule_33(self):
        """
        Rule 33: Each Sender-Receiver interface, when used across chiplets (inter-chiplet),
        requires the Provider's SoC to have UCIe-INTERFACE Mode='host'.

        Detection approach (XSD-aligned, no Network-Topology dependency):
        1) For each SRI, find provider SWCs (P-PORT) and consumer SWCs (R-PORT).
        2) Resolve HW-SW-MAPPINGs to find SoC(s) hosting provider runnables and consumer runnables.
        3) If any provider SoC and consumer SoC differ (cross-SoC use), and UCIe is present,
           treat it as inter-chiplet usage and enforce Provider SoC UCIe Mode == 'host'.
        4) Report an error per violating Core-Runnable-Mapping.
        """

        # Helper: resolve ClusterRef -> SoC element and name
        def resolve_soc_from_clusterref(
            cluster_ref: str,
        ) -> tuple[Optional[etree._Element], str]:
            cluster_name = self._extract_short_name_from_dest(cluster_ref)
            # Find the CPU_Cluster that contains this SHORT-NAME
            cluster_elems = self.root.xpath(
                f"//CPU_Cluster[.//SHORT-NAME/@name='{cluster_name}']"
            )
            if not cluster_elems:
                return None, "(unknown)"
            soc_elems = cluster_elems[0].xpath("ancestor::SoCs")
            if not soc_elems:
                return None, "(unknown)"
            soc = soc_elems[0]
            soc_name_nodes = soc.xpath("SHORT-NAME/@name") or soc.xpath(
                "SHORT-NAME/text()"
            )
            soc_name = soc_name_nodes[0] if soc_name_nodes else "(unknown)"
            return soc, soc_name

        # Build SRI -> provider/consumer runnables (need to distinguish by data access, not just SWC)
        # A runnable is a provider if it has DATA-WRITE-ACCESS to the SRI
        # A runnable is a consumer if it has DATA-READ-ACCESS to the SRI
        sri_to_provider_runnables: Dict[
            str, Set[str]
        ] = {}  # SRI -> set of runnable SHORT-NAMEs (providers)
        sri_to_consumer_runnables: Dict[
            str, Set[str]
        ] = {}  # SRI -> set of runnable SHORT-NAMEs (consumers)

        for swc in self.root.xpath("//APPLICATION-SW-COMPONENT-TYPE"):
            swc_name_nodes = swc.xpath("SHORT-NAME/@name")
            if not swc_name_nodes:
                continue
            swc_name = swc_name_nodes[0]

            # For each P-PORT (provider port), find which runnables write to it
            for p in swc.xpath(".//P-PORT-PROTOTYPE"):
                port_name_nodes = p.xpath("SHORT-NAME/@name")
                if not port_name_nodes:
                    continue
                port_name = port_name_nodes[0]

                for dest in p.xpath("PROVIDED-INTERFACE-TREF/@DEST"):
                    sri_name = self._extract_short_name_from_dest(dest)

                    # Find runnables with DATA-WRITE-ACCESS referencing this port
                    for runnable in swc.xpath(".//RUNNABLE-ENTITY"):
                        runnable_name_nodes = runnable.xpath("SHORT-NAME/@name")
                        if not runnable_name_nodes:
                            continue
                        runnable_name = runnable_name_nodes[0]

                        # Check if this runnable writes to the provider port
                        for write_access in runnable.xpath(".//DATA-WRITE-ACCESS"):
                            port_refs = write_access.xpath(
                                ".//PORT-PROTOTYPE-REF/@DEST"
                            )
                            for ref in port_refs:
                                # Does this reference match our provider port?
                                if f"/{swc_name}/{port_name}" == ref or ref.endswith(
                                    f"/{swc_name}/{port_name}"
                                ):
                                    sri_to_provider_runnables.setdefault(
                                        sri_name, set()
                                    ).add(runnable_name)

            # For each R-PORT (consumer port), find which runnables read from it
            for r in swc.xpath(".//R-PORT-PROTOTYPE"):
                port_name_nodes = r.xpath("SHORT-NAME/@name")
                if not port_name_nodes:
                    continue
                port_name = port_name_nodes[0]

                for dest in r.xpath("REQUIRED-INTERFACE-TREF/@DEST"):
                    sri_name = self._extract_short_name_from_dest(dest)

                    # Find runnables with DATA-READ-ACCESS referencing this port
                    for runnable in swc.xpath(".//RUNNABLE-ENTITY"):
                        runnable_name_nodes = runnable.xpath("SHORT-NAME/@name")
                        if not runnable_name_nodes:
                            continue
                        runnable_name = runnable_name_nodes[0]

                        # Check if this runnable reads from the consumer port
                        for read_access in runnable.xpath(".//DATA-READ-ACCESS"):
                            port_refs = read_access.xpath(".//PORT-PROTOTYPE-REF/@DEST")
                            for ref in port_refs:
                                # Does this reference match our consumer port?
                                if f"/{swc_name}/{port_name}" == ref or ref.endswith(
                                    f"/{swc_name}/{port_name}"
                                ):
                                    sri_to_consumer_runnables.setdefault(
                                        sri_name, set()
                                    ).add(runnable_name)

        # Build mapping from RunnableRef to runnable SHORT-NAME
        def extract_runnable_from_ref(runnable_ref: str) -> Optional[str]:
            path = self._normalize_dest_path(runnable_ref)
            parts = path.split("/")
            # Path format: /SWC/Behavior/Runnable
            if len(parts) >= 3:
                return parts[2] if parts[2] else None
            return None

        # For each SRI, find cross-SoC provider vs consumer mappings
        for sri_name in self.sri_index.keys():
            provider_runnables = sri_to_provider_runnables.get(sri_name, set())
            consumer_runnables = sri_to_consumer_runnables.get(sri_name, set())
            if not provider_runnables or not consumer_runnables:
                continue  # need both sides to reason about cross-chip usage

            # Collect SoCs hosting provider runnables and consumer runnables
            provider_soc_by_crm: List[
                Tuple[etree._Element, str, etree._Element]
            ] = []  # (crm, runnable_name, soc_elem)
            consumer_socs: Set[str] = set()

            for mapping in self.root.xpath("//HW-SW-MAPPING"):
                cluster_ref = mapping.get("ClusterRef", "").strip()
                if not cluster_ref:
                    continue
                soc_elem, soc_name = resolve_soc_from_clusterref(cluster_ref)
                if soc_elem is None:
                    continue

                for crm in mapping.xpath("Core-Runnable-Mapping"):
                    runnable_ref = crm.get("RunnableRef", "").strip()
                    runnable_name = extract_runnable_from_ref(runnable_ref)
                    if not runnable_name:
                        continue
                    if runnable_name in provider_runnables:
                        provider_soc_by_crm.append((crm, runnable_name, soc_elem))
                    if runnable_name in consumer_runnables:
                        consumer_socs.add(soc_name)

            # For each provider mapping, if any consumer is on a different SoC, enforce mode
            for crm, runnable_name, prov_soc in provider_soc_by_crm:
                prov_soc_name_nodes = prov_soc.xpath(
                    "SHORT-NAME/@name"
                ) or prov_soc.xpath("SHORT-NAME/text()")
                prov_soc_name = (
                    prov_soc_name_nodes[0] if prov_soc_name_nodes else "(unknown)"
                )

                # If there's at least one consumer on a different SoC, consider inter-chiplet
                if consumer_socs and (prov_soc_name not in consumer_socs):
                    ucie_if = prov_soc.xpath("UCIe-INTERFACE")
                    if ucie_if:
                        mode = ucie_if[0].get("Mode", "host")
                        if mode != "host":
                            xpath = self.tree.getpath(crm)
                            self.errors.append(
                                ValidationError(
                                    rule_number=33,
                                    severity="error",
                                    message=(
                                        f"Rule 33 violated: SoC '{prov_soc_name}' running Runnable '{runnable_name}' as Provider "
                                        f"for SRI '{sri_name}' in inter-chiplet use has UCIe-INTERFACE Mode='{mode}' "
                                        f"(should be 'host')."
                                    ),
                                    xpath=xpath,
                                )
                            )

    # ============================================================================
    # Rule 22: Each Read Operation has a valid Data Access reference
    # ============================================================================
    def _validate_data_access_operation(self, operation_type: str, rule_number: int):
        """
        Generic validator for READ/WRITE operations with Data Access references.

        This validates SWC operations only (not HWIP operations).
        HWIP operations are validated by Rule 59.

        Args:
            operation_type: "READ" or "WRITE"
            rule_number: 22 for READ, 23 for WRITE
        """
        # Build set of valid DATA-{operation_type}-ACCESS references
        access_type = f"DATA-{operation_type}-ACCESS"
        valid_data_access = set()
        for data_access in self.root.xpath(f"//{access_type}/VARIABLE-ACCESS"):
            name_nodes = data_access.xpath("SHORT-NAME/@name")
            if name_nodes:
                valid_data_access.add(name_nodes[0])

        # Validate each SWC operation (not HWIP operations)
        # SWC operations are in SWC-INTERNAL-BEHAVIOR/OPERATIONS-SEQUENCE
        # HWIP operations are in Generic_Hardware/INTERNAL-BEHAVIOR/OPERATIONS-SEQUENCE (handled by Rule 59)
        for operation in self.root.xpath(
            f"//SWC-INTERNAL-BEHAVIOR/OPERATIONS-SEQUENCE//{operation_type}"
        ):
            xpath = self.tree.getpath(operation)
            iref = operation.find("IREF")

            # Check 1: IREF exists
            if iref is None:
                self.errors.append(
                    ValidationError(
                        rule_number=rule_number,
                        severity="error",
                        message=f"{operation_type} operation missing IREF child.",
                        xpath=xpath,
                    )
                )
                continue

            # Check 2: DEST is non-empty
            dest = iref.get("DEST", "").strip()
            if not dest:
                self.errors.append(
                    ValidationError(
                        rule_number=rule_number,
                        severity="error",
                        message=f"{operation_type} operation IREF has empty DEST attribute.",
                        xpath=xpath,
                    )
                )
                continue

            # Check 3: DEST resolves to existing DATA-{operation_type}-ACCESS
            dest_name = dest.split("/")[-1]  # Extract last path component
            if dest_name not in valid_data_access:
                self.errors.append(
                    ValidationError(
                        rule_number=rule_number,
                        severity="error",
                        message=f"{operation_type} operation IREF DEST='{dest}' does not resolve to any {access_type} SHORT-NAME.",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 46: Each SoC name is valid against C variable naming rules
    # ============================================================================
    def _validate_rule_46(self):
        """
        Rule 46: SoC SHORT-NAME/@name must be a valid C identifier.

        Uses the shared _validate_c_identifier helper to enforce:
        - Pattern ^[a-zA-Z_][a-zA-Z0-9_]*$
        - Not a reserved C keyword
        """
        for soc in self.root.xpath("//ECUs/SoCs"):
            name_nodes = soc.xpath("SHORT-NAME/@name")
            if not name_nodes:
                continue
            name = name_nodes[0]
            is_valid, error_msg = self._validate_c_identifier(name)
            if not is_valid:
                xpath = self.tree.getpath(soc)
                self.errors.append(
                    ValidationError(
                        rule_number=46,
                        severity="error",
                        message=f"SoC name '{name}' {error_msg}",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 52: Each Chiplet name is valid against C variable naming rules
    # ============================================================================
    def _validate_rule_52(self):
        """
        Rule 52: Chiplet SHORT-NAME/@name must be a valid C identifier.

        Uses the shared _validate_c_identifier helper to enforce:
        - Pattern ^[a-zA-Z_][a-zA-Z0-9_]*$
        - Not a reserved C keyword
        """
        for chiplet in self.root.xpath("//Chiplet"):
            name_nodes = chiplet.xpath("SHORT-NAME/@name")
            if not name_nodes:
                continue
            name = name_nodes[0]
            is_valid, error_msg = self._validate_c_identifier(name)
            if not is_valid:
                xpath = self.tree.getpath(chiplet)
                self.errors.append(
                    ValidationError(
                        rule_number=52,
                        severity="error",
                        message=f"Chiplet name '{name}' {error_msg}",
                        xpath=xpath,
                    )
                )

    def _validate_rule_56(self):
        """
        Rule 56: Each HWIP (Generic_Hardware) SHORT-NAME/@name must be a valid C identifier.

        Uses the shared _validate_c_identifier helper to enforce:
        - Pattern ^[a-zA-Z_][a-zA-Z0-9_]*$
        - Not a reserved C keyword
        """
        for hwip in self.root.xpath("//Generic_Hardware"):
            name_nodes = hwip.xpath("SHORT-NAME/@name")
            if not name_nodes:
                continue
            name = name_nodes[0]
            is_valid, error_msg = self._validate_c_identifier(name)
            if not is_valid:
                xpath = self.tree.getpath(hwip)
                self.errors.append(
                    ValidationError(
                        rule_number=56,
                        severity="error",
                        message=f"Generic_Hardware (HWIP) name '{name}' {error_msg}",
                        xpath=xpath,
                    )
                )

    def _validate_rule_59(self):
        """
        Rule 59: Each HWIP Port is connected to at least one valid operation.

        For each P-PORT-PROTOTYPE in Generic_Hardware:
        - Must be referenced by at least one WRITE operation (IREF DEST matches port path)

        For each R-PORT-PROTOTYPE in Generic_Hardware:
        - Must be referenced by at least one READ operation (IREF DEST matches port path)

        Implementation:
        - Schematron (lines 613-633): Basic check using contains() for port name in IREF DEST
        - Python (this function): Validates exact path matching /hwip-name/port-name

        Why Python: Requires path normalization and exact matching of IREF DEST to port path.
        """
        for hwip in self.root.xpath("//Generic_Hardware"):
            hwip_name_nodes = hwip.xpath("SHORT-NAME/@name")
            if not hwip_name_nodes:
                continue
            hwip_name = hwip_name_nodes[0]

            # Check P-PORT-PROTOTYPE (must have WRITE operations)
            for p_port in hwip.xpath(".//INTERNAL-BEHAVIOR/PORTS/P-PORT-PROTOTYPE"):
                port_name_nodes = p_port.xpath("SHORT-NAME/@name")
                if not port_name_nodes:
                    continue
                port_name = port_name_nodes[0]

                # Expected path format: hwip-name/port-name (normalized without leading slash)
                expected_path = f"{hwip_name}/{port_name}"

                # Find all WRITE operations in this HWIP
                write_operations = hwip.xpath(
                    ".//OPERATIONS-SEQUENCE//WRITE/IREF/@DEST"
                )

                # Check if any WRITE operation references this port
                port_referenced = False
                for dest in write_operations:
                    normalized_dest = self._normalize_dest_path(dest)
                    if normalized_dest == expected_path:
                        port_referenced = True
                        break

                if not port_referenced:
                    xpath = self.tree.getpath(p_port)
                    self.errors.append(
                        ValidationError(
                            rule_number=59,
                            severity="error",
                            message=f"HWIP Provider port '{port_name}' in Generic_Hardware '{hwip_name}' is not referenced by any WRITE operation. Each HWIP port must be connected to at least one operation.",
                            xpath=xpath,
                        )
                    )

            # Check R-PORT-PROTOTYPE (must have READ operations)
            for r_port in hwip.xpath(".//INTERNAL-BEHAVIOR/PORTS/R-PORT-PROTOTYPE"):
                port_name_nodes = r_port.xpath("SHORT-NAME/@name")
                if not port_name_nodes:
                    continue
                port_name = port_name_nodes[0]

                # Expected path format: hwip-name/port-name (normalized without leading slash)
                expected_path = f"{hwip_name}/{port_name}"

                # Find all READ operations in this HWIP
                read_operations = hwip.xpath(".//OPERATIONS-SEQUENCE//READ/IREF/@DEST")

                # Check if any READ operation references this port
                port_referenced = False
                for dest in read_operations:
                    normalized_dest = self._normalize_dest_path(dest)
                    if normalized_dest == expected_path:
                        port_referenced = True
                        break

                if not port_referenced:
                    xpath = self.tree.getpath(r_port)
                    self.errors.append(
                        ValidationError(
                            rule_number=59,
                            severity="error",
                            message=f"HWIP Required port '{port_name}' in Generic_Hardware '{hwip_name}' is not referenced by any READ operation. Each HWIP port must be connected to at least one operation.",
                            xpath=xpath,
                        )
                    )

    def _validate_rule_60(self):
        """
        Rule 60: Each Hwip can NOT have provider and required ports connected to the same Sender-Receiver Interface.

        For each Generic_Hardware (HWIP), check that no SRI is referenced by BOTH:
        - A P-PORT-PROTOTYPE (via PROVIDED-INTERFACE-TREF/@DEST)
        - An R-PORT-PROTOTYPE (via REQUIRED-INTERFACE-TREF/@DEST)
        """
        hwips = self.root.xpath("//Generic_Hardware")

        for hwip in hwips:
            hwip_name_nodes = hwip.xpath("SHORT-NAME/@name")
            if not hwip_name_nodes:
                continue
            hwip_name = hwip_name_nodes[0]

            # Collect all SRIs referenced by P-PORTs
            p_port_sris = {}  # SRI path -> list of P-PORT names
            p_ports = hwip.xpath(".//INTERNAL-BEHAVIOR/PORTS/P-PORT-PROTOTYPE")
            for p_port in p_ports:
                port_name_nodes = p_port.xpath("SHORT-NAME/@name")
                sri_nodes = p_port.xpath("PROVIDED-INTERFACE-TREF/@DEST")

                if port_name_nodes and sri_nodes:
                    port_name = port_name_nodes[0]
                    sri_path = sri_nodes[0]

                    if sri_path not in p_port_sris:
                        p_port_sris[sri_path] = []
                    p_port_sris[sri_path].append(port_name)

            # Collect all SRIs referenced by R-PORTs
            r_port_sris = {}  # SRI path -> list of R-PORT names
            r_ports = hwip.xpath(".//INTERNAL-BEHAVIOR/PORTS/R-PORT-PROTOTYPE")
            for r_port in r_ports:
                port_name_nodes = r_port.xpath("SHORT-NAME/@name")
                sri_nodes = r_port.xpath("REQUIRED-INTERFACE-TREF/@DEST")

                if port_name_nodes and sri_nodes:
                    port_name = port_name_nodes[0]
                    sri_path = sri_nodes[0]

                    if sri_path not in r_port_sris:
                        r_port_sris[sri_path] = []
                    r_port_sris[sri_path].append(port_name)

            # Find SRIs that appear in BOTH P-PORT and R-PORT sets
            shared_sris = set(p_port_sris.keys()) & set(r_port_sris.keys())

            for sri_path in shared_sris:
                # Report violation with detailed information
                p_port_names = ", ".join(p_port_sris[sri_path])
                r_port_names = ", ".join(r_port_sris[sri_path])

                xpath = self.tree.getpath(hwip)
                self.errors.append(
                    ValidationError(
                        rule_number=60,
                        severity="error",
                        message=f"HWIP '{hwip_name}' violates Rule 60: Both P-PORT(s) [{p_port_names}] and R-PORT(s) [{r_port_names}] are connected to the same SRI '{sri_path}'. Each HWIP can NOT have provider and required ports connected to the same Sender-Receiver Interface.",
                        xpath=xpath,
                    )
                )

    def _validate_rule_62(self):
        """
        Rule 62: Each Hwip Operations are valid.

        Validates that operations are **well-formed** and have **valid internal values**:
        1. READ/WRITE operations:
           - Must have IREF child element
           - IREF must have non-empty DEST attribute
           (Port resolution/connectivity is checked in Rule 63)

        2. CUSTOM-OPERATION: Already validated by Rule 25

        3. ML operations (CONVOLUTION, BATCH-NORMALIZATION, etc.):
           - Dimension attributes (height, width, channels) must be non-zero

        4. LATENCY: value must be non-zero (semantic validity)
        5. LOAD: value must be non-zero
        """
        hwips = self.root.xpath("//Generic_Hardware")

        for hwip in hwips:
            hwip_name_nodes = hwip.xpath("SHORT-NAME/@name")
            if not hwip_name_nodes:
                continue
            hwip_name = hwip_name_nodes[0]

            # Validate each operation in OPERATIONS-SEQUENCE
            for operation in hwip.xpath(
                ".//INTERNAL-BEHAVIOR/OPERATIONS-SEQUENCE/OPERATION"
            ):
                # Check WRITE operations - basic structure only
                for write_elem in operation.xpath("WRITE"):
                    iref = write_elem.find("IREF")
                    if iref is None:
                        xpath = self.tree.getpath(write_elem)
                        self.errors.append(
                            ValidationError(
                                rule_number=62,
                                severity="error",
                                message=f"WRITE operation in HWIP '{hwip_name}' must have an IREF child.",
                                xpath=xpath,
                            )
                        )
                        continue

                    dest = iref.get("DEST", "").strip()
                    if not dest:
                        xpath = self.tree.getpath(write_elem)
                        self.errors.append(
                            ValidationError(
                                rule_number=62,
                                severity="error",
                                message=f"WRITE operation in HWIP '{hwip_name}' has empty IREF DEST attribute.",
                                xpath=xpath,
                            )
                        )

                # Check READ operations - basic structure only
                for read_elem in operation.xpath("READ"):
                    iref = read_elem.find("IREF")
                    if iref is None:
                        xpath = self.tree.getpath(read_elem)
                        self.errors.append(
                            ValidationError(
                                rule_number=62,
                                severity="error",
                                message=f"READ operation in HWIP '{hwip_name}' must have an IREF child.",
                                xpath=xpath,
                            )
                        )
                        continue

                    dest = iref.get("DEST", "").strip()
                    if not dest:
                        xpath = self.tree.getpath(read_elem)
                        self.errors.append(
                            ValidationError(
                                rule_number=62,
                                severity="error",
                                message=f"READ operation in HWIP '{hwip_name}' has empty IREF DEST attribute.",
                                xpath=xpath,
                            )
                        )

                # Check ML operations for valid dimensions
                # All ML operations defined in XSD schema that use AeInputImageType attribute group
                ml_ops = [
                    "CONVOLUTION",
                    "BATCH-NORMALIZATION",
                    "HARDMAX",
                    "LOG-SOFTMAX",
                    "MAX-POOL",
                    "AVG-POOL",
                    "TRANSPOSED-CONVOLUTION",
                ]

                for ml_op_name in ml_ops:
                    for ml_op in operation.xpath(ml_op_name):
                        # Check dimension attributes
                        height = ml_op.get("height", "1024")
                        width = ml_op.get("width", "1024")
                        channels = ml_op.get("channels", "3")

                        try:
                            if (
                                int(height) == 0
                                or int(width) == 0
                                or int(channels) == 0
                            ):
                                xpath = self.tree.getpath(ml_op)
                                self.errors.append(
                                    ValidationError(
                                        rule_number=62,
                                        severity="error",
                                        message=f"{ml_op_name} operation in HWIP '{hwip_name}' has invalid dimensions (height={height}, width={width}, channels={channels}). All dimensions must be non-zero.",
                                        xpath=xpath,
                                    )
                                )
                        except ValueError:
                            xpath = self.tree.getpath(ml_op)
                            self.errors.append(
                                ValidationError(
                                    rule_number=62,
                                    severity="error",
                                    message=f"{ml_op_name} operation in HWIP '{hwip_name}' has non-numeric dimension attributes.",
                                    xpath=xpath,
                                )
                            )

                # Check LATENCY operations
                for latency in operation.xpath("LATENCY"):
                    value = latency.get("value", "0")
                    try:
                        if int(value) == 0:
                            xpath = self.tree.getpath(latency)
                            self.errors.append(
                                ValidationError(
                                    rule_number=62,
                                    severity="error",
                                    message=f"LATENCY operation in HWIP '{hwip_name}' has zero value. Latency must be non-zero.",
                                    xpath=xpath,
                                )
                            )
                    except ValueError:
                        pass  # XSD already validates this is a number

                # Check LOAD operations
                for load in operation.xpath("LOAD"):
                    value = load.get("value", "0")
                    try:
                        if int(value) == 0:
                            xpath = self.tree.getpath(load)
                            self.errors.append(
                                ValidationError(
                                    rule_number=62,
                                    severity="error",
                                    message=f"LOAD operation in HWIP '{hwip_name}' has zero value. Load cycles must be non-zero.",
                                    xpath=xpath,
                                )
                            )
                    except ValueError:
                        pass  # XSD already validates this is a number

    def _validate_rule_63(self):
        """
        Rule 63: Each Hwip Read/Write operation is connected to a valid port.

        Validates that READ/WRITE operations in HWIP are **connected** to valid ports:
        1. DEST must resolve to an actual port in the same HWIP
        2. READ must point to R-PORT-PROTOTYPE (semantic correctness)
        3. WRITE must point to P-PORT-PROTOTYPE (semantic correctness)

        This is separate from Rule 62 which validates operations are well-formed.
        Rule 62 = operations are VALID (structure/values)
        Rule 63 = operations are CONNECTED (port resolution/semantics)
        """
        hwips = self.root.xpath("//Generic_Hardware")

        for hwip in hwips:
            hwip_name_nodes = hwip.xpath("SHORT-NAME/@name")
            if not hwip_name_nodes:
                continue
            hwip_name = hwip_name_nodes[0]

            # Build a map of port names in this HWIP
            p_ports = {}  # port_name -> port_element
            r_ports = {}  # port_name -> port_element

            for p_port in hwip.xpath(".//INTERNAL-BEHAVIOR/PORTS/P-PORT-PROTOTYPE"):
                port_name_nodes = p_port.xpath("SHORT-NAME/@name")
                if port_name_nodes:
                    p_ports[port_name_nodes[0]] = p_port

            for r_port in hwip.xpath(".//INTERNAL-BEHAVIOR/PORTS/R-PORT-PROTOTYPE"):
                port_name_nodes = r_port.xpath("SHORT-NAME/@name")
                if port_name_nodes:
                    r_ports[port_name_nodes[0]] = r_port

            # Check READ/WRITE operations for port connectivity
            for operation in hwip.xpath(
                ".//INTERNAL-BEHAVIOR/OPERATIONS-SEQUENCE/OPERATION"
            ):
                # Check WRITE operations - port connectivity
                for write_elem in operation.xpath("WRITE"):
                    iref = write_elem.find("IREF")
                    if iref is None:
                        continue  # Already caught by Rule 62

                    dest = iref.get("DEST", "").strip()
                    if not dest:
                        continue  # Already caught by Rule 62

                    # Validate DEST resolves to a port in this HWIP
                    # Expected format: /HWIP_name/port_name
                    port_name = dest.split("/")[-1]

                    # WRITE must point to P-PORT
                    if port_name not in p_ports:
                        # Check if it points to R-PORT (semantic error)
                        if port_name in r_ports:
                            xpath = self.tree.getpath(write_elem)
                            self.errors.append(
                                ValidationError(
                                    rule_number=63,
                                    severity="error",
                                    message=f"WRITE operation in HWIP '{hwip_name}' points to R-PORT '{port_name}'. WRITE operations must reference P-PORT-PROTOTYPE only.",
                                    xpath=xpath,
                                )
                            )
                        else:
                            xpath = self.tree.getpath(write_elem)
                            self.errors.append(
                                ValidationError(
                                    rule_number=63,
                                    severity="error",
                                    message=f"WRITE operation in HWIP '{hwip_name}' references non-existent port '{port_name}' (DEST='{dest}').",
                                    xpath=xpath,
                                )
                            )

                # Check READ operations - port connectivity
                for read_elem in operation.xpath("READ"):
                    iref = read_elem.find("IREF")
                    if iref is None:
                        continue  # Already caught by Rule 62

                    dest = iref.get("DEST", "").strip()
                    if not dest:
                        continue  # Already caught by Rule 62

                    # Validate DEST resolves to a port in this HWIP
                    port_name = dest.split("/")[-1]

                    # READ must point to R-PORT
                    if port_name not in r_ports:
                        # Check if it points to P-PORT (semantic error)
                        if port_name in p_ports:
                            xpath = self.tree.getpath(read_elem)
                            self.errors.append(
                                ValidationError(
                                    rule_number=63,
                                    severity="error",
                                    message=f"READ operation in HWIP '{hwip_name}' points to P-PORT '{port_name}'. READ operations must reference R-PORT-PROTOTYPE only.",
                                    xpath=xpath,
                                )
                            )
                        else:
                            xpath = self.tree.getpath(read_elem)
                            self.errors.append(
                                ValidationError(
                                    rule_number=63,
                                    severity="error",
                                    message=f"READ operation in HWIP '{hwip_name}' references non-existent port '{port_name}' (DEST='{dest}').",
                                    xpath=xpath,
                                )
                            )

    def _validate_rule_64(self):
        """
        Rule 64: Each Hwip Data Received event is connected to a valid port.

        Validates that DATA-RECEIVED-EVENT elements in HWIP are connected to valid ports:
        1. REQUIRED-PORT-TREF must resolve to an actual port in the same HWIP
        2. REQUIRED-PORT-TREF must point to R-PORT-PROTOTYPE (semantic correctness)
        3. REQUIRED-PORT-TREF must not be empty (structural)

        Similar to Rule 63, requires Python for reference resolution and semantic checks.
        """
        hwips = self.root.xpath("//Generic_Hardware")

        for hwip in hwips:
            hwip_name_nodes = hwip.xpath("SHORT-NAME/@name")
            if not hwip_name_nodes:
                continue
            hwip_name = hwip_name_nodes[0]

            # Build a map of port names in this HWIP
            p_ports = {}  # port_name -> port_element
            r_ports = {}  # port_name -> port_element

            for p_port in hwip.xpath(".//INTERNAL-BEHAVIOR/PORTS/P-PORT-PROTOTYPE"):
                port_name_nodes = p_port.xpath("SHORT-NAME/@name")
                if port_name_nodes:
                    p_ports[port_name_nodes[0]] = p_port

            for r_port in hwip.xpath(".//INTERNAL-BEHAVIOR/PORTS/R-PORT-PROTOTYPE"):
                port_name_nodes = r_port.xpath("SHORT-NAME/@name")
                if port_name_nodes:
                    r_ports[port_name_nodes[0]] = r_port

            # Check DATA-RECEIVED-EVENT elements for port connectivity
            # Note: XSD uses EVENT (singular) not EVENTS (plural)
            for event in hwip.xpath(".//INTERNAL-BEHAVIOR/EVENT/DATA-RECEIVED-EVENT"):
                event_name_nodes = event.xpath("SHORT-NAME/@name")
                event_name = event_name_nodes[0] if event_name_nodes else "(unnamed)"

                for port_tref in event.xpath("REQUIRED-PORT-TREF"):
                    port_ref = port_tref.get("DEST", "").strip()

                    # Check for empty reference (structural issue)
                    if not port_ref:
                        xpath = self.tree.getpath(port_tref)
                        self.errors.append(
                            ValidationError(
                                rule_number=64,
                                severity="error",
                                message=f"DATA-RECEIVED-EVENT in HWIP '{hwip_name}' has empty REQUIRED-PORT-TREF.",
                                xpath=xpath,
                            )
                        )
                        continue

                    # Extract port name from reference path
                    # Format can be: /HWIP_name/port_name OR /HWIP_name/HWIP_Behavior/PORTS/port_name
                    port_name = port_ref.split("/")[-1]

                    # DATA-RECEIVED-EVENT must reference R-PORT (required port)
                    if port_name not in r_ports:
                        # Check if it points to P-PORT (semantic error)
                        if port_name in p_ports:
                            xpath = self.tree.getpath(event)
                            self.errors.append(
                                ValidationError(
                                    rule_number=64,
                                    severity="error",
                                    message=f"DATA-RECEIVED-EVENT in HWIP '{hwip_name}' references P-PORT '{port_name}'. DATA-RECEIVED-EVENT must reference R-PORT-PROTOTYPE only (REQUIRED-PORT-TREF='{port_ref}').",
                                    xpath=xpath,
                                )
                            )
                        else:
                            xpath = self.tree.getpath(event)
                            self.errors.append(
                                ValidationError(
                                    rule_number=64,
                                    severity="error",
                                    message=f"DATA-RECEIVED-EVENT in HWIP '{hwip_name}' references non-existent port '{port_name}' (REQUIRED-PORT-TREF='{port_ref}').",
                                    xpath=xpath,
                                )
                            )

    def _validate_rule_65(self):
        """
        Rule 65: Each Hwip Trigger event is connected to a valid Runnable/Event.

        Validates that TRIGGER-EVENT elements in HWIP reference valid targets:
        1. TRIGGER DEST must resolve to an existing element
        2. Target should be a RUNNABLE-ENTITY, TIMING-EVENT, DATA-RECEIVED-EVENT, or OPERATION
        3. TRIGGER DEST must not be empty (structural)

        Requires Python for reference resolution across the document.
        """
        hwips = self.root.xpath("//Generic_Hardware")

        for hwip in hwips:
            hwip_name_nodes = hwip.xpath("SHORT-NAME/@name")
            if not hwip_name_nodes:
                continue
            hwip_name = hwip_name_nodes[0]

            # Check TRIGGER-EVENT elements
            for trigger_event in hwip.xpath(".//INTERNAL-BEHAVIOR/EVENT/TRIGGER-EVENT"):
                trigger_elem = trigger_event.find("TRIGGER")
                if trigger_elem is None:
                    continue

                trigger_dest = trigger_elem.get("DEST", "").strip()

                # Check for empty reference (structural issue)
                if not trigger_dest:
                    xpath = self.tree.getpath(trigger_elem)
                    self.errors.append(
                        ValidationError(
                            rule_number=65,
                            severity="error",
                            message=f"TRIGGER-EVENT in HWIP '{hwip_name}' has empty TRIGGER DEST.",
                            xpath=xpath,
                        )
                    )
                    continue

                # Try to resolve the reference
                # The DEST could point to various elements:
                # - RUNNABLE-ENTITY: /SWC/Behavior/RunnableName
                # - TIMING-EVENT or DATA-RECEIVED-EVENT: /SWC/Behavior/EventName
                # - OPERATION: /HWIP/Behavior/OperationSequence/Operation
                # - Interface: /InterfaceName

                # Extract the target name from the path
                target_name = trigger_dest.split("/")[-1]

                # Search for the target in various locations
                found = False

                # 1. Check if it's a RUNNABLE-ENTITY
                runnables = self.root.xpath(
                    f"//RUNNABLE-ENTITY[SHORT-NAME/@name='{target_name}']"
                )
                if runnables:
                    found = True

                # 2. Check if it's a TIMING-EVENT in SWC
                if not found:
                    timing_events = self.root.xpath(
                        f"//APPLICATION-SW-COMPONENT-TYPE//TIMING-EVENT[SHORT-NAME/@name='{target_name}']"
                    )
                    if timing_events:
                        found = True

                # 3. Check if it's a DATA-RECEIVED-EVENT in SWC
                if not found:
                    data_events = self.root.xpath(
                        f"//APPLICATION-SW-COMPONENT-TYPE//DATA-RECEIVED-EVENT[SHORT-NAME/@name='{target_name}']"
                    )
                    if data_events:
                        found = True

                # 4. Check if it's an OPERATION
                if not found:
                    # Operations don't always have SHORT-NAME, check if path exists
                    if "OPERATION" in trigger_dest or "Operation" in trigger_dest:
                        # Assume operations are valid if path contains OPERATION
                        found = True

                # 5. Check if it's an interface
                if not found:
                    interfaces = self.root.xpath(
                        f"//SENDER-RECEIVER-INTERFACE[SHORT-NAME/@name='{target_name}']"
                    )
                    if interfaces:
                        found = True

                if not found:
                    xpath = self.tree.getpath(trigger_event)
                    self.errors.append(
                        ValidationError(
                            rule_number=65,
                            severity="error",
                            message=f"TRIGGER-EVENT in HWIP '{hwip_name}' references non-existent target '{target_name}' (TRIGGER DEST='{trigger_dest}'). Target must be a valid RUNNABLE-ENTITY, Event, Operation, or Interface.",
                            xpath=xpath,
                        )
                    )

    def _validate_rule_66(self):
        """
        Rule 66: Each Hwip Trigger Runnable/Event is mapped to a core in same Chiplet/Soc Top Level.

        Validates that when a HWIP triggers a runnable, that runnable is mapped to a core
        in the same SoC or Chiplet as the HWIP.

        Process:
        1. Find HWIP location in hierarchy (identify parent SoC/Chiplet)
        2. Resolve TRIGGER DEST to find the target runnable
        3. Find Core-Runnable-Mapping for that runnable
        4. Extract SoC/Chiplet from ClusterRef path
        5. Compare HWIP location with runnable mapping location

        Requires Python for:
        - Reference resolution
        - Path parsing and hierarchy traversal
        - Cross-element comparison
        """
        hwips = self.root.xpath("//Generic_Hardware")

        # Build mapping: runnable name -> Core-Runnable-Mapping ClusterRef
        runnable_to_cluster = {}
        for hw_sw_mapping in self.root.xpath("//HW-SW-MAPPING"):
            cluster_ref = hw_sw_mapping.get("ClusterRef", "").strip()
            if not cluster_ref:
                continue

            for core_mapping in hw_sw_mapping.xpath("Core-Runnable-Mapping"):
                runnable_ref = core_mapping.get("RunnableRef", "").strip()
                if runnable_ref:
                    # Extract runnable name from path
                    runnable_name = runnable_ref.split("/")[-1]
                    runnable_to_cluster[runnable_name] = cluster_ref

        for hwip in hwips:
            hwip_name_nodes = hwip.xpath("SHORT-NAME/@name")
            if not hwip_name_nodes:
                continue
            hwip_name = hwip_name_nodes[0]

            # Find HWIP's parent SoC (or Chiplet if nested deeper)
            # HWIP is typically in: ECU/SoCs/HWIP or ECU/SoCs/Chiplets/HWIP
            # SoCs has a child SHORT-NAME element with @name attribute
            hwip_parent_soc = None
            parent = hwip.getparent()
            while parent is not None:
                # Check if parent is SoCs or Chiplets element
                if parent.tag == "SoCs":
                    # SoCs element has a SHORT-NAME child element with name attribute
                    parent_name_nodes = parent.xpath("SHORT-NAME/@name")
                    if parent_name_nodes:
                        hwip_parent_soc = parent_name_nodes[0]
                    break
                elif parent.tag == "Chiplets":
                    # Chiplet element also has SHORT-NAME child
                    parent_name_nodes = parent.xpath("SHORT-NAME/@name")
                    if parent_name_nodes:
                        hwip_parent_soc = parent_name_nodes[0]
                    break
                parent = parent.getparent()

            if not hwip_parent_soc:
                # Can't determine HWIP location, skip
                continue

            # Check TRIGGER-EVENT elements
            for trigger_event in hwip.xpath(".//INTERNAL-BEHAVIOR/EVENT/TRIGGER-EVENT"):
                trigger_elem = trigger_event.find("TRIGGER")
                if trigger_elem is None:
                    continue

                trigger_dest = trigger_elem.get("DEST", "").strip()
                if not trigger_dest:
                    # Empty DEST is already checked in Rule 65
                    continue

                # Extract target name
                target_name = trigger_dest.split("/")[-1]

                # Check if target is a RUNNABLE-ENTITY
                runnables = self.root.xpath(
                    f"//RUNNABLE-ENTITY[SHORT-NAME/@name='{target_name}']"
                )
                if not runnables:
                    # Not a runnable, could be event/operation - skip Rule 66 check
                    continue

                # Check if runnable is mapped to a core
                if target_name not in runnable_to_cluster:
                    xpath = self.tree.getpath(trigger_event)
                    self.errors.append(
                        ValidationError(
                            rule_number=66,
                            severity="error",
                            message=f"HWIP '{hwip_name}' triggers runnable '{target_name}' which is not mapped to any core. Add a Core-Runnable-Mapping for this runnable.",
                            xpath=xpath,
                        )
                    )
                    continue

                # Extract SoC/Chiplet from ClusterRef path
                # ClusterRef format: /ECU/SoC/Cluster or /ECU/SoC/Chiplet/Cluster
                cluster_ref = runnable_to_cluster[target_name]
                cluster_parts = [p for p in cluster_ref.split("/") if p]

                # Find the SoC or Chiplet in the path
                # Typically: ECU, SoC_name, Cluster_name or ECU, SoC_name, Chiplet_name, Cluster_name
                runnable_location = None
                if len(cluster_parts) >= 2:
                    # cluster_parts[0] is ECU, cluster_parts[1] is SoC
                    runnable_location = cluster_parts[1]
                    # If there's a third part before the Cluster, it might be a Chiplet
                    if len(cluster_parts) >= 4:
                        # Format: ECU/SoC/Chiplet/Cluster - use Chiplet as location
                        runnable_location = cluster_parts[2]

                if not runnable_location:
                    # Can't parse ClusterRef, skip
                    continue

                # Compare HWIP location with runnable mapping location
                if hwip_parent_soc != runnable_location:
                    xpath = self.tree.getpath(trigger_event)
                    self.errors.append(
                        ValidationError(
                            rule_number=66,
                            severity="error",
                            message=f"HWIP '{hwip_name}' in '{hwip_parent_soc}' triggers runnable '{target_name}' mapped to core in '{runnable_location}'. Runnable must be mapped to a core in the same SoC/Chiplet as the HWIP (ClusterRef='{cluster_ref}').",
                            xpath=xpath,
                        )
                    )

    def _validate_rule_22(self):
        """
        Rule 22: Each <READ> must have an <IREF> child with a non-empty DEST attribute,
        and DEST must resolve to a DATA-READ-ACCESS.
        """
        self._validate_data_access_operation("READ", 22)

    def _validate_rule_23(self):
        """
        Rule 23: Each <WRITE> must have an <IREF> child with a non-empty DEST attribute,
        and DEST must resolve to a DATA-WRITE-ACCESS.
        """
        self._validate_data_access_operation("WRITE", 23)

    def _validate_rule_24(self):
        """
        Rule 24: All Read and Write Operations have Data Access reference to same Runnable.
        For each OPERATIONS-SEQUENCE, all READ/WRITE operations must reference data accesses
        that belong to the SAME RUNNABLE-ENTITY.
        """
        # Build mapping: DATA-ACCESS SHORT-NAME -> parent RUNNABLE-ENTITY SHORT-NAME
        data_access_to_runnable = {}

        for runnable in self.root.xpath("//RUNNABLE-ENTITY"):
            runnable_name_nodes = runnable.xpath("SHORT-NAME/@name")
            if not runnable_name_nodes:
                continue
            runnable_name = runnable_name_nodes[0]

            # Map all DATA-READ-ACCESS in this runnable
            for read_access in runnable.xpath(".//DATA-READ-ACCESS/VARIABLE-ACCESS"):
                access_name_nodes = read_access.xpath("SHORT-NAME/@name")
                if access_name_nodes:
                    data_access_to_runnable[access_name_nodes[0]] = runnable_name

            # Map all DATA-WRITE-ACCESS in this runnable
            for write_access in runnable.xpath(".//DATA-WRITE-ACCESS/VARIABLE-ACCESS"):
                access_name_nodes = write_access.xpath("SHORT-NAME/@name")
                if access_name_nodes:
                    data_access_to_runnable[access_name_nodes[0]] = runnable_name

        # Check each OPERATIONS-SEQUENCE
        for ops_sequence in self.root.xpath("//OPERATIONS-SEQUENCE"):
            referenced_runnables = set()
            operations_info = []  # Track (operation_element, dest, access_name, runnable_name)

            # Collect all READ/WRITE operations and their referenced runnables
            for operation in ops_sequence.xpath(".//OPERATION"):
                for op_elem in operation.xpath("READ | WRITE"):
                    iref = op_elem.find("IREF")
                    if iref is None:
                        continue

                    dest = iref.get("DEST", "").strip()
                    if not dest:
                        continue

                    # Extract data access name from DEST path (last component)
                    access_name = dest.split("/")[-1]

                    # Look up which runnable this data access belongs to
                    if access_name in data_access_to_runnable:
                        runnable_name = data_access_to_runnable[access_name]
                        referenced_runnables.add(runnable_name)
                        operations_info.append(
                            (op_elem, dest, access_name, runnable_name)
                        )

            # Rule 24 violation: Operations reference data accesses from DIFFERENT runnables
            if len(referenced_runnables) > 1:
                # Generate detailed error message
                runnable_list = ", ".join(sorted(referenced_runnables))
                xpath = self.tree.getpath(ops_sequence)

                self.errors.append(
                    ValidationError(
                        rule_number=24,
                        severity="error",
                        message=f"OPERATIONS-SEQUENCE contains READ/WRITE operations referencing data accesses from multiple runnables: {runnable_list}. All operations in the same sequence must reference data accesses from the SAME runnable.",
                        xpath=xpath,
                    )
                )

    """
    Python validator for AE logical rules not fully covered by Schematron.
    """

    def __init__(self, xml_file: str, check_filesystem: bool = False):
        """
        Initialize validator.

        Args:
            xml_file: Path to XML file to validate
            check_filesystem: If True, perform filesystem checks (Rules 38, 39, 71)
        """
        self.xml_file = xml_file
        self.check_filesystem = check_filesystem
        self.tree = etree.parse(xml_file)
        self.root = self.tree.getroot()
        self.errors: List[ValidationError] = []

        # Build lookup indices for fast resolution
        self._build_indices()

    # ============================================================================
    # Rule 26: LATENCY operation not allowed in Custom Behavior
    # ============================================================================
    def _validate_rule_26(self):
        """
        Rule 26: LATENCY operation is not allowed inside SWC-CUSTOM-BEHAVIOR.
        This Python check supplements Schematron to guarantee detection.
        """
        for cb in self.root.xpath("//SWC-CUSTOM-BEHAVIOR"):
            cb_name = (cb.xpath("SHORT-NAME/@name") or ["unnamed"])[0]
            for latency in cb.xpath(".//LATENCY"):
                xpath = self.tree.getpath(latency)
                val = latency.get("value", "unspecified")
                unit = latency.get("unit", "")
                self.errors.append(
                    ValidationError(
                        rule_number=26,
                        severity="error",
                        message=f"LATENCY operation (value={val} {unit}) is not allowed inside SWC-CUSTOM-BEHAVIOR '{cb_name}'",
                        xpath=xpath,
                    )
                )

    def _build_indices(self):
        """Build lookup dictionaries for element resolution by SHORT-NAME."""
        self.swc_index = {}  # SHORT-NAME -> SWC element
        self.runnable_index = {}  # SHORT-NAME -> RUNNABLE-ENTITY element
        self.sri_index = {}  # SHORT-NAME -> SENDER-RECEIVER-INTERFACE element
        self.cluster_index = {}  # SHORT-NAME -> CPU_Cluster element
        self.soc_index = {}  # SHORT-NAME -> SoC element
        self.chiplet_index = {}  # SHORT-NAME -> Chiplet element
        self.prebuilt_app_index = {}  # SHORT-NAME -> PRE-BUILT-APPLICATION element

        # Index SWCs
        for swc in self.root.xpath("//APPLICATION-SW-COMPONENT-TYPE"):
            name = swc.get("name") or swc.xpath("SHORT-NAME/@name")
            if name:
                if isinstance(name, list):
                    name = name[0]
                self.swc_index[name] = swc

        # Index Runnables
        for runnable in self.root.xpath("//RUNNABLE-ENTITY"):
            name = runnable.get("name") or runnable.xpath("SHORT-NAME/@name")
            if name:
                if isinstance(name, list):
                    name = name[0]
                self.runnable_index[name] = runnable

        # Index SRIs
        for sri in self.root.xpath("//SENDER-RECEIVER-INTERFACE"):
            name = sri.get("name") or sri.xpath("SHORT-NAME/@name")
            if name:
                if isinstance(name, list):
                    name = name[0]
                self.sri_index[name] = sri

        # Index CPU Clusters
        for cluster in self.root.xpath("//CPU_Cluster"):
            name_nodes = cluster.xpath(".//SHORT-NAME/@name")
            if name_nodes:
                name = name_nodes[0]
                self.cluster_index[name] = cluster

        # Index SoCs
        for soc in self.root.xpath("//SoCs"):
            name_nodes = soc.xpath("SHORT-NAME/@name")
            if name_nodes:
                name = name_nodes[0]
                self.soc_index[name] = soc

        # Index Chiplets
        for chiplet in self.root.xpath("//Chiplet"):
            name_nodes = chiplet.xpath("SHORT-NAME/@name")
            if name_nodes:
                name = name_nodes[0]
                self.chiplet_index[name] = chiplet

        # Index Prebuilt Applications
        for app in self.root.xpath("//PRE-BUILT-APPLICATION"):
            name = app.get("name") or app.xpath("SHORT-NAME/@name")
            if name:
                if isinstance(name, list):
                    name = name[0]
                self.prebuilt_app_index[name] = app

    def _normalize_dest_path(self, dest: str) -> str:
        """
        Normalize a DEST path by removing leading/trailing slashes and whitespace.

        Args:
            dest: DEST attribute value like "/ECU1/SoC1/Cluster1"

        Returns:
            Normalized path
        """
        return dest.strip().strip("/")

    def _validate_c_identifier(self, name: str) -> tuple[bool, str]:
        """
        Validate if a name is a valid C identifier.

        Args:
            name: The identifier name to validate

        Returns:
            Tuple of (is_valid, error_message)
            - If valid: (True, '')
            - If invalid: (False, 'error description')
        """
        c_identifier_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
        c_keywords = {
            "auto",
            "break",
            "case",
            "char",
            "const",
            "continue",
            "default",
            "do",
            "double",
            "else",
            "enum",
            "extern",
            "float",
            "for",
            "goto",
            "if",
            "inline",
            "int",
            "long",
            "register",
            "restrict",
            "return",
            "short",
            "signed",
            "sizeof",
            "static",
            "struct",
            "switch",
            "typedef",
            "union",
            "unsigned",
            "void",
            "volatile",
            "while",
            "_Alignas",
            "_Alignof",
            "_Atomic",
            "_Bool",
            "_Complex",
            "_Generic",
            "_Imaginary",
            "_Noreturn",
            "_Static_assert",
            "_Thread_local",
        }

        if not c_identifier_pattern.match(name):
            return (
                False,
                "is not a valid C identifier. C identifiers must match the pattern ^[a-zA-Z_][a-zA-Z0-9_]*$ (start with letter or underscore, contain only letters, digits, and underscores).",
            )
        elif name in c_keywords:
            return False, "is a reserved C keyword and cannot be used as an identifier."

        return True, ""

    def _extract_short_name_from_dest(self, dest: str) -> str:
        """
        Extract the final SHORT-NAME from a DEST path.

        Args:
            dest: DEST path like "/ECU1/SoC1/Cluster1"

        Returns:
            Final segment (e.g., "Cluster1")
        """
        normalized = self._normalize_dest_path(dest)
        segments = normalized.split("/")
        return segments[-1] if segments else ""

    def validate_all(self) -> List[ValidationError]:
        """
        Run all Python validation rules.

        Returns:
            List of ValidationError objects
        """

        self.errors = []

        # Simulation-Time validation (must be >= 3000 ms)
        self._validate_simulation_time()
        
        # Timing Event Period validation (must be >= 10ms)
        self._validate_timing_event_period()

        # Rule 7: Each Runnable name is valid against C variable naming rules
        self._validate_rule_7()

        # Rule 6: Each Runnable has a globally unique name
        self._validate_rule_6()

        # Rule 9: Each Runnable is mapped to a valid Cpu Core (coverage existence)
        self._validate_rule_9()

        # Rule 10: Each Runnable is mapped to only one Cpu Core
        self._validate_rule_10()

        # Rule 12: Each Data Access is connected to a valid port
        self._validate_rule_12()

        # Rule 13: Each Data Access is connected to a valid Target Data
        self._validate_rule_13()

        # Rule 14: Runnable can't have Data Read and Write access to the same Sender-Receiver Interface
        self._validate_rule_14()

        # Rule 16: Each Event name is valid against C variable naming rules
        self._validate_rule_16()

        # Rule 28: Each Sender-Receiver interface name is valid against C variable naming rules
        self._validate_rule_28()

        # Rule 35: Each Data Element name is valid against C variable naming rules
        self._validate_rule_35()

        # Rule 22: Each Read Operation has a valid Data Access reference
        self._validate_rule_22()

        # Rule 23: Each Write Operation has a valid Data Access reference
        self._validate_rule_23()

        # Rule 24: All Read and Write Operations have Data Access reference to same Runnable
        self._validate_rule_24()

        # ...existing code...
        self._validate_rule_25()
        self._validate_rule_26()
        self._validate_rule_31()
        self._validate_rule_32()
        self._validate_rule_33()
        # Rule 38 (PATH existence) is handled by Rule 40 now; skip calling Rule 38 to avoid duplicate reporting
        self._validate_rule_39()
        # Rule 76b: Ensure HW-SW-MAPPING ClusterRefs point to existing clusters
        self._validate_rule_76b()
        self._validate_rule_3()
        self._validate_rule_4()
        self._validate_rule_5()
        self._validate_rule_40()
        self._validate_rule_41()
        self._validate_rule_44()
        # Rule 46: SoC name must be valid C identifier
        self._validate_rule_46()
        # Rule 52: Chiplet name must be valid C identifier
        self._validate_rule_52()
        # Rule 56: HWIP (Generic_Hardware) name must be valid C identifier
        self._validate_rule_56()
        # Rule 59: Each HWIP Port is connected to at least one valid operation
        self._validate_rule_59()
        # Rule 60: Each Hwip can NOT have provider and required ports connected to the same SRI
        self._validate_rule_60()
        # Rule 62: Each Hwip Operations are valid
        self._validate_rule_62()
        # Rule 63: Each Hwip Read/Write operation is connected to a valid port
        self._validate_rule_63()
        # Rule 64: Each Hwip Data Received event is connected to a valid port
        self._validate_rule_64()
        # Rule 65: Each Hwip Trigger event is connected to a valid Runnable/Event
        self._validate_rule_65()
        # Rule 66: Each Hwip Trigger Runnable/Event is mapped to a core in same Chiplet/Soc Top Level
        self._validate_rule_66()
        # Rule 48: D2D config references resolve to existing SoC/Chiplet
        self._validate_rule_47()
        self._validate_rule_58()
        self._validate_rule_70()

        self._validate_rule_71()
        # self._validate_rule_73()  # Rule 73 enforcement is currently disabled (leave this line commented to keep the call visible)
        self._validate_rule_74()
        self._validate_rule_75()
        self._validate_rule_76()
        self._validate_rule_76_hw_frequency()  # CPU Cluster Frequency validation for Linux OS
        self._validate_rule_77()
        # Rule 79: CorePrebuiltAppMapping CoreId validation (moved from Rule 39/77)
        # Ensure this runs after Rule 77's other checks.
        if hasattr(self, "_validate_rule_79"):
            self._validate_rule_79()
        self._validate_rule_78()
        # Rule 80 prebuilt mapping existence check (Core-PrebuiltApplication-Mapping)
        if hasattr(self, "_validate_rule_80_prebuilt"):
            self._validate_rule_80_prebuilt()
        # Rule 81: Cluster-PrebuiltApplication-Mapping existence check
        if hasattr(self, "_validate_rule_81_prebuilt"):
            self._validate_rule_81_prebuilt()
        # Rule 82 (Analysis SoC references): Ensure Analysis SocReference/SoC DEST values resolve to actual SoC SHORT-NAMEs
        if hasattr(self, "_validate_rule_82_analysis"):
            self._validate_rule_82_analysis()
        # NOTE: The PowerAnalysis CPU-type whitelist check has been disabled by request.
        # Many projects (Siemens etc.) manage an external policy for supported CPU
        # types. Because we don't want to assume a canonical supported list, skip
        # the authoritative whitelist enforcement here. The function `_validate_rule_83`
        # remains implemented and can be re-enabled by restoring the call below.
        # To re-enable: uncomment the following line.
        # Re-enable Power Analysis CPU-type whitelist enforcement (Rule 83)
        # (function name changed to _validate_rule_83 to reflect correct rule number)
        self._validate_rule_83()
        # Rule 84: When PowerAnalysis is enabled, all CPU_Cluster Operating-System types must be Nucleus_RTOS
        if hasattr(self, "_validate_rule_84"):
            self._validate_rule_84()
        # The OS whitelist enforcement is disabled because the authoritative
        # supported-OS list is not available. To re-enable, uncomment the
        # self._validate_rule_81() call below and ensure the policy is present.
        # self._validate_rule_81()

        # Use Rule 85 as the authoritative single-core enforcement for Power Analysis
        # (replaces the older Rule 82 semantic check to avoid duplicate reporting).
        if hasattr(self, "_validate_rule_85"):
            self._validate_rule_85()
        else:
            self._validate_rule_82()
        # Rule 90: InterfaceReference must point to existing SRI (moved from old Rule 40)
        self._validate_rule_90()
        return self.errors

    def _validate_rule_7(self):
        """
        Rule 7: Each Runnable name is valid against C variable naming rules.
        Checks:
        - Starts with letter or underscore
        - Only letters, digits, underscores
        - Not a C keyword
        """
        for runnable in self.root.xpath("//RUNNABLE-ENTITY"):
            name_nodes = runnable.xpath("SHORT-NAME/@name")
            if not name_nodes:
                continue
            name = name_nodes[0]
            xpath = self.tree.getpath(runnable)
            is_valid, error_msg = self._validate_c_identifier(name)
            if not is_valid:
                self.errors.append(
                    ValidationError(
                        rule_number=7,
                        severity="error",
                        message=f"Runnable name '{name}' {error_msg}",
                        xpath=xpath,
                    )
                )

    # End Rule 7 validation

    def _validate_rule_35(self):
        pass

    # ============================================================================
    # Rule 41: Each prebuilt app is compiled with the right toolchain
    # ============================================================================
    def _validate_rule_41(self):
        """
        Rule 41: Each PRE-BUILT-APPLICATION must indicate its toolchain (GCC, ARM, CLANG, MSVC).

        Detection strategy (since XSD doesn't support TOOLCHAIN element):
        1. Check for TOOLCHAIN child element (if added manually for testing)
        2. Extract toolchain from SHORT-NAME (e.g., "AppName_GCC", "AppName_CLANG")
        3. Extract toolchain from PATH (e.g., "bin/gcc/app.bin", "bin/app_gcc.bin")

        Flags:
        - Missing toolchain indicator
        - Invalid toolchain values (not in allowed set)
        """
        valid_toolchains = {"GCC", "ARM", "CLANG", "MSVC"}

        for app in self.root.xpath("//PRE-BUILT-APPLICATION"):
            xpath = self.tree.getpath(app)
            toolchain = None
            source = None

            # Strategy 1: Check for TOOLCHAIN child element (optional, for testing)
            toolchain_elem = app.find("TOOLCHAIN")
            if toolchain_elem is not None and toolchain_elem.text:
                toolchain = toolchain_elem.text.strip().upper()
                source = "TOOLCHAIN element"

            # Strategy 2: Extract from SHORT-NAME (e.g., "AppName_GCC")
            if not toolchain:
                name_nodes = app.xpath("SHORT-NAME/@name")
                if name_nodes:
                    name = name_nodes[0]
                    # First, try exact match with valid toolchains
                    for tc in valid_toolchains:
                        if name.upper().endswith(f"_{tc}") or name.upper().endswith(
                            f"-{tc}"
                        ):
                            toolchain = tc
                            source = f"SHORT-NAME ('{name}')"
                            break
                    # If no valid match, extract any suffix as potential toolchain
                    if not toolchain:
                        if "_" in name:
                            potential_tc = name.split("_")[-1].strip().upper()
                            if (
                                potential_tc and len(potential_tc) > 1
                            ):  # At least 2 chars
                                toolchain = potential_tc
                                source = f"SHORT-NAME ('{name}')"
                        elif "-" in name:
                            potential_tc = name.split("-")[-1].strip().upper()
                            if potential_tc and len(potential_tc) > 1:
                                toolchain = potential_tc
                                source = f"SHORT-NAME ('{name}')"

            # Strategy 3: Extract from PATH (e.g., "bin/gcc/app.bin" or "bin/app_gcc.bin")
            if not toolchain:
                path_elem = app.find("PATH")
                if path_elem is not None:
                    path = path_elem.get("DEST", "")
                    path_upper = path.upper()
                    for tc in valid_toolchains:
                        # Check if toolchain appears in path (case-insensitive)
                        if (
                            f"/{tc}/" in path_upper
                            or f"_{tc}." in path_upper
                            or f"_{tc}_" in path_upper
                            or f"-{tc}." in path_upper
                            or f"-{tc}-" in path_upper
                        ):
                            toolchain = tc
                            source = f"PATH ('{path}')"
                            break

            # Validate toolchain
            if not toolchain:
                self.errors.append(
                    ValidationError(
                        rule_number=41,
                        severity="error",
                        message='PRE-BUILT-APPLICATION missing toolchain indicator. Expected toolchain suffix in SHORT-NAME (e.g., "AppName_GCC") or path (e.g., "bin/gcc/app.bin").',
                        xpath=xpath,
                    )
                )
            elif toolchain not in valid_toolchains:
                self.errors.append(
                    ValidationError(
                        rule_number=41,
                        severity="error",
                        message=f"PRE-BUILT-APPLICATION has invalid toolchain '{toolchain}' (detected from {source}). Allowed: {sorted(valid_toolchains)}.",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 12: Each Data Access is connected to a valid port
    # ============================================================================
    def _validate_rule_12(self):
        """
        Rule 12: Each Data Access (VARIABLE-ACCESS) must reference an existing port via PORT-PROTOTYPE-REF/@DEST.
        The DEST must resolve to a P-PORT-PROTOTYPE or R-PORT-PROTOTYPE SHORT-NAME within the same SWC.

        Why Python: Requires DEST path normalization and lookup in port declarations within the SWC scope.
        """
        # Build port index: map full port paths to port elements within each SWC
        port_paths = set()
        for swc in self.root.xpath("//APPLICATION-SW-COMPONENT-TYPE"):
            swc_name_nodes = swc.xpath("SHORT-NAME/@name")
            if not swc_name_nodes:
                continue
            swc_name = swc_name_nodes[0]

            # Collect P-PORT names
            for pport in swc.xpath(".//P-PORT-PROTOTYPE"):
                port_name_nodes = pport.xpath("SHORT-NAME/@name")
                if port_name_nodes:
                    port_name = port_name_nodes[0]
                    port_path = f"/{swc_name}/{port_name}"
                    port_paths.add(port_path)

            # Collect R-PORT names
            for rport in swc.xpath(".//R-PORT-PROTOTYPE"):
                port_name_nodes = rport.xpath("SHORT-NAME/@name")
                if port_name_nodes:
                    port_name = port_name_nodes[0]
                    port_path = f"/{swc_name}/{port_name}"
                    port_paths.add(port_path)

        # Check all PORT-PROTOTYPE-REF elements
        for port_ref in self.root.xpath("//PORT-PROTOTYPE-REF"):
            dest = port_ref.get("DEST", "").strip()
            if not dest:
                xpath = self.tree.getpath(port_ref)
                self.errors.append(
                    ValidationError(
                        rule_number=12,
                        severity="error",
                        message="PORT-PROTOTYPE-REF has empty @DEST attribute.",
                        xpath=xpath,
                    )
                )
                continue

            # Normalize and check existence
            normalized_dest = self._normalize_dest_path(dest)
            # Reconstruct as /SWC/Port for comparison
            if not normalized_dest.startswith("/"):
                normalized_dest = "/" + normalized_dest

            if normalized_dest not in port_paths:
                xpath = self.tree.getpath(port_ref)
                self.errors.append(
                    ValidationError(
                        rule_number=12,
                        severity="error",
                        message=f"PORT-PROTOTYPE-REF/@DEST='{dest}' does not resolve to an existing P-PORT-PROTOTYPE or R-PORT-PROTOTYPE. Each data access must reference a valid declared port.",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 13: Each Data Access is connected to a valid Target Data
    # ============================================================================
    def _validate_rule_13(self):
        """
        Rule 13: Each Data Access (VARIABLE-ACCESS) must reference an existing data element via TARGET-DATA-PROTOTYPE-REF/@DEST.
        The DEST must resolve to a VARIABLE-DATA-PROTOTYPE SHORT-NAME within a SENDER-RECEIVER-INTERFACE.

        Why Python: Requires DEST path normalization and lookup in data element declarations within SRIs.
        """
        # Build data element index: map full data element paths to declarations in SRIs
        data_element_paths = set()
        for sri in self.root.xpath("//SENDER-RECEIVER-INTERFACE"):
            sri_name_nodes = sri.xpath("SHORT-NAME/@name")
            if not sri_name_nodes:
                continue
            sri_name = sri_name_nodes[0]

            # Collect VARIABLE-DATA-PROTOTYPE names
            for data_elem in sri.xpath(".//VARIABLE-DATA-PROTOTYPE"):
                elem_name_nodes = data_elem.xpath("SHORT-NAME/@name")
                if elem_name_nodes:
                    elem_name = elem_name_nodes[0]
                    elem_path = f"/{sri_name}/{elem_name}"
                    data_element_paths.add(elem_path)

        # Check all TARGET-DATA-PROTOTYPE-REF elements
        for target_ref in self.root.xpath("//TARGET-DATA-PROTOTYPE-REF"):
            dest = target_ref.get("DEST", "").strip()
            if not dest:
                xpath = self.tree.getpath(target_ref)
                self.errors.append(
                    ValidationError(
                        rule_number=13,
                        severity="error",
                        message="TARGET-DATA-PROTOTYPE-REF has empty @DEST attribute.",
                        xpath=xpath,
                    )
                )
                continue

            # Normalize and check existence
            normalized_dest = self._normalize_dest_path(dest)
            # Reconstruct as /Interface/DataElement for comparison
            if not normalized_dest.startswith("/"):
                normalized_dest = "/" + normalized_dest

            if normalized_dest not in data_element_paths:
                xpath = self.tree.getpath(target_ref)
                self.errors.append(
                    ValidationError(
                        rule_number=13,
                        severity="error",
                        message=f"TARGET-DATA-PROTOTYPE-REF/@DEST='{dest}' does not resolve to an existing VARIABLE-DATA-PROTOTYPE in any SENDER-RECEIVER-INTERFACE. Each data access must reference a valid declared data element.",
                        xpath=xpath,
                    )
                )

    def _validate_rule_14(self):
        """
        Rule 14: Runnable can't have Data Read and Write access to the same Sender-Receiver Interface.

        This rule checks that within a single RUNNABLE-ENTITY, if there are both DATA-READ-ACCESS
        and DATA-WRITE-ACCESS, they must not reference ports that connect to the same SRI.

        Algorithm:
        1. Build a mapping of port paths to their connected SRI names
        2. For each runnable:
           a. Collect all SRI names accessed via DATA-READ-ACCESS
           b. Collect all SRI names accessed via DATA-WRITE-ACCESS
           c. Report error if any SRI appears in both sets
        """
        # Step 1: Build port -> SRI mapping
        port_to_sri = {}

        # Process all SWC types
        for swc in self.root.xpath("//APPLICATION-SW-COMPONENT-TYPE"):
            swc_name_nodes = swc.xpath("SHORT-NAME/@name")
            if not swc_name_nodes:
                continue
            swc_name = swc_name_nodes[0]

            # Process P-PORTs (provided)
            for p_port in swc.xpath(".//P-PORT-PROTOTYPE"):
                port_name_nodes = p_port.xpath("SHORT-NAME/@name")
                if not port_name_nodes:
                    continue
                port_name = port_name_nodes[0]
                port_path = f"/{swc_name}/{port_name}"

                # Get the provided interface reference
                interface_refs = p_port.xpath("PROVIDED-INTERFACE-TREF/@DEST")
                if interface_refs:
                    interface_dest = interface_refs[0].strip()
                    # Normalize to remove leading slash if present
                    if interface_dest.startswith("/"):
                        interface_dest = interface_dest[1:]
                    # Extract just the interface name (last component)
                    sri_name = interface_dest.split("/")[-1]
                    port_to_sri[port_path] = sri_name

            # Process R-PORTs (required)
            for r_port in swc.xpath(".//R-PORT-PROTOTYPE"):
                port_name_nodes = r_port.xpath("SHORT-NAME/@name")
                if not port_name_nodes:
                    continue
                port_name = port_name_nodes[0]
                port_path = f"/{swc_name}/{port_name}"

                # Get the required interface reference
                interface_refs = r_port.xpath("REQUIRED-INTERFACE-TREF/@DEST")
                if interface_refs:
                    interface_dest = interface_refs[0].strip()
                    # Normalize to remove leading slash if present
                    if interface_dest.startswith("/"):
                        interface_dest = interface_dest[1:]
                    # Extract just the interface name (last component)
                    sri_name = interface_dest.split("/")[-1]
                    port_to_sri[port_path] = sri_name

        # Step 2: For each runnable, check for read/write to same SRI
        for runnable in self.root.xpath("//RUNNABLE-ENTITY"):
            read_sris = set()
            write_sris = set()

            # Collect SRIs from DATA-READ-ACCESS
            for read_access in runnable.xpath(".//DATA-READ-ACCESS"):
                port_refs = read_access.xpath(".//PORT-PROTOTYPE-REF/@DEST")
                for port_dest in port_refs:
                    port_dest = port_dest.strip()
                    # Normalize
                    if not port_dest.startswith("/"):
                        port_dest = "/" + port_dest
                    if port_dest in port_to_sri:
                        read_sris.add(port_to_sri[port_dest])

            # Collect SRIs from DATA-WRITE-ACCESS
            for write_access in runnable.xpath(".//DATA-WRITE-ACCESS"):
                port_refs = write_access.xpath(".//PORT-PROTOTYPE-REF/@DEST")
                for port_dest in port_refs:
                    port_dest = port_dest.strip()
                    # Normalize
                    if not port_dest.startswith("/"):
                        port_dest = "/" + port_dest
                    if port_dest in port_to_sri:
                        write_sris.add(port_to_sri[port_dest])

            # Check for intersection
            conflicting_sris = read_sris & write_sris
            if conflicting_sris:
                runnable_name_nodes = runnable.xpath("SHORT-NAME/@name")
                runnable_name = (
                    runnable_name_nodes[0] if runnable_name_nodes else "unknown"
                )
                xpath = self.tree.getpath(runnable)

                sri_list = ", ".join(sorted(conflicting_sris))
                self.errors.append(
                    ValidationError(
                        rule_number=14,
                        severity="error",
                        message=f"RUNNABLE-ENTITY '{runnable_name}' has both DATA-READ-ACCESS and DATA-WRITE-ACCESS to the same Sender-Receiver Interface(s): {sri_list}. A runnable cannot both read from and write to the same interface.",
                        xpath=xpath,
                    )
                )

    def _validate_rule_16(self):
        """
        Rule 16: Each Event name is valid against C variable naming rules.

        Validates that all event names (TIMING-EVENT, DATA-RECEIVED-EVENT, TRIGGER-EVENT)
        follow C identifier naming rules:
        - Starts with letter (a-z, A-Z) or underscore (_)
        - Contains only letters, digits, underscores
        - Not a C keyword
        """
        # Check all event types
        event_types = ["TIMING-EVENT", "DATA-RECEIVED-EVENT", "TRIGGER-EVENT"]
        for event_type in event_types:
            for event in self.root.xpath(f"//{event_type}"):
                name_nodes = event.xpath("SHORT-NAME/@name")
                if not name_nodes:
                    continue
                name = name_nodes[0]
                xpath = self.tree.getpath(event)

                is_valid, error_msg = self._validate_c_identifier(name)
                if not is_valid:
                    self.errors.append(
                        ValidationError(
                            rule_number=16,
                            severity="error",
                            message=f"Event SHORT-NAME/@name '{name}' {error_msg}",
                            xpath=xpath,
                        )
                    )

    def _validate_rule_28(self):
        """
        Rule 28: Each Sender-Receiver interface name is valid against C variable naming rules.

        Validates that all SENDER-RECEIVER-INTERFACE names follow C identifier rules using
        the shared helper `_validate_c_identifier` to avoid redundant logic.
        """
        for sri in self.root.xpath("//SENDER-RECEIVER-INTERFACE"):
            name_nodes = sri.xpath("SHORT-NAME/@name")
            if not name_nodes:
                continue
            name = name_nodes[0]
            xpath = self.tree.getpath(sri)

            is_valid, error_msg = self._validate_c_identifier(name)
            if not is_valid:
                self.errors.append(
                    ValidationError(
                        rule_number=28,
                        severity="error",
                        message=f"SENDER-RECEIVER-INTERFACE name '{name}' {error_msg}",
                        xpath=xpath,
                    )
                )

    def _validate_rule_6(self):
        """
        Rule 6: Each Runnable has a globally unique name.
        Reports all duplicates with their locations.
        """
        name_to_paths = {}
        for runnable in self.root.xpath("//RUNNABLE-ENTITY"):
            name_nodes = runnable.xpath("SHORT-NAME/@name")
            if not name_nodes:
                continue
            name = name_nodes[0]
            xpath = self.tree.getpath(runnable)
            if name in name_to_paths:
                # Already seen: report all previous and current as errors
                self.errors.append(
                    ValidationError(
                        rule_number=6,
                        severity="error",
                        message=f"Duplicate RUNNABLE-ENTITY SHORT-NAME/@name '{name}' found. Previous occurrence(s) at: {name_to_paths[name]}",
                        xpath=xpath,
                    )
                )
            else:
                name_to_paths[name] = xpath

    # ============================================================================
    # Rule 9: Each Runnable is mapped to a valid Cpu Core (existence)
    # ============================================================================
    def _validate_rule_9(self):
        """
        Rule 9: Ensure every RUNNABLE-ENTITY is mapped by at least one Core-Runnable-Mapping.
        This check ensures coverage (existence). Validity of the mapping itself is handled by:
        - Rule 74: HwSwMapping/@ClusterRef resolves to CPU_Cluster
        - Rule 75: CoreId < CoresPerCluster
        - Rule 76: RunnableRef resolves to an existing RUNNABLE-ENTITY
        """
        # Collect mapped runnable names (from RunnableRef short names).
        # Also capture raw RunnableRef values found in mappings for diagnostics.
        mapped: set[str] = set()
        mapping_runnable_refs: list[str] = []
        for mapping in self.root.xpath(
            "//Core-Runnable-Mapping | //CoreRunnableMapping"
        ):
            runnable_ref = (mapping.get("RunnableRef") or "").strip()
            if not runnable_ref:
                continue
            mapping_runnable_refs.append(runnable_ref)
            short = self._extract_short_name_from_dest(runnable_ref)
            # Only consider a mapping as mapping the runnable if it resolves to an existing RUNNABLE-ENTITY
            if short and short in self.runnable_index:
                mapped.add(short)

        # For each runnable, ensure it appears in mapped set. If not, include helpful diagnostics
        # listing existing mapping RunnableRef values to aid debugging (e.g. mappings that
        # reference missing runnables).
        for runnable in self.root.xpath("//RUNNABLE-ENTITY"):
            name_nodes = runnable.xpath("SHORT-NAME/@name")
            if not name_nodes:
                continue
            name = name_nodes[0]
            xpath = self.tree.getpath(runnable)
            if name not in mapped:
                found_refs = (
                    ", ".join(mapping_runnable_refs[:10])
                    if mapping_runnable_refs
                    else "none"
                )
                suggestion = (
                    f"Existing Core-Runnable-Mapping RunnableRef values in document: {found_refs}.\n"
                    "If mappings reference a non-existent runnable, fix the RunnableRef paths or add the runnable."
                )
                self.errors.append(
                    ValidationError(
                        rule_number=9,
                        severity="error",
                        message=(
                            f"RUNNABLE-ENTITY '{name}' is not mapped to any Cpu Core. "
                            "Add a Core-Runnable-Mapping with RunnableRef pointing to this runnable and a valid ClusterRef/CoreId.\n"
                            + suggestion
                        ),
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 10: Each Runnable is mapped to only one Cpu Core
    # ============================================================================
    def _validate_rule_10(self):
        """
        Rule 10: Ensure no runnable is mapped more than once across Core-Runnable-Mapping entries.
        This detects duplicates even within a single HW-SW-MAPPING block.
        """
        counts: Dict[str, int] = {}
        first_mapping_for: Dict[str, etree._Element] = {}
        for mapping in self.root.xpath(
            "//Core-Runnable-Mapping | //CoreRunnableMapping"
        ):
            runnable_ref = (mapping.get("RunnableRef") or "").strip()
            if not runnable_ref:
                continue
            short = self._extract_short_name_from_dest(runnable_ref)
            if not short:
                continue
            counts[short] = counts.get(short, 0) + 1
            if short not in first_mapping_for:
                first_mapping_for[short] = mapping

        for runnable in self.root.xpath("//RUNNABLE-ENTITY"):
            name_nodes = runnable.xpath("SHORT-NAME/@name")
            if not name_nodes:
                continue
            name = name_nodes[0]
            if counts.get(name, 0) > 1:
                xpath = self.tree.getpath(runnable)
                self.errors.append(
                    ValidationError(
                        rule_number=10,
                        severity="error",
                        message=(
                            f"RUNNABLE-ENTITY '{name}' is mapped {counts[name]} times. "
                            f"Each runnable must be mapped to only one Cpu Core (one Core-Runnable-Mapping)."
                        ),
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 5: Each Provider port connected to exactly one DATA-WRITE-ACCESS
    # ============================================================================
    def _validate_rule_5(self):
        """
        Rule 5: Each P-PORT-PROTOTYPE must be referenced by exactly one DATA-WRITE-ACCESS.
        Why Python: Requires counting references across all DATA-WRITE-ACCESS elements.
        """
        # Build a map of P-PORT SHORT-NAME to reference count
        pport_ref_count = {}
        # Collect all P-PORT-PROTOTYPE SHORT-NAMEs with their full paths
        for pport in self.root.xpath("//P-PORT-PROTOTYPE"):
            port_name_nodes = pport.xpath("SHORT-NAME/@name")
            if not port_name_nodes:
                continue
            port_name = port_name_nodes[0]
            # Build the expected reference path (e.g., "/SWCName/PortName")
            swc = pport.xpath("ancestor::APPLICATION-SW-COMPONENT-TYPE")
            if swc:
                swc_name_nodes = swc[0].xpath("SHORT-NAME/@name")
                if swc_name_nodes:
                    swc_name = swc_name_nodes[0]
                    port_path = f"/{swc_name}/{port_name}"
                    pport_ref_count[port_path] = {"count": 0, "element": pport}

        # Count references from DATA-WRITE-ACCESS
        for write_access in self.root.xpath("//DATA-WRITE-ACCESS"):
            port_refs = write_access.xpath(".//PORT-PROTOTYPE-REF/@DEST")
            for ref in port_refs:
                if ref in pport_ref_count:
                    pport_ref_count[ref]["count"] += 1

        # Validate: each P-PORT must have exactly 1 reference
        for port_path, data in pport_ref_count.items():
            count = data["count"]
            element = data["element"]
            port_name_nodes = element.xpath("SHORT-NAME/@name")
            port_name = port_name_nodes[0] if port_name_nodes else "unknown"
            xpath = self.tree.getpath(element)
            if count == 0:
                self.errors.append(
                    ValidationError(
                        rule_number=5,
                        severity="error",
                        message=f"Provider port '{port_name}' (at {port_path}) has ZERO DATA-WRITE-ACCESS references. Each P-PORT must be connected to exactly one DATA-WRITE-ACCESS.",
                        xpath=xpath,
                    )
                )
            elif count > 1:
                self.errors.append(
                    ValidationError(
                        rule_number=5,
                        severity="error",
                        message=f"Provider port '{port_name}' (at {port_path}) has {count} DATA-WRITE-ACCESS references. Each P-PORT must be connected to exactly ONE DATA-WRITE-ACCESS.",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 25: Each Custom Operation has valid inputs
    # ============================================================================
    def _validate_rule_25(self):
        """
        Rule 25: Each Custom Operation has valid inputs.

        Validates:
        - CUSTOM-OPERATION: functionPrototype format, non-empty headerFile/includesDir/sourcesDir
        - AI/ML operations: height, width, channels, kernelSize, stride > 0

        Why Python: Backup validation for Schematron (some processors may miss errors),
        plus file existence checks (optional).
        """
        import re
        import os

        # Validate CUSTOM-OPERATION attributes
        for op in self.root.xpath("//CUSTOM-OPERATION"):
            xpath = self.tree.getpath(op)

            # Check functionPrototype format with strict regex
            func_proto = op.get("functionPrototype", "")
            if not func_proto or not func_proto.strip():
                self.errors.append(
                    ValidationError(
                        rule_number=25,
                        severity="error",
                        message="CUSTOM-OPERATION must have a non-empty functionPrototype attribute.",
                        xpath=xpath,
                    )
                )
            else:
                # Strict pattern: void <function_name>(void) with optional whitespace
                # Must start with "void", followed by identifier, followed by "(void)"
                pattern = r"^\s*void\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(\s*void\s*\)\s*$"
                if not re.match(pattern, func_proto):
                    self.errors.append(
                        ValidationError(
                            rule_number=25,
                            severity="error",
                            message=f"CUSTOM-OPERATION functionPrototype must follow format 'void func_name(void)', got: '{func_proto}'",
                            xpath=xpath,
                        )
                    )

            # Check headerFile
            header_file = op.get("headerFile", "")
            if not header_file or not header_file.strip():
                self.errors.append(
                    ValidationError(
                        rule_number=25,
                        severity="error",
                        message="CUSTOM-OPERATION must have a non-empty headerFile attribute.",
                        xpath=xpath,
                    )
                )
            elif self.check_filesystem:
                # Optional: Check if headerFile exists (when filesystem checks enabled)
                xml_dir = os.path.dirname(os.path.abspath(self.xml_file))
                header_path = os.path.join(xml_dir, header_file)
                if not os.path.isfile(header_path):
                    self.errors.append(
                        ValidationError(
                            rule_number=25,
                            severity="warning",
                            message=f"CUSTOM-OPERATION headerFile not found: '{header_file}'",
                            xpath=xpath,
                        )
                    )

            # Check includesDir
            includes_dir = op.get("includesDir", "")
            if not includes_dir or not includes_dir.strip():
                self.errors.append(
                    ValidationError(
                        rule_number=25,
                        severity="error",
                        message="CUSTOM-OPERATION must have a non-empty includesDir attribute.",
                        xpath=xpath,
                    )
                )
            elif self.check_filesystem:
                # Optional: Check if includesDir exists (when filesystem checks enabled)
                xml_dir = os.path.dirname(os.path.abspath(self.xml_file))
                includes_path = os.path.join(xml_dir, includes_dir)
                if not os.path.isdir(includes_path):
                    self.errors.append(
                        ValidationError(
                            rule_number=25,
                            severity="warning",
                            message=f"CUSTOM-OPERATION includesDir not found: '{includes_dir}'",
                            xpath=xpath,
                        )
                    )

            # Check sourcesDir
            sources_dir = op.get("sourcesDir", "")
            if not sources_dir or not sources_dir.strip():
                self.errors.append(
                    ValidationError(
                        rule_number=25,
                        severity="error",
                        message="CUSTOM-OPERATION must have a non-empty sourcesDir attribute.",
                        xpath=xpath,
                    )
                )
            elif self.check_filesystem:
                # Optional: Check if sourcesDir exists (when filesystem checks enabled)
                xml_dir = os.path.dirname(os.path.abspath(self.xml_file))
                sources_path = os.path.join(xml_dir, sources_dir)
                if not os.path.isdir(sources_path):
                    self.errors.append(
                        ValidationError(
                            rule_number=25,
                            severity="warning",
                            message=f"CUSTOM-OPERATION sourcesDir not found: '{sources_dir}'",
                            xpath=xpath,
                        )
                    )

        # Note: AI/ML operations (CONVOLUTION, MAX-POOL, AVG-POOL, etc.) have their
        # numeric attributes (height, width, channels, kernelSize, stride) validated
        # by XSD schema (xs:unsignedInt), so no additional LOGICAL validation is needed.
        # Rule 25 focuses on CUSTOM-OPERATION format requirements only.

    # ============================================================================
    # Rule 31: Network topology type validation (Ethernet modes)
    # ============================================================================
    def _validate_rule_31(self):
        """
        Rule 31: Each Sender-Receiver interface referenced by a CAN-BUS or Eth-Switch must have at least one DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE.

        Why Python: Defense-in-depth redundancy with Schematron.
        Note: This rule is also enforced by XSD (structurally) and Schematron.
        Python provides: (1) robust DEST reference resolution, (2) better error messages with SRI names,
        (3) future extensibility for network-specific data requirements.
        """
        # Check CAN-BUS references
        for canbus in self.root.xpath("//CAN-BUS"):
            sri_ref_nodes = canbus.xpath("INTERFACE-TREF/@DEST")
            if sri_ref_nodes:
                sri_ref = sri_ref_nodes[0]
                sri_name = self._extract_short_name_from_dest(sri_ref)

                # Find the referenced SRI
                sris = self.root.xpath(
                    f".//SENDER-RECEIVER-INTERFACE[SHORT-NAME/@name='{sri_name}']"
                )
                if sris:
                    sri = sris[0]
                    # Check if it has DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE
                    data_protos = sri.xpath(".//DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE")
                    if not data_protos:
                        xpath = self.tree.getpath(canbus)
                        self.errors.append(
                            ValidationError(
                                rule_number=31,
                                severity="error",
                                message=f"SENDER-RECEIVER-INTERFACE '{sri_name}' referenced by CAN-BUS does not have any DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE.",
                                xpath=xpath,
                            )
                        )

        # Check Eth-Switch references
        for eth in self.root.xpath("//Eth-Switch"):
            sri_ref_nodes = eth.xpath("INTERFACE-TREF/@DEST")
            if sri_ref_nodes:
                sri_ref = sri_ref_nodes[0]
                sri_name = self._extract_short_name_from_dest(sri_ref)

                # Find the referenced SRI
                sris = self.root.xpath(
                    f".//SENDER-RECEIVER-INTERFACE[SHORT-NAME/@name='{sri_name}']"
                )
                if sris:
                    sri = sris[0]
                    # Check if it has DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE
                    data_protos = sri.xpath(".//DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE")
                    if not data_protos:
                        xpath = self.tree.getpath(eth)
                        self.errors.append(
                            ValidationError(
                                rule_number=31,
                                severity="error",
                                message=f"SENDER-RECEIVER-INTERFACE '{sri_name}' referenced by Eth-Switch does not have any DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE.",
                                xpath=xpath,
                            )
                        )

    # ============================================================================
    # Rule 32: Inter-Chiplet Provider must be 'host' UCIe mode
    # ============================================================================
    def _validate_rule_32(self):
        """
        Rule 32: Each Sender-Receiver interface if through Ethernet, both Provider and Required must have "simulated" Ethernet mode.

        For each Eth-Switch in Network-Topology:
        - For each INTERFACE-TREF, find the referenced SRI.
        - For each P-PORT and R-PORT referencing that SRI, find the containing SoC's ETHERNET-INTERFACE Mode.
        - If any Mode != "simulated", report error.
        """
        # Step 1: Collect all SRI references from Eth-Switch INTERFACE-TREF
        eth_sri_refs = set()
        for eth_switch in self.root.xpath("//Eth-Switch"):
            eth_sri_refs.update(eth_switch.xpath("INTERFACE-TREF/@DEST"))

        for sri_ref in eth_sri_refs:
            sri_name = self._extract_short_name_from_dest(sri_ref)
            swcs = set()
            for port_type, port_xpath, tref_xpath in [
                ("Provider", ".//P-PORT-PROTOTYPE", "PROVIDED-INTERFACE-TREF/@DEST"),
                ("Required", ".//R-PORT-PROTOTYPE", "REQUIRED-INTERFACE-TREF/@DEST"),
            ]:
                for port in self.root.xpath(port_xpath):
                    trefs = port.xpath(tref_xpath)
                    if sri_ref in trefs:
                        swc = port.xpath("ancestor::APPLICATION-SW-COMPONENT-TYPE")
                        if swc:
                            swcs.add(swc[0])

            for mapping in self.root.xpath("//HW-SW-MAPPING"):
                cluster_ref = mapping.get("ClusterRef", "")
                cluster_name = cluster_ref.split("/")[-1]
                cluster = self.root.xpath(
                    f".//CortexA53[SHORT-NAME/@name='{cluster_name}']"
                )
                if not cluster:
                    continue
                soc = (
                    cluster[0].xpath("ancestor::SoCs")[0]
                    if cluster[0].xpath("ancestor::SoCs")
                    else None
                )
                if soc is None:
                    continue
                soc_name = soc.xpath("SHORT-NAME/@name") or soc.xpath(
                    "SHORT-NAME/text()"
                )
                soc_name_str = soc_name[0] if soc_name else "(unknown)"
                eth_if = soc.xpath("ETHERNET-INTERFACE")
                for crm in mapping.xpath("Core-Runnable-Mapping"):
                    runnable_ref = crm.get("RunnableRef", "")
                    for swc in swcs:
                        swc_name = swc.xpath("SHORT-NAME/@name") or swc.xpath(
                            "SHORT-NAME/text()"
                        )
                        swc_name_str = swc_name[0] if swc_name else "(unknown)"
                        if f"/{swc_name_str}/" in runnable_ref:
                            if eth_if:
                                mode = eth_if[0].get("Mode", "simulated")
                                if mode != "simulated":
                                    xpath = self.tree.getpath(crm)
                                    self.errors.append(
                                        ValidationError(
                                            rule_number=32,
                                            severity="error",
                                            message=f"Rule 32 violated: SoC '{soc_name_str}' running SWC '{swc_name_str}' for SRI '{sri_name}' has ETHERNET-INTERFACE Mode='{mode}' (should be 'simulated').",
                                            xpath=xpath,
                                        )
                                    )

    # ============================================================================
    # Rule 38: Prebuilt app PATH existence check
    # ============================================================================
    def _validate_rule_38(self):
        """
        ⚠️ Rule 38: PRE-BUILT-APPLICATION PATH/@DEST must exist and be executable.

        Why Python: Filesystem checks cannot be done in Schematron. Schematron
        validates format (contains '.'), but Python checks actual file existence
        and executable permissions.
        """
        if not self.check_filesystem:
            return  # Skip filesystem checks if disabled

        for path_elem in self.root.xpath("//PRE-BUILT-APPLICATION/PATH"):
            dest = path_elem.get("DEST", "").strip()
            if not dest:
                continue

            # Convert to absolute path (relative to XML file directory)
            xml_dir = Path(self.xml_file).parent
            file_path = xml_dir / dest

            if not file_path.exists():
                xpath = self.tree.getpath(path_elem)
                self.errors.append(
                    ValidationError(
                        rule_number=38,
                        severity="error",
                        message=f"PRE-BUILT-APPLICATION PATH '@DEST={dest}' does not exist on filesystem",
                        xpath=xpath,
                    )
                )
            elif not os.access(file_path, os.X_OK):
                xpath = self.tree.getpath(path_elem)
                self.errors.append(
                    ValidationError(
                        rule_number=38,
                        severity="warning",
                        message=f"PRE-BUILT-APPLICATION PATH '@DEST={dest}' exists but is not executable",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 39: Toolchain/compile verification
    # ============================================================================
    def _validate_rule_39(self):
        """
        Rule 39: Each prebuilt app mapping must reference a real cluster/core and a real prebuilt app.
        - For each Core-PrebuiltApplication-Mapping and Cluster-PrebuiltApplication-Mapping:
            - ClusterRef must point to a real cluster
            - PrebuiltApplicationRef must point to a real PRE-BUILT-APPLICATION
        """
        # Build set of valid cluster paths
        valid_clusters = set()
        for cluster in self.root.xpath("//CPU_Cluster"):
            cluster_name = cluster.xpath(".//SHORT-NAME/@name")
            soc = cluster.xpath("ancestor::SoCs[1]/SHORT-NAME/@name")
            ecu = cluster.xpath("ancestor::ECUs[1]/SHORT-NAME/@name")
            if cluster_name and soc and ecu:
                valid_clusters.add(f"/{ecu[0]}/{soc[0]}/{cluster_name[0]}")

        # Build set of valid prebuilt app refs
        valid_prebuilt = set()
        for app in self.root.xpath("//PRE-BUILT-APPLICATION"):
            app_name = app.xpath("SHORT-NAME/@name")
            if app_name:
                valid_prebuilt.add(f"/{app_name[0]}")

        # Check all HW-SW-MAPPINGs
        for mapping in self.root.xpath("//HW-SW-MAPPING"):
            # Note: existence of ClusterRef is now validated by Rule 76b to avoid duplicate
            # reporting between Rule 39 and Rule 76 responsibilities.
            xpath = self.tree.getpath(mapping)
            cluster_ref = mapping.get("ClusterRef")

            # Find the referenced cluster element (if valid)
            cluster_elem = None
            if cluster_ref and cluster_ref in valid_clusters:
                # Extract cluster name from ref
                parts = cluster_ref.strip("/").split("/")
                if len(parts) == 3:
                    ecu_name, soc_name, cluster_name = parts
                    cluster_xpath = f"//ECUs[SHORT-NAME/@name='{ecu_name}']/SoCs[SHORT-NAME/@name='{soc_name}']//CPU_Cluster[.//SHORT-NAME/@name='{cluster_name}']"
                    clusters = self.root.xpath(cluster_xpath)
                    if clusters:
                        cluster_elem = clusters[0]

            # Determine CoresPerCluster for this cluster (default 1 if not found)
            cores_per_cluster = 1
            if cluster_elem is not None:
                # Try to find CoresPerCluster attribute in ARMV8-Family/CortexA53 or similar
                cortex = cluster_elem.xpath(
                    ".//CortexA53 | .//CortexA72 | .//CortexA57 | .//CortexA55"
                )
                if cortex:
                    cpc = cortex[0].get("CoresPerCluster")
                    if cpc and cpc.isdigit():
                        cores_per_cluster = int(cpc)

            # Prebuilt-application existence checks removed from Rule 39 to avoid
            # duplicate reporting. PrebuiltApplicationRef resolution is handled by
            # the dedicated prebuilt-app rules (e.g., Rule 77/78) or by model-level
            # checks, and CoreId range is now enforced by Rule 79.

    # ============================================================================
    # Rule 40: PRE-BUILT-APPLICATION/PATH must exist and be executable
    # ============================================================================
    def _validate_rule_40(self):
        """
        Rule 40: Each PRE-BUILT-APPLICATION/PATH must exist on disk and be executable.
        Note: The actual filesystem logic already exists under Rule 38. To align numbering
        without duplicating logic, we call Rule 38 and retag any new errors from 38 -> 40.
        """
        before_len = len(self.errors)
        # Delegate to Rule 38 if available
        if hasattr(self, "_validate_rule_38"):
            self._validate_rule_38()
        else:
            return

        # Retag any new Rule 38 errors as Rule 40
        for err in self.errors[before_len:]:
            if getattr(err, "rule_number", None) == 38:
                err.rule_number = 40
                if hasattr(err, "message") and isinstance(err.message, str):
                    err.message = err.message.replace("Rule 38", "Rule 40")

    # ============================================================================
    # Rule 90: InterfaceReference → SRI resolution (moved from old Rule 40)
    # ============================================================================
    def _validate_rule_90(self):
        """
        Rule 90: InterfaceReference must point to existing SENDER-RECEIVER-INTERFACE.

        Why Python: Requires DEST normalization and lookup in SRI index.
        """
        for iref in self.root.xpath("//InterfaceReference"):
            dest = iref.get("DEST", "").strip()
            if not dest:
                xpath = self.tree.getpath(iref)
                self.errors.append(
                    ValidationError(
                        rule_number=90,
                        severity="error",
                        message="InterfaceReference has empty @DEST",
                        xpath=xpath,
                    )
                )
                continue

            # Extract SHORT-NAME and check against SRI index
            short_name = self._extract_short_name_from_dest(dest)
            if short_name not in self.sri_index:
                xpath = self.tree.getpath(iref)
                self.errors.append(
                    ValidationError(
                        rule_number=90,
                        severity="error",
                        message=f"InterfaceReference @DEST='{dest}' does not resolve to existing SENDER-RECEIVER-INTERFACE",
                        xpath=xpath,
                    )
                )

            # ============================================================================
            # Rule 3: Port interface reference existence check (Python)
            # ============================================================================

    # ============================================================================
    # Rule 3: Port interface reference existence check (Python)
    # ============================================================================
    def _validate_rule_3(self):
        """
        Rule 3: Each P-PORT-PROTOTYPE and R-PORT-PROTOTYPE must reference an existing SENDER-RECEIVER-INTERFACE.

        This rule applies to ALL ports in the document:
        - SWC ports (APPLICATION-SW-COMPONENT-TYPE)
        - HWIP ports (Generic_Hardware) - also covers Rule 58

        Rule 58 ("Each Hwip Port is connected to a valid Sender-Receiver Interface") is a
        specific case of Rule 3 and is automatically enforced by this implementation.

        Implementation:
        - Schematron (lines 38-40, 51-55): Checks DEST is non-empty and looks like a path (contains '/')
        - Python (this function): Validates that the referenced SRI actually exists in the model

        Why Python: Requires DEST normalization and lookup in SRI index.
        """
        for port in self.root.xpath("//P-PORT-PROTOTYPE | //R-PORT-PROTOTYPE"):
            # Check PROVIDED-INTERFACE-TREF and REQUIRED-INTERFACE-TREF
            provided_refs = port.xpath(".//PROVIDED-INTERFACE-TREF/@DEST")
            required_refs = port.xpath(".//REQUIRED-INTERFACE-TREF/@DEST")
            for dest in provided_refs + required_refs:
                short_name = self._extract_short_name_from_dest(dest)
                if short_name and short_name not in self.sri_index:
                    xpath = self.tree.getpath(port)
                    self.errors.append(
                        ValidationError(
                            rule_number=3,
                            severity="error",
                            message=f"Port references interface '{dest}', but no SENDER-RECEIVER-INTERFACE with SHORT-NAME='{short_name}' exists in the model.",
                            xpath=xpath,
                        )
                    )
                elif not short_name:
                    xpath = self.tree.getpath(port)
                    self.errors.append(
                        ValidationError(
                            rule_number=3,
                            severity="error",
                            message="Port interface reference DEST is empty or not a valid path. Please check the format.",
                            xpath=xpath,
                        )
                    )

    # ============================================================================
    # Rule 4: Each Required port connected to exactly one DATA-READ-ACCESS
    # ============================================================================
    def _validate_rule_4(self):
        """
        Rule 4: Each R-PORT-PROTOTYPE must be referenced by exactly one DATA-READ-ACCESS.
        Why Python: Requires counting references across all DATA-READ-ACCESS elements.
        """
        # Build a map of R-PORT SHORT-NAME to reference count
        rport_ref_count = {}

        # Collect all R-PORT-PROTOTYPE SHORT-NAMEs with their full paths
        for rport in self.root.xpath("//R-PORT-PROTOTYPE"):
            port_name_nodes = rport.xpath("SHORT-NAME/@name")
            if not port_name_nodes:
                continue
            port_name = port_name_nodes[0]

            # Build the expected reference path (e.g., "/SWCName/PortName")
            swc = rport.xpath("ancestor::APPLICATION-SW-COMPONENT-TYPE")
            if swc:
                swc_name_nodes = swc[0].xpath("SHORT-NAME/@name")
                if swc_name_nodes:
                    swc_name = swc_name_nodes[0]
                    port_path = f"/{swc_name}/{port_name}"
                    rport_ref_count[port_path] = {"count": 0, "element": rport}

        # Count references from DATA-READ-ACCESS
        for read_access in self.root.xpath("//DATA-READ-ACCESS"):
            port_refs = read_access.xpath(".//PORT-PROTOTYPE-REF/@DEST")
            for ref in port_refs:
                if ref in rport_ref_count:
                    rport_ref_count[ref]["count"] += 1

        # Validate: each R-PORT must have exactly 1 reference
        for port_path, data in rport_ref_count.items():
            count = data["count"]
            element = data["element"]
            port_name_nodes = element.xpath("SHORT-NAME/@name")
            port_name = port_name_nodes[0] if port_name_nodes else "unknown"

            xpath = self.tree.getpath(element)
            if count == 0:
                self.errors.append(
                    ValidationError(
                        rule_number=4,
                        severity="error",
                        message=f"Required port '{port_name}' (at {port_path}) has ZERO DATA-READ-ACCESS references. Each R-PORT must be connected to exactly one DATA-READ-ACCESS.",
                        xpath=xpath,
                    )
                )
            elif count > 1:
                self.errors.append(
                    ValidationError(
                        rule_number=4,
                        severity="error",
                        message=f"Required port '{port_name}' (at {port_path}) has {count} DATA-READ-ACCESS references. Each R-PORT must be connected to exactly ONE DATA-READ-ACCESS.",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 44: SoC name valid C identifier
    # ============================================================================
    def _validate_rule_44(self):
        """
        Rule 44: Each ECU name is valid against C variable naming rules.

        Checks:
        - Starts with letter or underscore
        - Only letters, digits, underscores
        - Not a C keyword
        """
        for ecu in self.root.xpath("//ECUs"):
            name_nodes = ecu.xpath("SHORT-NAME/@name")
            if not name_nodes:
                continue

            name = name_nodes[0]
            is_valid, error_msg = self._validate_c_identifier(name)

            if not is_valid:
                xpath = self.tree.getpath(ecu)
                self.errors.append(
                    ValidationError(
                        rule_number=44,
                        severity="error",
                        message=f"ECU name '{name}' {error_msg}",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rules 48 & 54: D2D configurations connected to valid SoC/Chiplet
    # ============================================================================
    def _validate_rule_47(self):
        """
        🚧 Rules 48 & 54: D2D configuration references must resolve to existing SoC or Chiplet.

        Rule 48: Each SoC each D2D Configuration is connected to a valid Chiplet.
        Rule 54: Each Chiplet each D2D Configuration is connected to a valid SoC/Chiplet.

        NOTE: Despite Rule 48 text saying "Chiplet", the XSD DestChipletRef documentation
              explicitly allows both path formats:
              - /ecu-name/soc-name (points to SoC)
              - /ecu-name/soc-name/chiplet-name (points to Chiplet)

              Therefore, we validate that ALL D2D references (both SoC-level and Chiplet-level)
              resolve to either a valid SoC OR Chiplet, following the XSD specification.

        Why Python: Requires path normalization and cross-element resolution.
        """
        # Support both legacy and XSD-aligned spellings:
        #  - Elements: D2D-Configuration, D2DConfiguration, D2D_Configuration
        #  - Attributes: DEST (legacy) and DestChipletRef (XSD)
        for d2d in self.root.xpath(
            "//D2D-Configuration | //D2DConfiguration | //D2D_Configuration"
        ):
            dest = (d2d.get("DEST") or d2d.get("DestChipletRef") or "").strip()
            if not dest:
                continue

            short_name = self._extract_short_name_from_dest(dest)
            # XSD allows D2D to point to either SoC or Chiplet
            if (
                short_name not in self.soc_index
                and short_name not in self.chiplet_index
            ):
                xpath = self.tree.getpath(d2d)
                self.errors.append(
                    ValidationError(
                        rule_number=54,  # Report as Rule 54 (more general rule covering both SoC and Chiplet D2D)
                        severity="error",
                        message=f"D2D configuration reference '{dest}' does not resolve to an existing SoC or Chiplet",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 58: Hwip Provider/Required not pointing to same SRI (robust)
    # ============================================================================
    def _validate_rule_58(self):
        """
        ⚠️ Rule 58: Hwip must not have Provider and Required ports pointing to same SRI.

        Why Python: Schematron has a conservative check but it's brittle for complex
        nested structures. Python can robustly resolve PORT-REF/@DEST to SRI names.
        """
        for hwip in self.root.xpath("//Hwip"):
            provider_sris = set()
            required_sris = set()

            # Find all Provider ports and extract their SRI references
            for provider in hwip.xpath(".//Port[Provider]"):
                port_refs = provider.xpath(".//PORT-REF/@DEST")
                for ref in port_refs:
                    sri_name = self._extract_short_name_from_dest(ref)
                    provider_sris.add(sri_name)

            # Find all Required ports and extract their SRI references
            for required in hwip.xpath(".//Port[Required]"):
                port_refs = required.xpath(".//PORT-REF/@DEST")
                for ref in port_refs:
                    sri_name = self._extract_short_name_from_dest(ref)
                    required_sris.add(sri_name)

            # Check for overlap
            overlap = provider_sris & required_sris
            if overlap:
                hwip_name = hwip.get("name", "unnamed")
                xpath = self.tree.getpath(hwip)
                self.errors.append(
                    ValidationError(
                        rule_number=58,
                        severity="error",
                        message=f"Hwip '{hwip_name}' has Provider and Required ports pointing to same SRI(s): {overlap}",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 64: Trigger Runnable/Event mapped to Core in same Chiplet/SoC
    # ============================================================================
    # ============================================================================
    # Rule 70: CPU cluster name and OS type validation
    # ============================================================================
    def _validate_rule_70(self):
        """
        Rule 70: CPU_Cluster must:
        1. Have a name that is a valid C identifier (matches pattern ^[a-zA-Z_][a-zA-Z0-9_]*$ and not a C keyword)
        2. Declare a supported Operating-System type (Linux or Nucleus_RTOS)

        Why Python: XPath 1.0 cannot check regex patterns or C keyword lists.
        Schematron only does basic checks (empty, spaces).

        Note: Core-specific OS restrictions are validated in Rule 72.
        """
        # XSD restricts OS to Nucleus_RTOS or Linux. Keep Python aligned and explicit.
        supported_os_types = {"Nucleus_RTOS", "Linux"}
        restricted_cores = {
            "CortexM7",
            "CortexR52",
        }  # Cores that can ONLY run Nucleus_RTOS

        for cluster in self.root.xpath("//CPU_Cluster"):
            # Part 1: Validate CPU_Cluster name (C identifier rules)
            # Path: CPU_Cluster/*/CortexA72/SHORT-NAME or similar ARM family variants
            name_elem = cluster.xpath(
                ".//*[starts-with(local-name(), 'Cortex')]/SHORT-NAME"
            )
            cluster_name = None
            core_type = None

            if name_elem:
                cluster_name = name_elem[0].get("name")
                if cluster_name:
                    is_valid, error_msg = self._validate_c_identifier(cluster_name)
                    if not is_valid:
                        xpath = self.tree.getpath(name_elem[0])
                        self.errors.append(
                            ValidationError(
                                rule_number=70,
                                severity="error",
                                message=f"CPU_Cluster SHORT-NAME '{cluster_name}' {error_msg}",
                                xpath=xpath,
                            )
                        )

                # Get core type (CortexM7, CortexR52, CortexA53, etc.)
                core_elem = name_elem[0].getparent()
                if core_elem is not None:
                    core_type = etree.QName(core_elem).localname

            # Part 2: Validate OS type
            os_elem = cluster.xpath("Operating-System/*")
            if not os_elem:
                xpath = self.tree.getpath(cluster)
                self.errors.append(
                    ValidationError(
                        rule_number=70,
                        severity="error",
                        message="CPU_Cluster has no Operating-System child element",
                        xpath=xpath,
                    )
                )
                continue

            # Extract OS type from child element name
            os_type = etree.QName(os_elem[0]).localname

            # Check if OS type is in supported list
            if os_type not in supported_os_types:
                xpath = self.tree.getpath(cluster)
                self.errors.append(
                    ValidationError(
                        rule_number=70,
                        severity="error",
                        message=f"CPU_Cluster OS type '{os_type}' is not in supported list: {supported_os_types}",
                        xpath=xpath,
                    )
                )
                continue

            # Rule 72: Core-specific OS restrictions (CortexM7/R52 can ONLY run Nucleus_RTOS)
            # Implemented here for efficiency (same loop over CPU_Clusters)
            if core_type and core_type in restricted_cores:
                if os_type != "Nucleus_RTOS":
                    xpath = self.tree.getpath(cluster)
                    cluster_display_name = (
                        cluster_name if cluster_name else f"unnamed {core_type} cluster"
                    )
                    self.errors.append(
                        ValidationError(
                            rule_number=72,
                            severity="error",
                            message=f"CPU_Cluster '{cluster_display_name}' with core type '{core_type}' can ONLY run Nucleus_RTOS. Found OS type '{os_type}'. CortexM7 and CortexR52 cores do not support Linux or other operating systems.",
                            xpath=xpath,
                        )
                    )

    # ============================================================================
    # Rule 71: Linux filesystem checks
    # ============================================================================
    def _validate_rule_71(self):
        """
        Rule 71: CPU clusters running Linux must use supported filesystems.

        Why Python: Requires inspecting model details or config files for
        filesystem types. May need external validation or model-specific knowledge.
        """
        if not self.check_filesystem:
            return

        # Placeholder: Full implementation would check filesystem declarations
        # This is model-specific and may require additional configuration
        pass

    # ============================================================================
    # Rule 73: Linux filesystem policy (model-level)
    # ============================================================================
    # def _validate_rule_73(self):
    #     """
    #     Rule 73: Each CPU_Cluster running Linux must use only supported filesystems (policy).
    #     Current policy: only Buildroot_File_System is supported for Linux.
    #     This is a model-level check (not filesystem existence), so it always runs.
    #     """
    #     for cluster in self.root.xpath("//CPU_Cluster"):
    #         os_parent = cluster.find("Operating-System")
    #         if os_parent is None:
    #             continue
    #         os_child = None
    #         # Find first OS child element
    #         for child in os_parent:
    #             if isinstance(child.tag, str):
    #                 os_child = child
    #                 break
    #         if os_child is None:
    #             continue
    #         os_type = etree.QName(os_child).localname
    #         if os_type != 'Linux':
    #             continue
    #         # Collect filesystem children under Linux
    #         fs_children = [etree.QName(c).localname for c in os_child if isinstance(c.tag, str)]
    #         if len(fs_children) != 1 or fs_children[0] != 'Buildroot_File_System':
    #             xpath = self.tree.getpath(cluster)
    #             found = fs_children[0] if fs_children else '(none)'
    #             self.errors.append(ValidationError(
    #                 rule_number=73,
    #                 severity='error',
    #                 message=("Rule 73 violated: CPU_Cluster running Linux must use 'Buildroot_File_System' "
    #                          f"(found: '{found}')."),
    #                 xpath=xpath
    #             ))

    # ============================================================================
    # Rule 74: HwSwMapping ClusterRef resolution
    # ============================================================================
    def _validate_rule_74(self):
        """
        Rule 74: Each CPU cluster can either be connected to a runnable or prebuilt app mappings, but not both.
        For each CPU_Cluster, check if it is referenced by both Core-Runnable-Mapping and Core-PrebuiltApplication-Mapping (or Cluster-PrebuiltApplication-Mapping).
        If so, report an error.
        """
        # Build a map: cluster_short_name -> set of mapping types
        cluster_map = {}
        # Collect all Core-Runnable-Mapping references
        for mapping in self.root.xpath(
            "//Core-Runnable-Mapping | //CoreRunnableMapping"
        ):
            cluster_refs = mapping.xpath("parent::*//@ClusterRef")
            if cluster_refs:
                cluster_short = self._extract_short_name_from_dest(cluster_refs[0])
                cluster_map.setdefault(cluster_short, set()).add("runnable")
        # Collect all Core-PrebuiltApplication-Mapping references
        for mapping in self.root.xpath(
            "//Core-PrebuiltApplication-Mapping | //CorePrebuiltAppMapping"
        ):
            cluster_refs = mapping.xpath("parent::*//@ClusterRef")
            if cluster_refs:
                cluster_short = self._extract_short_name_from_dest(cluster_refs[0])
                cluster_map.setdefault(cluster_short, set()).add("prebuilt")
        # Collect all Cluster-PrebuiltApplication-Mapping references
        for mapping in self.root.xpath(
            "//Cluster-PrebuiltApplication-Mapping | //ClusterPrebuiltAppMapping"
        ):
            # ClusterRef may be on the child (legacy) or on the parent HW-SW-MAPPING container.
            cluster_ref = mapping.get("ClusterRef", "").strip()
            if not cluster_ref:
                # look on the parent element(s)
                parent_cluster_refs = mapping.xpath("parent::*//@ClusterRef")
                if parent_cluster_refs:
                    cluster_ref = parent_cluster_refs[0].strip()
            if cluster_ref:
                cluster_short = self._extract_short_name_from_dest(cluster_ref)
                cluster_map.setdefault(cluster_short, set()).add("prebuilt")
        # Now check for clusters with both
        for cluster_short, types in cluster_map.items():
            if "runnable" in types and "prebuilt" in types:
                # Find all mappings referencing this cluster for error reporting
                # Core-Runnable-Mapping
                for mapping in self.root.xpath(
                    f"//Core-Runnable-Mapping | //CoreRunnableMapping"
                ):
                    cluster_refs = mapping.xpath("parent::*//@ClusterRef")
                    if (
                        cluster_refs
                        and self._extract_short_name_from_dest(cluster_refs[0])
                        == cluster_short
                    ):
                        xpath = self.tree.getpath(mapping)
                        self.errors.append(
                            ValidationError(
                                rule_number=74,
                                severity="error",
                                message=f"CPU_Cluster '{cluster_short}' is referenced by both runnable and prebuilt app mappings (not allowed)",
                                xpath=xpath,
                            )
                        )
                # Core-PrebuiltApplication-Mapping
                for mapping in self.root.xpath(
                    f"//Core-PrebuiltApplication-Mapping | //CorePrebuiltAppMapping"
                ):
                    cluster_refs = mapping.xpath("parent::*//@ClusterRef")
                    if (
                        cluster_refs
                        and self._extract_short_name_from_dest(cluster_refs[0])
                        == cluster_short
                    ):
                        xpath = self.tree.getpath(mapping)
                        self.errors.append(
                            ValidationError(
                                rule_number=74,
                                severity="error",
                                message=f"CPU_Cluster '{cluster_short}' is referenced by both runnable and prebuilt app mappings (not allowed)",
                                xpath=xpath,
                            )
                        )
                # Cluster-PrebuiltApplication-Mapping
                for mapping in self.root.xpath(
                    f"//Cluster-PrebuiltApplication-Mapping | //ClusterPrebuiltAppMapping"
                ):
                    cluster_ref = mapping.get("ClusterRef", "").strip()
                    if not cluster_ref:
                        parent_cluster_refs = mapping.xpath("parent::*//@ClusterRef")
                        if parent_cluster_refs:
                            cluster_ref = parent_cluster_refs[0].strip()
                    if (
                        cluster_ref
                        and self._extract_short_name_from_dest(cluster_ref)
                        == cluster_short
                    ):
                        xpath = self.tree.getpath(mapping)
                        self.errors.append(
                            ValidationError(
                                rule_number=74,
                                severity="error",
                                message=f"CPU_Cluster '{cluster_short}' is referenced by both runnable and prebuilt app mappings (not allowed)",
                                xpath=xpath,
                            )
                        )

    # Note: Rule 75 implementation (Nucleus cluster mapped to runnable) is defined earlier

    # ============================================================================
    # Rule 76: CoreRunnableMapping RunnableRef resolution
    # ============================================================================
    def _validate_rule_76(self):
        """
        ⚠️ Rule 76: Core-Runnable-Mapping/@RunnableRef must resolve to existing RUNNABLE-ENTITY.

        Why Python: Schematron uses substring match. Python performs exact lookup,
        handling scope ambiguity (same runnable name in multiple SWCs).
        """
        for mapping in self.root.xpath(
            "//Core-Runnable-Mapping | //CoreRunnableMapping"
        ):
            runnable_ref = mapping.get("RunnableRef", "").strip()
            if not runnable_ref:
                xpath = self.tree.getpath(mapping)
                self.errors.append(
                    ValidationError(
                        rule_number=78,
                        severity="error",
                        message="Core-Runnable-Mapping has empty @RunnableRef",
                        xpath=xpath,
                    )
                )
                continue

            short_name = self._extract_short_name_from_dest(runnable_ref)
            if short_name not in self.runnable_index:
                xpath = self.tree.getpath(mapping)
                self.errors.append(
                    ValidationError(
                        rule_number=78,
                        severity="error",
                        message=f"Core-Runnable-Mapping @RunnableRef='{runnable_ref}' does not resolve to existing RUNNABLE-ENTITY",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 76b: Each HW-SW-MAPPING ClusterRef must resolve to an existing CPU_Cluster
    # ============================================================================
    def _validate_rule_76b(self):
        """
        Rule 76b (related): Each HW-SW-MAPPING/@ClusterRef must point to an existing CPU_Cluster element.
        This catches typos or mappings to clusters that don't exist in the AR-PACKAGE.
        """
        for mapping in self.root.xpath("//HW-SW-MAPPING"):
            cluster_ref = (mapping.get("ClusterRef") or "").strip()
            if not cluster_ref:
                # already handled elsewhere (missing ClusterRef may be structural XSD error)
                continue
            cluster_short = self._extract_short_name_from_dest(cluster_ref)
            if cluster_short not in self.cluster_index:
                xpath = self.tree.getpath(mapping)
                self.errors.append(
                    ValidationError(
                        rule_number=76,
                        severity="error",
                        message=(
                            f"HW-SW-MAPPING ClusterRef '{cluster_ref}' does not resolve to any CPU_Cluster (no SHORT-NAME '{cluster_short}' found)."
                        ),
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 76 (HW): CPU Cluster Frequency must be 1000000000 Hz (1 GHz) for Linux OS
    # ============================================================================
    def _validate_rule_76_hw_frequency(self):
        """
        Rule 76 (HW): CPU Cluster Frequency must be exactly 1000000000 Hz (1 GHz) for Linux OS.
        
        This is a requirement from the Innexis Architect Explorer tool.
        """
        for cpu_cluster in self.root.xpath("//CPU_Cluster | //CPU-Cluster | //CPUCluster"):
            # Check if this cluster runs Linux OS
            os_nodes = cpu_cluster.xpath(".//Operating-System | .//OS | .//OperatingSystem")
            is_linux = False
            
            for os_node in os_nodes:
                # Check for Linux child element
                linux_nodes = os_node.xpath(".//Linux")
                if linux_nodes:
                    is_linux = True
                    break
                # Check text content
                if os_node.text and "linux" in os_node.text.lower():
                    is_linux = True
                    break
            
            # Also check for Linux in descendant elements
            if not is_linux:
                if cpu_cluster.xpath(".//*[contains(local-name(), 'Linux') or contains(local-name(), 'LINUX')]"):
                    is_linux = True
            
            if not is_linux:
                continue  # Skip non-Linux clusters
            
            # Get cluster name for error message
            cluster_name = "unnamed"
            short_name = cpu_cluster.find(".//SHORT-NAME")
            if short_name is not None:
                cluster_name = short_name.get("name", "unnamed")
            
            # Find Frequency element under the CPU variant (CortexA72, etc.)
            freq_nodes = cpu_cluster.xpath(".//Frequency")
            if not freq_nodes:
                xpath = self.tree.getpath(cpu_cluster)
                self.errors.append(
                    ValidationError(
                        rule_number=76,
                        severity="error",
                        message=f'CPU_Cluster "{cluster_name}" running Linux OS is missing Frequency value',
                        xpath=xpath,
                    )
                )
                continue
            
            # Check frequency value
            for freq_node in freq_nodes:
                freq_value = freq_node.get("value", "").strip()
                if not freq_value:
                    # Also check text content
                    freq_value = (freq_node.text or "").strip()
                
                if freq_value:
                    try:
                        freq_int = int(freq_value)
                        if freq_int != 1000000000:
                            xpath = self.tree.getpath(freq_node)
                            self.errors.append(
                                ValidationError(
                                    rule_number=76,
                                    severity="error",
                                    message=f'CPU_Cluster "{cluster_name}" running Linux OS has invalid Frequency: {freq_int} Hz. Must be exactly 1000000000 Hz (1 GHz)',
                                    xpath=xpath,
                                )
                            )
                    except (ValueError, TypeError):
                        xpath = self.tree.getpath(freq_node)
                        self.errors.append(
                            ValidationError(
                                rule_number=76,
                                severity="error",
                                message=f'CPU_Cluster "{cluster_name}" running Linux OS has invalid Frequency value: "{freq_value}" (must be numeric)',
                                xpath=xpath,
                            )
                        )

    # ============================================================================
    # Timing Event Period validation: must be at least 10ms
    # ============================================================================
    def _validate_timing_event_period(self):
        """
        Timing Event Period must be at least 10ms to avoid errors from Innexis Architect Explorer.
        """
        for timing_event in self.root.xpath("//TIMING-EVENT"):
            period = timing_event.find(".//PERIOD")
            if period is None:
                continue
            
            value_str = period.get("value", "").strip()
            unit = period.get("unit", "ms").strip().lower()
            
            if not value_str:
                xpath = self.tree.getpath(timing_event)
                self.errors.append(
                    ValidationError(
                        rule_number=20,
                        severity="error",
                        message="Timing Event is missing PERIOD value attribute",
                        xpath=xpath,
                    )
                )
                continue
            
            try:
                value = float(value_str)
                # Convert to ms if needed
                if unit == "us":
                    value_ms = value / 1000.0
                elif unit == "s":
                    value_ms = value * 1000.0
                elif unit == "ns":
                    value_ms = value / 1000000.0
                else:  # ms or default
                    value_ms = value
                
                if value_ms < 10:
                    xpath = self.tree.getpath(timing_event)
                    self.errors.append(
                        ValidationError(
                            rule_number=20,
                            severity="error",
                            message=f"Timing Event Period must be at least 10ms. Found: {value_str} {unit} ({value_ms:.2f} ms)",
                            xpath=xpath,
                        )
                    )
            except (ValueError, TypeError):
                xpath = self.tree.getpath(timing_event)
                self.errors.append(
                    ValidationError(
                        rule_number=20,
                        severity="error",
                        message=f"Timing Event PERIOD has invalid value: '{value_str}' (must be numeric)",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Simulation-Time validation: must be at least 3000 ms
    # ============================================================================
    def _validate_simulation_time(self):
        """
        Simulation-Time must be at least 3000 ms to avoid warnings from Innexis Architect Explorer.
        """
        for sim_time in self.root.xpath("//Simulation-Time | //SimulationTime"):
            value_str = sim_time.get("value", "").strip()
            unit = sim_time.get("unit", "ms").strip().lower()
            
            if not value_str:
                xpath = self.tree.getpath(sim_time)
                self.errors.append(
                    ValidationError(
                        rule_number=0,  # General validation rule
                        severity="error",
                        message="Simulation-Time is missing value attribute",
                        xpath=xpath,
                    )
                )
                continue
            
            try:
                value = float(value_str)
                # Convert to ms if needed
                if unit == "us":
                    value_ms = value / 1000.0
                elif unit == "s":
                    value_ms = value * 1000.0
                elif unit == "ns":
                    value_ms = value / 1000000.0
                else:  # ms or default
                    value_ms = value
                
                if value_ms < 3000:
                    xpath = self.tree.getpath(sim_time)
                    self.errors.append(
                        ValidationError(
                            rule_number=0,  # General validation rule
                            severity="error",
                            message=f"Simulation-Time must be at least 3000 ms. Found: {value_str} {unit} ({value_ms:.2f} ms)",
                            xpath=xpath,
                        )
                    )
            except (ValueError, TypeError):
                xpath = self.tree.getpath(sim_time)
                self.errors.append(
                    ValidationError(
                        rule_number=0,
                        severity="error",
                        message=f"Simulation-Time has invalid value: '{value_str}' (must be numeric)",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 77: CorePrebuiltAppMapping CoreId validation
    # ============================================================================
    def _validate_rule_77(self):
        """
        ⚠️ Rule 77: Core-PrebuiltApplication-Mapping/@CoreId must be valid for cluster.

        Why Python: Similar to Rule 75, requires CoreId vs CoresPerCluster check
        plus PrebuiltApplicationRef resolution.
        """
        for mapping in self.root.xpath(
            "//Core-PrebuiltApplication-Mapping | //CorePrebuiltAppMapping"
        ):
            core_id_str = mapping.get("CoreId", "").strip()
            app_ref = mapping.get("PrebuiltApplicationRef", "").strip()
            cluster_ref = mapping.xpath("parent::*//@ClusterRef")

            if not core_id_str:
                continue

            try:
                core_id = int(core_id_str)
            except ValueError:
                continue  # Schematron checks numeric format

            # NOTE: CoreId range validation moved to Rule 79 to avoid duplicate checks
            # (see _validate_rule_79). This function keeps the PrebuiltApplicationRef
            # resolution logic only.
            # Note: PrebuiltApplicationRef existence checks are handled elsewhere
            # (Rule 39) and have been suppressed here to keep CoreId range checks
            # centralized in Rule 79. This avoids duplicate reporting for the same
            # issue when validating small, focused samples.

    # ============================================================================
    # Rule 79: CorePrebuiltAppMapping CoreId validation
    # ============================================================================
    def _validate_rule_79(self):
        """
        ⚠️ Rule 79: Each Core-PrebuiltApplication-Mapping/@CoreId must be valid for the
        referenced cluster (0-based and less than CoresPerCluster).

        Why Python: Requires looking up the referenced CPU_Cluster and reading its
        CoresPerCluster value, which is dynamic per model instance.
        """
        for mapping in self.root.xpath(
            "//Core-PrebuiltApplication-Mapping | //CorePrebuiltAppMapping"
        ):
            core_id_str = mapping.get("CoreId", "").strip()
            if not core_id_str:
                continue

            try:
                core_id = int(core_id_str)
            except ValueError:
                # Schematron/XSD should catch non-numeric CoreId; skip here
                continue

            cluster_ref = mapping.xpath("parent::*//@ClusterRef")
            if cluster_ref:
                cluster_ref_val = cluster_ref[0]
                cluster_name = self._extract_short_name_from_dest(cluster_ref_val)

                if cluster_name in self.cluster_index:
                    cluster_elem = self.cluster_index[cluster_name]
                    cores_per_cluster = None
                    for elem in cluster_elem.xpath(".//*[@CoresPerCluster]"):
                        try:
                            cores_per_cluster = int(elem.get("CoresPerCluster"))
                        except Exception:
                            cores_per_cluster = None
                        break

                    if cores_per_cluster is not None and core_id >= cores_per_cluster:
                        xpath = self.tree.getpath(mapping)
                        self.errors.append(
                            ValidationError(
                                rule_number=79,
                                severity="error",
                                message=f"Core-PrebuiltApplication-Mapping CoreId={core_id} out of range for cluster '{cluster_name}' (CoresPerCluster={cores_per_cluster})",
                                xpath=xpath,
                            )
                        )

    # ============================================================================
    # Rule 78: ClusterPrebuiltAppMapping resolution
    # ============================================================================
    def _validate_rule_78(self):
        """
        ⚠️ Rule 78: Cluster-PrebuiltApplication-Mapping must reference existing prebuilt app.

        Why Python: Requires PrebuiltApplicationRef resolution and optional
        filesystem checks for binary existence.
        """
        for mapping in self.root.xpath(
            "//Cluster-PrebuiltApplication-Mapping | //ClusterPrebuiltAppMapping"
        ):
            app_ref = mapping.get("PrebuiltApplicationRef", "").strip()
            if not app_ref:
                xpath = self.tree.getpath(mapping)
                self.errors.append(
                    ValidationError(
                        rule_number=78,
                        severity="error",
                        message="Cluster-PrebuiltApplication-Mapping has empty @PrebuiltApplicationRef",
                        xpath=xpath,
                    )
                )
                continue

            app_name = self._extract_short_name_from_dest(app_ref)
            if app_name not in self.prebuilt_app_index:
                xpath = self.tree.getpath(mapping)
                self.errors.append(
                    ValidationError(
                        rule_number=78,
                        severity="error",
                        message=f"Cluster-PrebuiltApplication-Mapping @PrebuiltApplicationRef='{app_ref}' does not resolve to existing PRE-BUILT-APPLICATION",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 80 (prebuilt existence for Core mappings): Core-PrebuiltApplication-Mapping must reference an existing PRE-BUILT-APPLICATION
    # ============================================================================
    def _validate_rule_80_prebuilt(self):
        """
        Rule 80: Each Core-PrebuiltApplication-Mapping/@PrebuiltApplicationRef must resolve
        to an existing PRE-BUILT-APPLICATION.

        Why Python: Existence is a cross-element lookup (DEST normalization and index lookup).
        Schematron can check path format but cannot assert model-level existence reliably.
        """
        # Build a simple index of PRE-BUILT-APPLICATION SHORT-NAME -> element
        prebuilt_index = {}
        for app in self.root.xpath("//PRE-BUILT-APPLICATION"):
            name_nodes = app.xpath("SHORT-NAME/@name")
            if name_nodes:
                prebuilt_index[name_nodes[0]] = app

        for mapping in self.root.xpath(
            "//Core-PrebuiltApplication-Mapping | //CorePrebuiltAppMapping"
        ):
            app_ref = mapping.get("PrebuiltApplicationRef", "").strip()
            if not app_ref:
                xpath = self.tree.getpath(mapping)
                self.errors.append(
                    ValidationError(
                        rule_number=80,
                        severity="error",
                        message="Core-PrebuiltApplication-Mapping has empty @PrebuiltApplicationRef",
                        xpath=xpath,
                    )
                )
                continue

            app_name = self._extract_short_name_from_dest(app_ref)
            if app_name not in prebuilt_index:
                xpath = self.tree.getpath(mapping)
                self.errors.append(
                    ValidationError(
                        rule_number=80,
                        severity="error",
                        message=f"Core-PrebuiltApplication-Mapping @PrebuiltApplicationRef='{app_ref}' does not resolve to existing PRE-BUILT-APPLICATION",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 81: ClusterPrebuiltAppMapping existence
    # ============================================================================
    def _validate_rule_81_prebuilt(self):
        """
        Rule 81: Each Cluster-PrebuiltApplication-Mapping/@PrebuiltApplicationRef must
        resolve to an existing PRE-BUILT-APPLICATION.

        Why Python: Existence resolution and normalization are best done in Python
        for accurate diagnostics and cross-element lookup.
        """
        # Build prebuilt app index
        prebuilt_index = {}
        for app in self.root.xpath("//PRE-BUILT-APPLICATION"):
            name_nodes = app.xpath("SHORT-NAME/@name")
            if name_nodes:
                prebuilt_index[name_nodes[0]] = app

        for mapping in self.root.xpath(
            "//Cluster-PrebuiltApplication-Mapping | //ClusterPrebuiltAppMapping"
        ):
            app_ref = mapping.get("PrebuiltApplicationRef", "").strip()
            if not app_ref:
                xpath = self.tree.getpath(mapping)
                self.errors.append(
                    ValidationError(
                        rule_number=81,
                        severity="error",
                        message="Cluster-PrebuiltApplication-Mapping has empty @PrebuiltApplicationRef",
                        xpath=xpath,
                    )
                )
                continue

            app_name = self._extract_short_name_from_dest(app_ref)
            if app_name not in prebuilt_index:
                xpath = self.tree.getpath(mapping)
                self.errors.append(
                    ValidationError(
                        rule_number=81,
                        severity="error",
                        message=f"Cluster-PrebuiltApplication-Mapping @PrebuiltApplicationRef='{app_ref}' does not resolve to existing PRE-BUILT-APPLICATION",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 82 (Analysis): Analysis SoC reference resolution
    # ============================================================================
    def _validate_rule_82_analysis(self):
        """
        Rule 82: Each Analysis Soc reference is connected to a valid SoC.

        This validator traverses elements under //Analysis that may reference
        a SoC (both <SocReference DEST="..."> and inline <SoC DEST="...">)
        and ensures the final path segment resolves to an existing SoC
        SHORT-NAME in the document. Schematron performs a conservative
        non-empty/@DEST check; Python provides authoritative cross-element
        resolution and clearer diagnostics.
        """
        # Look for both SocReference elements and any SoC elements under Analysis
        nodes = self.root.xpath("//Analysis//SocReference | //Analysis//SoC")
        for node in nodes:
            dest = (node.get("DEST") or "").strip()
            xpath = self.tree.getpath(node)
            if not dest:
                self.errors.append(
                    ValidationError(
                        rule_number=82,
                        severity="error",
                        message="Analysis SoC reference has empty @DEST",
                        xpath=xpath,
                    )
                )
                continue

            soc_short = self._extract_short_name_from_dest(dest)
            # Use the prebuilt soc_index (built in _build_indices) for resolution
            if not soc_short or soc_short not in self.soc_index:
                self.errors.append(
                    ValidationError(
                        rule_number=82,
                        severity="error",
                        message=(
                            f"Analysis SoC reference @DEST='{dest}' does not resolve to any SoC SHORT-NAME in the document (expected: '{soc_short}')"
                        ),
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 83: Power Analysis CPU Cluster type validation
    # ============================================================================
    def _validate_rule_83(self):
        """
        ⚠️ Rule 83: When PowerAnalysis enabled, CPU_Cluster type must be in supported list.

        Why Python: XSD represents CPU arch via nested elements (AeCpuArchType).
        Python navigates this structure to extract and validate arch type.
        """
        # Check if PowerAnalysis is enabled
        # Detect multiple ways PowerAnalysis may be enabled in documents:
        # - <PowerAnalysis enabled="true"/> (legacy)
        # - <Analysis PowerAnalysisEnabled="true" /> (attribute)
        # - <Power-Analysis-Enable> (preferred XSD element)
        power_analysis = self.root.xpath(
            "//Analysis//PowerAnalysis[@enabled='true'] | //Analysis[@PowerAnalysisEnabled='true'] | //Analysis//Power-Analysis-Enable"
        )
        if not power_analysis:
            return

        # Updated supported CPU types per Rule 83 policy
        supported_types = {
            "CortexA53",
            "CortexA57",
            "CortexA72",
            "CortexR52",
            "CortexM7",
        }

        for cluster in self.root.xpath("//CPU_Cluster"):
            # Extract CPU type from nested XSD structure (e.g., ARMV9-Family/AFM-CortexA510)
            cpu_type_elems = cluster.xpath(
                ".//*[starts-with(local-name(), 'AFM-') or starts-with(local-name(), 'RISCV')]"
            )
            if cpu_type_elems:
                cpu_type = etree.QName(cpu_type_elems[0]).localname.replace("AFM-", "")
                if cpu_type not in supported_types:
                    xpath = self.tree.getpath(cluster)
                    self.errors.append(
                        ValidationError(
                            rule_number=83,
                            severity="error",
                            message=f"Power Analysis enabled: CPU_Cluster type '{cpu_type}' not in supported list: {supported_types}",
                            xpath=xpath,
                        )
                    )

    # ============================================================================
    # Rule 81: Power Analysis CPU Cluster OS validation
    # ============================================================================
    def _validate_rule_81(self):
        """
        ⚠️ Rule 81: When PowerAnalysis enabled, CPU_Cluster OS must be in supported list.

        Why Python: XSD models OS as nested Operating-System elements. Python
        extracts and validates OS type reliably.
        """
        power_analysis = self.root.xpath(
            "//Analysis//PowerAnalysis[@enabled='true'] | //Analysis[@PowerAnalysisEnabled='true'] | //Analysis//Power-Analysis-Enable"
        )
        if not power_analysis:
            return

        # Note: enforcement of an externally maintained "supported OS" policy
        # may be product-specific. Per user request, this enforcement is
        # currently allowed to be disabled in the validation flow. The
        # canonical supported list should not be hard-coded here long-term;
        # move to a config file if/when the policy becomes available.
        supported_os = {"Nucleus_RTOS", "Linux", "FreeRTOS"}

        for cluster in self.root.xpath("//CPU_Cluster"):
            os_elem = cluster.xpath("Operating-System/*")
            if os_elem:
                os_type = etree.QName(os_elem[0]).localname
                if os_type not in supported_os:
                    xpath = self.tree.getpath(cluster)
                    self.errors.append(
                        ValidationError(
                            rule_number=81,
                            severity="error",
                            message=f"Power Analysis enabled: CPU_Cluster OS '{os_type}' not in supported list: {supported_os}",
                            xpath=xpath,
                        )
                    )

    # ============================================================================
    # Rule 84: When PowerAnalysis enabled, ALL CPU_Clusters OS must be Nucleus_RTOS
    # ============================================================================
    # (Duplicate/older implementation removed — keep the single, authoritative
    # _validate_rule_84 implementation that appears later in the file.)

    # ============================================================================
    # Rule 84: When PowerAnalysis enabled, ALL CPU_Clusters OS must be Nucleus_RTOS
    # ============================================================================
    def _validate_rule_84(self):
        """
        Rule 84: If Power Analysis is enabled anywhere in the Analysis block, every
        CPU_Cluster in the document must have Operating-System type 'Nucleus_RTOS'.

        This enforces a strict product policy for power analysis runs.
        """
        power_analysis = self.root.xpath(
            "//Analysis//PowerAnalysis[@enabled='true'] | //Analysis[@PowerAnalysisEnabled='true'] | //Analysis//Power-Analysis-Enable"
        )
        if not power_analysis:
            return

        for cluster in self.root.xpath("//CPU_Cluster"):
            os_elem = cluster.xpath("Operating-System/*")
            if not os_elem:
                xpath = self.tree.getpath(cluster)
                self.errors.append(
                    ValidationError(
                        rule_number=84,
                        severity="error",
                        message="Power Analysis enabled: CPU_Cluster has no Operating-System child (expected 'Nucleus_RTOS')",
                        xpath=xpath,
                    )
                )
                continue

            os_type = etree.QName(os_elem[0]).localname
            # Strict enforcement: only Nucleus_RTOS allowed
            if os_type != "Nucleus_RTOS":
                xpath = self.tree.getpath(cluster)
                self.errors.append(
                    ValidationError(
                        rule_number=84,
                        severity="error",
                        message=(
                            f"Power Analysis enabled: CPU_Cluster OS '{os_type}' not allowed for power runs; expected 'Nucleus_RTOS'"
                        ),
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 82: Power Analysis single-core enforcement
    # ============================================================================
    def _validate_rule_82(self):
        """
        ⚠️ Rule 82: When PowerAnalysis enabled, CPU_Cluster must be single-core.

        Why Python: XSD uses CoresPerCluster or nested cluster element enumerations.
        Python extracts and validates core count from XSD structure.
        """
        power_analysis = self.root.xpath(
            "//Analysis//PowerAnalysis[@enabled='true'] | //Analysis[@PowerAnalysisEnabled='true'] | //Analysis//Power-Analysis-Enable"
        )
        if not power_analysis:
            return

        for cluster in self.root.xpath("//CPU_Cluster"):
            # Extract CoresPerCluster from nested elements
            cores_per_cluster = None
            for elem in cluster.xpath(".//*[@CoresPerCluster]"):
                cores_per_cluster = int(elem.get("CoresPerCluster"))
                break

            if cores_per_cluster is not None and cores_per_cluster != 1:
                xpath = self.tree.getpath(cluster)
                self.errors.append(
                    ValidationError(
                        rule_number=82,
                        severity="error",
                        message=f"Power Analysis enabled: CPU_Cluster must be single-core (found CoresPerCluster={cores_per_cluster})",
                        xpath=xpath,
                    )
                )

    # ============================================================================
    # Rule 85: When PowerAnalysis enabled, ALL CPU_Clusters must be single-core
    # ============================================================================
    def _validate_rule_85(self):
        """
        Rule 85: If Power Analysis is enabled, every CPU_Cluster in the document
        must be single-core (CoresPerCluster == 1).

        Why Python: Determining 'single-core' requires reading the CoresPerCluster
        attribute which is modeled in nested elements in the XSD and is awkward
        to express reliably in Schematron. Python normalizes and inspects the
        structure and reports a clear rule number (85).
        """
        power_analysis = self.root.xpath(
            "//Analysis//PowerAnalysis[@enabled='true'] | //Analysis[@PowerAnalysisEnabled='true'] | //Analysis//Power-Analysis-Enable"
        )
        if not power_analysis:
            return

        for cluster in self.root.xpath("//CPU_Cluster"):
            cores_per_cluster = None
            for elem in cluster.xpath(".//*[@CoresPerCluster]"):
                try:
                    cores_per_cluster = int(elem.get("CoresPerCluster"))
                except Exception:
                    cores_per_cluster = None
                break

            # If CoresPerCluster is present and not 1 -> error
            if cores_per_cluster is not None and cores_per_cluster != 1:
                xpath = self.tree.getpath(cluster)
                self.errors.append(
                    ValidationError(
                        rule_number=85,
                        severity="error",
                        message=f"Power Analysis enabled: all CPU_Clusters must be single-core (found CoresPerCluster={cores_per_cluster})",
                        xpath=xpath,
                    )
                )


def validate_file(
    xml_file: str, check_filesystem: bool = False
) -> List[ValidationError]:
    """
    Validate a single XML file using Python logical validators.

    Args:
        xml_file: Path to XML file
        check_filesystem: Enable filesystem checks (Rules 38, 39, 71)

    Returns:
        List of ValidationError objects
    """
    validator = PythonLogicalValidator(xml_file, check_filesystem)
    errors = validator.validate_all()
    if errors is None:
        errors = []
    return errors


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python python_logical_validations.py <xml_file> [--check-filesystem]"
        )
        sys.exit(1)

    xml_file = sys.argv[1]
    check_fs = "--check-filesystem" in sys.argv

    print(f"Validating {xml_file} (filesystem checks: {check_fs})")
    print("=" * 80)

    errors = validate_file(xml_file, check_fs)

    if not errors:
        print("✅ All Python validation rules passed!")
    else:
        print(f"❌ Found {len(errors)} validation error(s):\n")
        for error in errors:
            print(error)

    sys.exit(0 if not errors else 1)
