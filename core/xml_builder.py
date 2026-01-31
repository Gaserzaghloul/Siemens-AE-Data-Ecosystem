import os
import re
import time
import random
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import defaultdict
from core.settings import *

try:
    from faker import Faker
    fake = Faker()
except ImportError:
    fake = None

PROMPT_META_PATTERN = re.compile(r"\[\[PROMPT_META (.+?)\]\]\s*$")

def extract_prompt_metadata(prompt_text):
    """Split the human-readable prompt from its machine metadata."""
    if not isinstance(prompt_text, str):
        return prompt_text, {}

    match = PROMPT_META_PATTERN.search(prompt_text)
    metadata = {}
    if match:
        payload = match.group(1).strip()
        try:
            metadata = json.loads(payload)
        except json.JSONDecodeError:
            metadata = {}
        prompt_text = prompt_text[: match.start()].rstrip()
    return prompt_text, metadata

def apply_quick_schema_fixes(xml_content, category_id=None):
    """Apply minimal, safe transformations to the generated XML to reduce
    trivial schema validation failures.
    """
    if not isinstance(xml_content, str):
        return xml_content

    # Remove NULL bytes and ensure consistent newlines
    fixed = xml_content.replace("\x00", "").replace("\r\n", "\n")

    # Ensure it has an <AR-PACKAGE> root (very conservative check)
    if "<AR-PACKAGE" not in fixed:
        if category_id == 3:
            if "Simulation-Time" in fixed:
                fixed = f"""<AR-PACKAGE>
  <ELEMENTS>
    {fixed}
    <ECUs>
      <SHORT-NAME name="MinimalECU" />
      <SoCs>
        <SHORT-NAME name="MinimalSoC" />
        <AXI-BUS width="32" frequency="100000000" />
        <ETHERNET-INTERFACE Mode="simulated" />
        <UCIe-INTERFACE Mode="host" />
        <CPU_Cluster>
          <Operating-System><Linux Affine-tasks-byOS="false" Show_UART_Terminal="false"><Ubuntu_File_System>default</Ubuntu_File_System></Linux></Operating-System>
          <ARMV8-Family><CortexA72 CoresPerCluster="1"><SHORT-NAME name="Core" /><Frequency value="1000000000" /></CortexA72></ARMV8-Family>
        </CPU_Cluster>
      </SoCs>
    </ECUs>
  </ELEMENTS>
</AR-PACKAGE>"""
            else:
                fixed = f"""<AR-PACKAGE>
  <ELEMENTS>
    <ECUs>
      <SHORT-NAME name="MinimalECU" />
      <SoCs>
        <SHORT-NAME name="MinimalSoC" />
        <AXI-BUS width="32" frequency="100000000" />
        <ETHERNET-INTERFACE Mode="simulated" />
        <UCIe-INTERFACE Mode="host" />
        <CPU_Cluster>
          <Operating-System><Linux Affine-tasks-byOS="false" Show_UART_Terminal="false"><Ubuntu_File_System>default</Ubuntu_File_System></Linux></Operating-System>
          <ARMV8-Family><CortexA72 CoresPerCluster="1"><SHORT-NAME name="Core" /><Frequency value="1000000000" /></CortexA72></ARMV8-Family>
        </CPU_Cluster>
      </SoCs>
    </ECUs>
  </ELEMENTS>
</AR-PACKAGE>"""
        else:
            fixed = f"<AR-PACKAGE>\n<ELEMENTS>\n{fixed}\n</ELEMENTS>\n</AR-PACKAGE>"

    # Convert SHORT-NAME element text to required attribute form (schema requires AeIdentity with name attribute)
    fixed = re.sub(
        r"<SHORT-NAME>\s*([^<]+?)\s*</SHORT-NAME>",
        r"<SHORT-NAME name=\"\1\" />",
        fixed,
    )

    return fixed

def _normalize_label(tag):
    if not tag:
        return "Item"
    label = LABEL_OVERRIDES.get(tag, tag)
    label = label.replace("-", "_").replace(":", "_").replace(" ", "_")
    label_parts = [part for part in label.split("_") if part]
    if not label_parts:
        return "Item"
    return "".join(part.capitalize() for part in label_parts)

def _assign_frequency(element, parent_tag, context_element=None):
    # Find the CPU_Cluster ancestor to check OS
    cpu_cluster = None
    # Start from the frequency element and walk up to find CPU_Cluster
    current = element
    max_depth = 10  # Safety limit
    depth = 0
    while current is not None and depth < max_depth:
        tag_name = current.tag if hasattr(current, 'tag') else str(current)
        if 'CPU_Cluster' in tag_name or tag_name.endswith('CPU_Cluster') or tag_name.endswith('CPU-Cluster') or 'CPUCluster' in tag_name:
            cpu_cluster = current
            break
        if hasattr(current, 'getparent'):
            current = current.getparent()
        else:
            break
        depth += 1
    
    if cpu_cluster is not None:
        is_linux = False
        for os_node in cpu_cluster.findall(".//Operating-System") + cpu_cluster.findall(".//OS"):
            if os_node.find(".//Linux") is not None:
                is_linux = True
                break
            if os_node.text and "linux" in os_node.text.lower():
                is_linux = True
                break
        if not is_linux:
            for linux_elem in cpu_cluster.findall(".//Linux"):
                is_linux = True
                break
        
        if is_linux:
            element.set("value", "1000000000")
        else:
            element.set("value", str(random.randint(800, 1000) * 1_000_000))
    else:
        element.set("value", str(random.randint(350, 900) * 1_000_000))

def _assign_power(element, total_mw=None):
    if total_mw:
        # Scale parts based on total
        element.set("Split_power_mw", f"{total_mw * 0.4:.1f}")
        element.set("Delay_power_mw", f"{total_mw * 0.2:.1f}")
        element.set("Sequential_power_mw", f"{total_mw * 0.3:.1f}")
        element.set("Static_Power_Leakage_mw", f"{total_mw * 0.05:.2f}")
        element.set("Clock_Tree_Power_mw", f"{total_mw * 0.05:.1f}")
    else:
        element.set("Split_power_mw", f"{random.uniform(20.0, 80.0):.1f}")
        element.set("Delay_power_mw", f"{random.uniform(10.0, 40.0):.1f}")
        element.set("Sequential_power_mw", f"{random.uniform(15.0, 60.0):.1f}")
        element.set("Static_Power_Leakage_mw", f"{random.uniform(0.05, 0.4):.2f}")
        element.set("Clock_Tree_Power_mw", f"{random.uniform(1.0, 6.0):.1f}")
    element.set("Power_Per_Nominal_Clock_Mhz", str(random.randint(60, 110)))

def _prettify_xml(xml_string):
    """Use minidom to prettify XML with proper indentation."""
    try:
        # Remove existing indentation and newlines to avoid doubling
        reparsed = minidom.parseString(re.sub(r'>\s+<', '><', xml_string))
        return reparsed.toprettyxml(indent="  ")
    except Exception:
        return xml_string

def apply_prompt_alignment(xml_text, prefix=None, metadata=None):
    """Rename generated identifiers to respect prompt prefixes and align key constraints."""
    if not prefix or not isinstance(xml_text, str):
        return xml_text

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return xml_text

    prefix = re.sub(r"[^0-9A-Za-z_]", "_", prefix.replace(" ", "_"))
    if not re.match(r"[A-Za-z_]", prefix):
        prefix = f"P_{prefix}"
    metadata = metadata or {}
    name_counters = defaultdict(int)
    name_map = {}

    def traverse(element, parent_tag=None):
        for child in list(element):
            if child.tag == "SHORT-NAME":
                old = child.attrib.get("name")
                if not old:
                    continue
                new_name = f"{prefix}_{old}"
                name_map[old] = new_name
                child.set("name", new_name)
                continue

            # Align numeric values with prompt metadata
            if child.tag == "LATENCY":
                child.set("unit", "us")
                val = metadata.get("latency_us", random.randint(5, 45))
                child.set("value", str(val))
            elif child.tag == "PERIOD":
                child.set("unit", "ms")
                val = metadata.get("period_ms", random.randint(10, 100))
                child.set("value", str(val))
            elif child.tag == "POWER-PARAMETERS":
                _assign_power(child, total_mw=metadata.get("power_mw"))
            elif child.tag == "Ubuntu_File_System":
                if "ram_mb" in metadata:
                    child.text = f"ubuntu_fs_{metadata['ram_mb']}MB"
            elif "CoresPerCluster" in child.attrib:
                if "cpu_cores" in metadata:
                    child.set("CoresPerCluster", str(metadata["cpu_cores"]))
            
            if child.tag == "Frequency":
                current_value = child.get("value", "").strip()
                if current_value == "1000000000":
                    traverse(child, child.tag)
                    continue
                
                cpu_cluster = None
                current_elem = element
                depth = 0
                while current_elem is not None and depth < 15:
                    tag_name = current_elem.tag if hasattr(current_elem, 'tag') else str(current_elem)
                    if 'CPU_Cluster' in tag_name or tag_name.endswith('CPU_Cluster') or tag_name.endswith('CPU-Cluster'):
                        cpu_cluster = current_elem
                        break
                    if hasattr(current_elem, 'getparent'):
                        current_elem = current_elem.getparent()
                    else:
                        break
                    depth += 1
                
                is_linux = False
                if cpu_cluster is not None:
                    for os_node in cpu_cluster.findall(".//Operating-System") + cpu_cluster.findall(".//OS"):
                        if os_node.find(".//Linux") is not None:
                            is_linux = True
                            break
                        if os_node.text and "linux" in os_node.text.lower():
                            is_linux = True
                            break
                    if not is_linux:
                        for linux_elem in cpu_cluster.findall(".//Linux"):
                            is_linux = True
                            break
                
                if is_linux:
                    child.set("value", "1000000000")
                else:
                    _assign_frequency(child, parent_tag, element)
            elif child.tag == "Simulation-Time":
                child.set("unit", "ms")
                child.set("value", str(random.randint(3000, 10000)))

            traverse(child, child.tag)

    traverse(root, root.tag)

    # Update references after renaming
    sorted_replacements = sorted(name_map.items(), key=lambda kv: -len(kv[0]))
    for elem in root.iter():
        for attr, value in list(elem.attrib.items()):
            if not isinstance(value, str):
                continue
            updated = value
            for old, new in sorted_replacements:
                if f"/{old}" in updated:
                    updated = updated.replace(f"/{old}", f"/{new}")
                elif updated == old:
                    updated = new
            elem.attrib[attr] = updated

    # Ensure HWIP operations reference the renamed ports so logical rules pass.
    for gh in root.findall(".//Generic_Hardware"):
        gh_short = gh.find("SHORT-NAME")
        if gh_short is None:
            continue
        gh_name = gh_short.attrib.get("name")
        internal = gh.find("INTERNAL-BEHAVIOR")
        if internal is None:
            continue
        ports_section = internal.find("PORTS")
        provided_name = None
        required_name = None
        if ports_section is not None:
            provided_ports = ports_section.findall("P-PORT-PROTOTYPE")
            required_ports = ports_section.findall("R-PORT-PROTOTYPE")
            if provided_ports:
                short = provided_ports[0].find("SHORT-NAME")
                if short is not None and "name" in short.attrib:
                    provided_name = short.attrib["name"]
            if required_ports:
                short = required_ports[0].find("SHORT-NAME")
                if short is not None and "name" in short.attrib:
                    required_name = short.attrib["name"]

        ops_seq = internal.find("OPERATIONS-SEQUENCE")
        if ops_seq is None:
            continue
        for op in ops_seq.findall("OPERATION"):
            read = op.find("READ")
            if read is not None and required_name:
                iref = read.find("IREF")
                if iref is not None:
                    iref.set("DEST", f"/{gh_name}/{required_name}")
            write = op.find("WRITE")
            if write is not None and provided_name:
                iref = write.find("IREF")
                if iref is not None:
                    iref.set("DEST", f"/{gh_name}/{provided_name}")

    # Return pretty XML
    rough_string = ET.tostring(root, encoding='utf-8')
    # Decode and strip inter-tag whitespace to prevent double-spacing
    rough_string_decoded = rough_string.decode('utf-8')
    compact_xml = re.sub(r'>\s+<', '><', rough_string_decoded)
    reparsed = minidom.parseString(compact_xml)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    # remove the xml header if present
    if pretty_xml.startswith('<?xml'):
        lines = pretty_xml.splitlines()[1:]
        pretty_xml = '\n'.join(lines)
    return pretty_xml

def _reserve_hw_name(name_set, base_name):
    """Ensure a hardware element name is unique within the SOC/Chiplet scope."""
    name = base_name
    counter = 1
    while name in name_set:
        name = f"{base_name}_{counter}"
        counter += 1
    name_set.add(name)
    return name

def make_random_hw_name(category="GH"):
    if fake:
        return f"{category}_{fake.word().capitalize()}"
    return f"{category}_{random.randint(100, 999)}"

def build_auxiliary_hw_block(prefix, index, indent="        ", existing_names=None):
    """Create an auxiliary Generic_Hardware block to increase detail without
    touching interface bindings."""
    base_name = f"{prefix}_Diag_{index}"
    gh_name = (
        _reserve_hw_name(existing_names, base_name)
        if existing_names is not None
        else base_name
    )
    freq = random.randint(120_000_000, 900_000_000)
    priority = random.randint(8, 96)
    mem_flag = random.choice(["true", "false"])
    operations = []
    for _ in range(random.randint(3, 5)):
        latency_value = random.randint(8, 120)
        latency_unit = random.choice(["us", "ms", "ns"])
        operations.append(
            f"""{indent}    <OPERATION>
{indent}      <LATENCY value="{latency_value}" unit="{latency_unit}" />
{indent}    </OPERATION>"""
        )
    operations_block = "\n".join(operations)
    # Timing Event Period must be at least 10ms
    period_value = random.randint(10, 250)
    period_unit = "ms"  # Use ms to ensure >= 10ms requirement
    split_pw = round(random.uniform(5.0, 25.0), 2)
    delay_pw = round(random.uniform(2.0, 15.0), 2)
    seq_pw = round(random.uniform(4.0, 20.0), 2)
    leak_pw = round(random.uniform(0.01, 0.3), 3)
    clock_pw = round(random.uniform(0.2, 2.5), 2)
    nominal_clock = random.randint(50, 200)
    return f"""
{indent}<Generic_Hardware>
{indent}  <SHORT-NAME name="{gh_name}" />
{indent}  <Frequency value="{freq}" />
{indent}  <AXI-Master-Port priority="{priority}" />
{indent}  <MEMORY-INTERFACE InternalMemory="{mem_flag}" />
{indent}  <INTERNAL-BEHAVIOR>
{indent}    <PORTS />
{indent}    <OPERATIONS-SEQUENCE>
{operations_block}
{indent}    </OPERATIONS-SEQUENCE>
{indent}    <EVENT>
{indent}      <TIMING-EVENT>
{indent}        <PERIOD value="{period_value}" unit="{period_unit}" />
{indent}      </TIMING-EVENT>
{indent}    </EVENT>
{indent}  </INTERNAL-BEHAVIOR>
{indent}  <POWER-PARAMETERS Split_power_mw="{split_pw}" Delay_power_mw="{delay_pw}" Sequential_power_mw="{seq_pw}" Static_Power_Leakage_mw="{leak_pw}" Clock_Tree_Power_mw="{clock_pw}" Power_Per_Nominal_Clock_Mhz="{nominal_clock}" />
{indent}</Generic_Hardware>"""

def build_analysis_section(ecu_name, soc_name):
    """Return a standard analysis block referencing a specific SoC."""
    soc_ref = f"/{ecu_name}/{soc_name}"
    # Note: Power-Analysis-Enable is excluded because it's not supported yet and causes warnings
    return f"""
    <Analysis>
      <SW-Analysis-Enable>
        <ALL-SoCs>enabled</ALL-SoCs>
      </SW-Analysis-Enable>
      <HW-Analysis-Enable>
        <Selected-SoCs>
          <SoC DEST="{soc_ref}" />
        </Selected-SoCs>
      </HW-Analysis-Enable>
      <Network-Analysis-Enable>
        <CAN-BUS-Monitor-Enable>enabled</CAN-BUS-Monitor-Enable>
        <ETH-Switch-Monitor-Enable>enabled</ETH-Switch-Monitor-Enable>
      </Network-Analysis-Enable>
    </Analysis>"""

def build_cpu_cluster_block(
    cluster_name,
    frequency,
    cores_per_cluster,
    indent="        ",
    os_mode="linux",
    file_system=None,
    affine_tasks=False,
    show_uart=False,
    family="ARMV8-Family",
    variant="CortexA72",
):
    """Return a CPU_Cluster block with consistent OS and architecture structure."""

    def _bool_to_str(flag):
        return "true" if str(flag).lower() in {"1", "true", "yes", "on"} else "false"

    os_mode_normalized = os_mode.lower()
    if os_mode_normalized not in {"linux", "nucleus", "freertos"}:
        os_mode_normalized = "linux"

    if os_mode_normalized == "nucleus":
        os_block = (
            f'{indent}  <Nucleus_RTOS Affine-tasks-byOS="{_bool_to_str(affine_tasks)}" '
            f'Show_UART_Terminal="{_bool_to_str(show_uart)}" />'
        )
    else:
        fs_value = file_system or "ubuntu_rootfs"
        os_block = (
            f'{indent}  <Linux Affine-tasks-byOS="{_bool_to_str(affine_tasks)}" '
            f'Show_UART_Terminal="{_bool_to_str(show_uart)}">\n'
            f"{indent}    <Ubuntu_File_System>{fs_value}</Ubuntu_File_System>\n"
            f"{indent}  </Linux>"
        )

    cores_value = str(cores_per_cluster)
    if os_mode_normalized == "nucleus":
        cores_value = "1"

    cpu_block = (
        f'{indent}<CPU_Cluster>\n'
        f"{indent}  <Operating-System>\n"
        f"{os_block}\n"
        f"{indent}  </Operating-System>\n"
        f"{indent}  <{family}>\n"
        f'{indent}    <{variant} CoresPerCluster="{cores_value}">\n'
        f'{indent}      <SHORT-NAME name="{cluster_name}" />\n'
        f'{indent}      <Frequency value="{frequency}" />\n'
        f"{indent}    </{variant}>\n"
        f"{indent}  </{family}>\n"
        f"{indent}</CPU_Cluster>"
    )
    return cpu_block

def append_sections_before_elements_end(xml_content, sections):
    """Helper to insert extra sections (like Analysis) before the final </ELEMENTS> tag."""
    if not sections:
        return xml_content
    
    sections_str = "\n".join(sections)
    if "</ELEMENTS>" in xml_content:
        return xml_content.replace("</ELEMENTS>", f"{sections_str}\n  </ELEMENTS>")
    return xml_content + "\n" + sections_str

def generate_complete_xml(key, cat_id, rules, prompt_meta=None):
    # Random variations for diversity
    sim_time_value = random.randint(3000, 10000)
    sim_time_unit = random.choice(["ms", "us"])

    size_hint = None
    if isinstance(rules, dict):
        size_hint = rules.get("_size_hint")
    if prompt_meta and prompt_meta.get("size"):
        size_hint = prompt_meta["size"]

    prefix = None
    if isinstance(prompt_meta, dict):
        prefix = prompt_meta.get("prefix")

    analysis_sections = []

    def select_count(small_range, medium_range, large_range):
        """Pick a count based on the size hint to avoid fixed-length XML."""
        if size_hint == "small":
            chosen = small_range
        elif size_hint == "medium":
            chosen = medium_range
        else:
            chosen = large_range
        low, high = chosen
        if low > high:
            low, high = high, low
        return random.randint(low, high)

    if cat_id == 3:  # TIME AND LATENCY (Atomic)
        # Generate simple atomic elements
        elem_type = random.choice(["Simulation-Time", "PERIOD", "LATENCY", "Frequency"])
        if elem_type == "Simulation-Time":
            return f'<Simulation-Time value="{sim_time_value}" unit="{sim_time_unit}" />'
        elif elem_type == "PERIOD":
             return f'<PERIOD value="{random.randint(10, 1000)}" unit="{random.choice(["ms", "us"])}" />'
        elif elem_type == "LATENCY":
             return f'<LATENCY value="{random.randint(1, 100)}" unit="{random.choice(["ns", "us"])}" />'
        elif elem_type == "Frequency":
             return f'<Frequency value="{random.randint(1000000, 1000000000)}" />'
        return ""

    elif cat_id == 6:  # COMPLETE SYSTEM
        complete_xml = f'''<AR-PACKAGE>
  <ELEMENTS>
    <Simulation-Time value="{sim_time_value}" unit="{sim_time_unit}" />'''

        sris = []
        num_sris = select_count((3, 4), (4, 5), (5, 6))
        for i in range(num_sris):
            sri_name = fake.word().capitalize() if fake else f"Interface_{i + 1}"
            sris.append(sri_name)
            complete_xml += f'''
    <SENDER-RECEIVER-INTERFACE>
      <SHORT-NAME name="{sri_name}" />
      <DATA-ELEMENTS>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME name="Data_{i}_0" />
          <TYPE-TREF>
            <Array-of-uint8 No_Of_Bytes="{random.randint(256, 1024)}">
              <Random-Values-generated>
                <Data-Range min="0" max="255" />
              </Random-Values-generated>
            </Array-of-uint8>
          </TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME name="Data_{i}_1" />
          <TYPE-TREF>
            <Array-of-uint8 No_Of_Bytes="{random.randint(256, 1024)}">
              <Random-Values-generated>
                <Data-Range min="0" max="255" />
              </Random-Values-generated>
            </Array-of-uint8>
          </TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
      </DATA-ELEMENTS>
    </SENDER-RECEIVER-INTERFACE>'''

        sri_name_to_idx = {sri: i for i, sri in enumerate(sris)}
        complete_xml += f"""
    <APPLICATION-SW-COMPONENT-TYPE>
      <SHORT-NAME name="SWC_Generated" />
      <PORTS>"""
        port_definitions = []
        for idx, sri_name in enumerate(sris):
            provider_name = f"Provider_{idx}"
            required_name = f"Required_{idx}"
            port_definitions.append((provider_name, required_name, sri_name))
            complete_xml += f"""
        <P-PORT-PROTOTYPE>
          <SHORT-NAME name="{provider_name}" />
          <PROVIDED-INTERFACE-TREF DEST="/{sri_name}" />
        </P-PORT-PROTOTYPE>
        <R-PORT-PROTOTYPE>
          <SHORT-NAME name="{required_name}" />
          <REQUIRED-INTERFACE-TREF DEST="/{sri_name}" />
        </R-PORT-PROTOTYPE>"""
        complete_xml += """
      </PORTS>
      <INTERNAL-BEHAVIORS>
        <SWC-INTERNAL-BEHAVIOR>
          <SHORT-NAME name="Behavior_0" />
          <RUNNABLES>"""
        read_runnables = []
        write_runnables = []
        runnable_ports = port_definitions[:]
        for idx, (provider_name, required_name, sri_name) in enumerate(runnable_ports):
            read_name = f"Read_Run_{idx}"
            write_name = f"Write_Run_{idx}"
            read_runnables.append(read_name)
            write_runnables.append(write_name)
            complete_xml += f"""
            <RUNNABLE-ENTITY>
              <SHORT-NAME name="{read_name}" />
              <DATA-READ-ACCESS>
                <VARIABLE-ACCESS>
                  <SHORT-NAME name="ReadVar_{idx}" />
                  <ACCESSED-VARIABLE>
                    <AUTOSAR-VARIABLE-IREF>
                      <PORT-PROTOTYPE-REF DEST="/SWC_Generated/{required_name}" />
                      <TARGET-DATA-PROTOTYPE-REF DEST="/{sri_name}/Data_{sri_name_to_idx[sri_name]}_0" />
                    </AUTOSAR-VARIABLE-IREF>
                  </ACCESSED-VARIABLE>
                </VARIABLE-ACCESS>
              </DATA-READ-ACCESS>
            </RUNNABLE-ENTITY>
            <RUNNABLE-ENTITY>
              <SHORT-NAME name="{write_name}" />
              <DATA-WRITE-ACCESS>
                <VARIABLE-ACCESS>
                  <SHORT-NAME name="WriteVar_{idx}" />
                  <ACCESSED-VARIABLE>
                    <AUTOSAR-VARIABLE-IREF>
                      <PORT-PROTOTYPE-REF DEST="/SWC_Generated/{provider_name}" />
                      <TARGET-DATA-PROTOTYPE-REF DEST="/{sri_name}/Data_{sri_name_to_idx[sri_name]}_1" />
                    </AUTOSAR-VARIABLE-IREF>
                  </ACCESSED-VARIABLE>
                </VARIABLE-ACCESS>
              </DATA-WRITE-ACCESS>
            </RUNNABLE-ENTITY>"""
        complete_xml += f"""
          </RUNNABLES>
          <EVENTS>"""
        for r in read_runnables + write_runnables:
            period_value = random.randint(10, 500)
            period_unit = "ms"
            complete_xml += f'''
            <TIMING-EVENT>
              <SHORT-NAME name="Timer_{r}" />
              <START-ON-EVENT-REF DEST="/SWC_Generated/Behavior_0/{r}" />
              <PERIOD value="{period_value}" unit="{period_unit}" />
            </TIMING-EVENT>'''
        complete_xml += f"""
          </EVENTS>
        </SWC-INTERNAL-BEHAVIOR>
      </INTERNAL-BEHAVIORS>
    </APPLICATION-SW-COMPONENT-TYPE>"""

        mapping_ecu_name = None
        mapping_soc_name = None
        mapping_cluster_name = None

        ecu_name = fake.word().capitalize() if fake else f"ECU_{random.randint(1, 100)}"
        soc_name = fake.word().capitalize() if fake else f"SoC_{random.randint(1, 100)}"
        cores_per_cluster = random.choice(["1", "2", "4", "8"])
        core_ids = list(range(max(1, int(cores_per_cluster))))
        cluster_name = (
            fake.word().capitalize() if fake else f"Cluster_{random.randint(1, 100)}"
        )
        cluster_freq = 1000000000

        mapping_ecu_name = ecu_name
        mapping_soc_name = soc_name
        mapping_cluster_name = cluster_name

        diag_blocks = select_count((2, 3), (3, 4), (4, 5))
        diag_block = "".join(
            build_auxiliary_hw_block(ecu_name, idx, indent="        ")
            for idx in range(diag_blocks)
        )

        complete_xml += f'''
    <ECUs>
      <SHORT-NAME name="{ecu_name}" />
      <SoCs>
        <SHORT-NAME name="{soc_name}" />
        <AXI-BUS width="{random.randint(16, 64)}" frequency="{
            random.randint(500_000_000, 1_000_000_000)
        }" />
        <ETHERNET-INTERFACE Mode="simulated" />
        <UCIe-INTERFACE Mode="{random.choice(["host", "endpoint"])}" />
{
            build_cpu_cluster_block(
                cluster_name,
                cluster_freq,
                cores_per_cluster,
                indent="        ",
                os_mode="linux",
                file_system=(fake.word() if fake else "ubuntu_fs"),
                affine_tasks=True,
                show_uart=True,
                family="ARMV8-Family",
                variant="CortexA72",
            )
        }
{diag_block}
      </SoCs>
    </ECUs>'''

        if mapping_ecu_name and mapping_soc_name and mapping_cluster_name:
            complete_xml += f"""
    <HW-SW-MAPPING ClusterRef="/{mapping_ecu_name}/{mapping_soc_name}/{mapping_cluster_name}">"""
            base_load = 50000
            mapping_targets = read_runnables + write_runnables
            random.shuffle(mapping_targets)
            for idx, r in enumerate(mapping_targets):
                core_id = core_ids[idx % len(core_ids)]
                load = base_load + random.randint(1500, 3500) * (1 + core_id)
                prio = random.randint(8, 40)
                complete_xml += f'''
       <Core-Runnable-Mapping CoreId="{core_id}" RunnableRef="/SWC_Generated/Behavior_0/{r}" Load="{load}" Priority="{prio}" />'''
            complete_xml += f"""
     </HW-SW-MAPPING>"""

        complete_xml += f"""
  </ELEMENTS>
</AR-PACKAGE>"""

    elif cat_id == 16:  # SWC CUSTOM BEHAVIOR
        complete_xml = f'''<AR-PACKAGE>
  <ELEMENTS>
    <Simulation-Time value="{sim_time_value}" unit="{sim_time_unit}" />'''
        sris = []
        num_sris = select_count((4, 5), (5, 6), (6, 8))
        for i in range(num_sris):
            sri_name = fake.word().capitalize() if fake else f"Interface_{i + 1}"
            sris.append(sri_name)
            complete_xml += f'''
    <SENDER-RECEIVER-INTERFACE>
      <SHORT-NAME name="{sri_name}" />
      <DATA-ELEMENTS>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME name="Data_0" />
          <TYPE-TREF>
            <Array-of-uint8 No_Of_Bytes="{random.randint(256, 1024)}">
              <Random-Values-generated>
                <Data-Range min="0" max="255" />
              </Random-Values-generated>
            </Array-of-uint8>
          </TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME name="Data_1" />
          <TYPE-TREF>
            <Array-of-uint8 No_Of_Bytes="{random.randint(256, 1024)}">
              <Random-Values-generated>
                <Data-Range min="0" max="255" />
              </Random-Values-generated>
            </Array-of-uint8>
          </TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
      </DATA-ELEMENTS>
    </SENDER-RECEIVER-INTERFACE>'''

        ecu_name = fake.word().capitalize() if fake else f"ECU_{random.randint(1, 100)}"
        soc_name = fake.word().capitalize() if fake else f"SoC_{random.randint(1, 100)}"
        bus_width = random.randint(16, 64)
        bus_freq = random.randint(200_000_000, 1_000_000_000)
        eth_mode = random.choice(["simulated"])
        ucie_mode = random.choice(["host", "endpoint"])
        chiplet_name = (
            fake.word().capitalize() if fake else f"Chiplet_{random.randint(1, 100)}"
        )

        complete_xml += f'''
    <ECUs>
      <SHORT-NAME name="{ecu_name}" />
      <SoCs>
        <SHORT-NAME name="{soc_name}" />
        <AXI-BUS width="{bus_width}" frequency="{bus_freq}" />
        <ETHERNET-INTERFACE Mode="{eth_mode}" />
        <UCIe-INTERFACE Mode="{ucie_mode}" />
        <Chiplet>
          <SHORT-NAME name="{chiplet_name}" />
          <AXI-BUS width="{bus_width}" frequency="{bus_freq}" />
          <ETHERNET-INTERFACE Mode="{eth_mode}" />
          <UCIe-INTERFACE Mode="{ucie_mode}" />'''

        chiplet_hw_names = set()
        for i, sri in enumerate(sris):
            gh_prod = _reserve_hw_name(
                chiplet_hw_names,
                fake.word().capitalize() if fake else f"GH_Prod_{i + 1}",
            )
            gh_cons = _reserve_hw_name(
                chiplet_hw_names,
                fake.word().capitalize() if fake else f"GH_Cons_{i + 1}",
            )
            period_value_prod = random.randint(10, 100)
            period_unit_prod = "ms"
            period_value_cons = random.randint(10, 100)
            period_unit_cons = "ms"
            prod_freq = random.randint(120_000_000, 300_000_000)
            cons_freq = random.randint(100_000_000, 250_000_000)
            prod_prio = random.randint(8, 64)
            cons_prio = random.randint(8, 64)
            prod_mem = random.choice(["true", "false"])
            cons_mem = random.choice(["true", "false"])
            latency_value = random.randint(8, 25)
            latency_unit = random.choice(["us", "ms"])

            complete_xml += f'''
          <Generic_Hardware>
            <SHORT-NAME name="{gh_prod}" />
            <Frequency value="{prod_freq}" />
            <AXI-Master-Port priority="{prod_prio}" />
            <MEMORY-INTERFACE InternalMemory="{prod_mem}" />
            <INTERNAL-BEHAVIOR>
              <PORTS>
                <P-PORT-PROTOTYPE>
                  <SHORT-NAME name="Out_{i}" />
                  <PROVIDED-INTERFACE-TREF DEST="/{sri}" />
                </P-PORT-PROTOTYPE>
              </PORTS>
              <OPERATIONS-SEQUENCE>
                <OPERATION>
                  <WRITE>
                    <IREF DEST="/{gh_prod}/Out_{i}" />
                  </WRITE>
                </OPERATION>
              </OPERATIONS-SEQUENCE>
              <EVENT>
                <TIMING-EVENT>
                  <PERIOD value="{period_value_prod}" unit="{period_unit_prod}" />
                </TIMING-EVENT>
              </EVENT>
            </INTERNAL-BEHAVIOR>
          </Generic_Hardware>

          <Generic_Hardware>
            <SHORT-NAME name="{gh_cons}" />
            <Frequency value="{cons_freq}" />
            <AXI-Master-Port priority="{cons_prio}" />
            <MEMORY-INTERFACE InternalMemory="{cons_mem}" />
            <INTERNAL-BEHAVIOR>
              <PORTS>
                <R-PORT-PROTOTYPE>
                  <SHORT-NAME name="In_{i}" />
                  <REQUIRED-INTERFACE-TREF DEST="/{sri}" />
                </R-PORT-PROTOTYPE>
              </PORTS>
              <OPERATIONS-SEQUENCE>
                <OPERATION>
                  <READ>
                    <IREF DEST="/{gh_cons}/In_{i}" />
                  </READ>
                </OPERATION>
                <OPERATION>
                  <LATENCY value="{latency_value}" unit="{latency_unit}" />
                </OPERATION>
              </OPERATIONS-SEQUENCE>
                <EVENT>
                  <TIMING-EVENT>
                    <PERIOD value="{period_value_cons}" unit="{period_unit_cons}" />
                  </TIMING-EVENT>
                </EVENT>
              </INTERNAL-BEHAVIOR>
            </Generic_Hardware>'''

        diag_blocks = select_count((2, 3), (3, 4), (4, 5))
        for diag_idx in range(diag_blocks):
            complete_xml += build_auxiliary_hw_block(
                chiplet_name,
                diag_idx,
                indent="          ",
                existing_names=chiplet_hw_names,
            )

        cores_per_cluster = random.choice(["2", "4"])
        cluster_name = (
            fake.word().capitalize() if fake else f"Cluster_{random.randint(1, 100)}"
        )
        cluster_freq = 1000000000

        complete_xml += f"""
        </Chiplet>
{
            build_cpu_cluster_block(
                cluster_name,
                cluster_freq,
                cores_per_cluster,
                indent="        ",
                os_mode="linux",
                file_system=(fake.word() if fake else "ubuntu_fs"),
                affine_tasks=False,
                show_uart=True,
                family="ARMV8-Family",
                variant="CortexA72",
            )
        }
      </SoCs>
    </ECUs>

  </ELEMENTS>
</AR-PACKAGE>"""
    else:
        complete_xml = f'''<AR-PACKAGE>
  <ELEMENTS>
    <Simulation-Time value="{sim_time_value}" unit="{sim_time_unit}" />'''

        interface_names = []
        used_interface_names = set()
        sri_count = max(select_count((6, 7), (7, 8), (8, 10)), 2)
        for i in range(sri_count):
            base_name = (
                fake.word().capitalize()
                if fake
                else f"Interface_{random.randint(1, 100)}"
            )
            if base_name in used_interface_names:
                base_name = f"{base_name}_{i}"
            used_interface_names.add(base_name)
            interface_names.append(base_name)
            complete_xml += f'''
    <SENDER-RECEIVER-INTERFACE>
      <SHORT-NAME name="{base_name}" />
      <DATA-ELEMENTS>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME name="Data_{i}" />
          <TYPE-TREF>
            <Array-of-uint8 No_Of_Bytes="{random.randint(128, 1024)}">
              <Random-Values-generated>
                <Data-Range min="0" max="255" />
              </Random-Values-generated>
            </Array-of-uint8>
          </TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
      </DATA-ELEMENTS>
    </SENDER-RECEIVER-INTERFACE>'''

        analysis_swc_name = None
        analysis_behavior_name = None
        analysis_runnable_name = None
        analysis_ecu_name = None
        analysis_soc_name = None
        analysis_cluster_name = None
        analysis_interface_name = None

        if cat_id == 15:
            analysis_interface_name = f"Analysis_Interface_{random.randint(1, 1000)}"
            complete_xml += f'''
    <SENDER-RECEIVER-INTERFACE>
      <SHORT-NAME name="{analysis_interface_name}" />
      <DATA-ELEMENTS>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME name="AnalysisValue" />
          <TYPE-TREF>
            <Array-of-uint8 No_Of_Bytes="64">
              <Random-Values-generated>
                <Data-Range min="0" max="255" />
              </Random-Values-generated>
            </Array-of-uint8>
          </TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
      </DATA-ELEMENTS>
    </SENDER-RECEIVER-INTERFACE>'''

            analysis_swc_name = f"AnalysisSWC_{random.randint(1, 1000)}"
            analysis_behavior_name = f"{analysis_swc_name}_Behavior"
            analysis_runnable_name = f"{analysis_swc_name}_Runnable"
            complete_xml += f"""
    <APPLICATION-SW-COMPONENT-TYPE>
      <SHORT-NAME name="{analysis_swc_name}" />
      <PORTS>
        <R-PORT-PROTOTYPE>
          <SHORT-NAME name="AnalysisInput" />
          <REQUIRED-INTERFACE-TREF DEST="/{analysis_interface_name}" />
        </R-PORT-PROTOTYPE>
      </PORTS>
      <INTERNAL-BEHAVIORS>
        <SWC-INTERNAL-BEHAVIOR>
          <SHORT-NAME name="{analysis_behavior_name}" />
          <RUNNABLES>
            <RUNNABLE-ENTITY>
              <SHORT-NAME name="{analysis_runnable_name}" />
              <DATA-READ-ACCESS>
                <VARIABLE-ACCESS>
                  <SHORT-NAME name="AnalysisRead" />
                  <ACCESSED-VARIABLE>
                    <AUTOSAR-VARIABLE-IREF>
                      <PORT-PROTOTYPE-REF DEST="/{analysis_swc_name}/AnalysisInput" />
                      <TARGET-DATA-PROTOTYPE-REF DEST="/{analysis_interface_name}/AnalysisValue" />
                    </AUTOSAR-VARIABLE-IREF>
                  </ACCESSED-VARIABLE>
                </VARIABLE-ACCESS>
              </DATA-READ-ACCESS>
            </RUNNABLE-ENTITY>
          </RUNNABLES>
          <EVENTS>
            <TIMING-EVENT>
              <SHORT-NAME name="AnalysisEvent" />
              <START-ON-EVENT-REF DEST="/{analysis_swc_name}/{analysis_behavior_name}/{analysis_runnable_name}" />
              <PERIOD value="10" unit="ms" />
            </TIMING-EVENT>
          </EVENTS>
        </SWC-INTERNAL-BEHAVIOR>
      </INTERNAL-BEHAVIORS>
    </APPLICATION-SW-COMPONENT-TYPE>"""

        num_ecus = 1
        num_socs_per_ecu = 1
        num_chiplets_per_soc = 1
        num_gh_per_chiplet = len(interface_names)

        for ecu_idx in range(num_ecus):
            ecu_name = (
                fake.word().capitalize() if fake else f"ECU_{random.randint(1, 100)}"
            )
            if cat_id == 15:
                analysis_ecu_name = ecu_name
            complete_xml += f'''
    <ECUs>
      <SHORT-NAME name="{ecu_name}" />'''

            for soc_idx in range(num_socs_per_ecu):
                soc_name = (
                    fake.word().capitalize()
                    if fake
                    else f"SoC_{random.randint(1, 100)}"
                )
                if cat_id == 15:
                    analysis_soc_name = soc_name
                bus_width = random.choice([16, 32, 48, 64, 128])
                bus_freq = random.randint(400_000_000, 1_600_000_000)
                eth_mode = random.choice(["simulated", "native"])
                if cat_id == 15:
                    ucie_mode = "host"
                else:
                    ucie_mode = random.choice(["host", "endpoint"])
                native_consumed = eth_mode == "native"

                complete_xml += f'''
      <SoCs>
        <SHORT-NAME name="{soc_name}" />
        <AXI-BUS width="{bus_width}" frequency="{bus_freq}" />
        <ETHERNET-INTERFACE Mode="{eth_mode}" />
        <UCIe-INTERFACE Mode="{ucie_mode}" />'''

                for chiplet_idx in range(num_chiplets_per_soc):
                    chiplet_name = (
                        fake.word().capitalize()
                        if fake
                        else f"Chiplet_{random.randint(1, 100)}"
                    )
                    chiplet_bus_width = random.choice([32, 48, 64, 128])
                    chiplet_bus_freq = random.randint(500_000_000, 1_800_000_000)
                    chiplet_eth_mode = (
                        "native"
                        if (not native_consumed and random.choice([True, False]))
                        else "simulated"
                    )
                    native_consumed = native_consumed or chiplet_eth_mode == "native"
                    if cat_id == 15:
                        chiplet_ucie_mode = "host"
                    else:
                        chiplet_ucie_mode = random.choice(["host", "endpoint"])
                    complete_xml += f'''
        <Chiplet>
          <SHORT-NAME name="{chiplet_name}" />
          <AXI-BUS width="{chiplet_bus_width}" frequency="{chiplet_bus_freq}" />
          <ETHERNET-INTERFACE Mode="{chiplet_eth_mode}" />
          <UCIe-INTERFACE Mode="{chiplet_ucie_mode}" />'''

                    chiplet_hw_names = set()
                    for gh_idx in range(num_gh_per_chiplet):
                        base_hw_name = (
                            fake.word().capitalize()
                            if fake
                            else f"GH_{random.randint(1, 100)}"
                        )
                        gh_name = _reserve_hw_name(chiplet_hw_names, base_hw_name)
                        gh_freq = random.randint(1000000, 1000000000)
                        priority = random.randint(0, 255)
                        internal_mem = random.choice(["true", "false"])
                        latency_value = random.randint(10, 100)
                        latency_unit = random.choice(["s", "ms", "us", "ns"])
                        period_value = random.randint(10, 1000)
                        period_unit = "ms"
                        split_pw = round(random.uniform(5.0, 50.0), 1)
                        delay_pw = round(random.uniform(3.0, 40.0), 1)
                        seq_pw = round(random.uniform(8.0, 60.0), 1)
                        leak_pw = round(random.uniform(0.01, 0.5), 2)
                        clock_pw = round(random.uniform(0.5, 5.0), 1)
                        nominal_clock = random.randint(50, 200)
                        output_interface = interface_names[
                            gh_idx % len(interface_names)
                        ]
                        input_interface = interface_names[
                            (gh_idx + 1) % len(interface_names)
                        ]
                        include_second_latency = random.choice([True, False])
                        optional_latency = ""
                        if include_second_latency:
                            optional_latency = f'''
                <OPERATION>
                  <LATENCY value="{latency_value}" unit="{latency_unit}" />
                </OPERATION>'''

                        complete_xml += f'''
          <Generic_Hardware>
            <SHORT-NAME name="{gh_name}" />
            <Frequency value="{gh_freq}" />
            <AXI-Master-Port priority="{priority}" />
            <MEMORY-INTERFACE InternalMemory="{internal_mem}" />
            <INTERNAL-BEHAVIOR>
              <PORTS>
                <P-PORT-PROTOTYPE>
                  <SHORT-NAME name="OutputPort" />
                  <PROVIDED-INTERFACE-TREF DEST="/{output_interface}" />
                </P-PORT-PROTOTYPE>
                <R-PORT-PROTOTYPE>
                  <SHORT-NAME name="InputPort" />
                  <REQUIRED-INTERFACE-TREF DEST="/{input_interface}" />
                </R-PORT-PROTOTYPE>
              </PORTS>
              <OPERATIONS-SEQUENCE>
                <OPERATION>
                  <READ>
                    <IREF DEST="/{gh_name}/InputPort" />
                  </READ>
                </OPERATION>
                <OPERATION>
                  <LATENCY value="{latency_value}" unit="{latency_unit}" />
                </OPERATION>
                <OPERATION>
                  <WRITE>
                    <IREF DEST="/{gh_name}/OutputPort" />
                  </WRITE>
                </OPERATION>
                {optional_latency}
              </OPERATIONS-SEQUENCE>
              <EVENT>
                <TIMING-EVENT>
                  <PERIOD value="{period_value}" unit="{period_unit}" />
                </TIMING-EVENT>
              </EVENT>
            </INTERNAL-BEHAVIOR>
            <POWER-PARAMETERS Split_power_mw="{split_pw}" Delay_power_mw="{
                            delay_pw
                        }" Sequential_power_mw="{seq_pw}" Static_Power_Leakage_mw="{
                            leak_pw
                        }" Clock_Tree_Power_mw="{
                            clock_pw
                        }" Power_Per_Nominal_Clock_Mhz="{nominal_clock}" />
          </Generic_Hardware>'''

                    if cat_id == 15 and analysis_interface_name:
                        provider_name = _reserve_hw_name(
                            chiplet_hw_names,
                            "AnalysisFeed",
                        )
                        complete_xml += f'''
          <Generic_Hardware>
            <SHORT-NAME name="{provider_name}" />
            <Frequency value="{random.randint(50000000, 150000000)}" />
            <AXI-Master-Port priority="32" />
            <MEMORY-INTERFACE InternalMemory="false" />
            <INTERNAL-BEHAVIOR>
              <PORTS>
                <P-PORT-PROTOTYPE>
                  <SHORT-NAME name="AnalysisOut" />
                  <PROVIDED-INTERFACE-TREF DEST="/{analysis_interface_name}" />
                </P-PORT-PROTOTYPE>
              </PORTS>
              <OPERATIONS-SEQUENCE>
                <OPERATION>
                  <WRITE>
                    <IREF DEST="/{provider_name}/AnalysisOut" />
                  </WRITE>
                </OPERATION>
              </OPERATIONS-SEQUENCE>
              <EVENT>
                <TIMING-EVENT>
                  <PERIOD value="10" unit="ms" />
                </TIMING-EVENT>
              </EVENT>
            </INTERNAL-BEHAVIOR>
          </Generic_Hardware>'''

                    complete_xml += f"""
        </Chiplet>"""

                cores_per_cluster = (
                    "1" if cat_id == 15 else random.choice(["1", "2", "4"])
                )
                cluster_name = (
                    fake.word().capitalize()
                    if fake
                    else f"Cluster_{random.randint(1, 100)}"
                )
                cluster_os_mode = "nucleus" if cat_id == 15 else "linux"
                if cluster_os_mode == "linux":
                    cluster_freq = 1000000000
                else:
                    cluster_freq = random.randint(800_000_000, 1_000_000_000)
                affine_tasks = (
                    "true" if cat_id == 15 else random.choice(["true", "false"])
                )
                uart_terminal = (
                    "true" if cat_id == 15 else random.choice(["true", "false"])
                )
                ubuntu_fs = (
                    fake.word() if fake else f"ubuntu_fs_{random.randint(1, 100)}"
                )
                if cat_id == 15:
                    analysis_cluster_name = cluster_name
                complete_xml += f"""
{
                    build_cpu_cluster_block(
                        cluster_name,
                        cluster_freq,
                        cores_per_cluster,
                        indent="      ",
                        os_mode=cluster_os_mode,
                        file_system=ubuntu_fs,
                        affine_tasks=affine_tasks,
                        show_uart=uart_terminal,
                        family="ARMV8-Family",
                        variant="CortexA72",
                    )
                }
      </SoCs>"""
                if cat_id == 15:
                    analysis_sections.append(build_analysis_section(ecu_name, soc_name))

        complete_xml += f"""
    </ECUs>"""

        if (
            cat_id == 15
            and analysis_swc_name
            and analysis_behavior_name
            and analysis_runnable_name
            and analysis_ecu_name
            and analysis_soc_name
            and analysis_cluster_name
        ):
            complete_xml += f"""
    <HW-SW-MAPPING ClusterRef="/{analysis_ecu_name}/{analysis_soc_name}/{analysis_cluster_name}">
      <Core-Runnable-Mapping CoreId="0" RunnableRef="/{analysis_swc_name}/{analysis_behavior_name}/{analysis_runnable_name}" Load="50000" Priority="12" />
    </HW-SW-MAPPING>"""

        complete_xml += f"""
  </ELEMENTS>
</AR-PACKAGE>"""

    complete_xml = append_sections_before_elements_end(complete_xml, analysis_sections)
    complete_xml = apply_prompt_alignment(
        complete_xml, prefix=prefix, metadata=prompt_meta
    )
    return complete_xml

def generate_high_quality_cat3(prompt_meta):
    """
    Generates structurally diverse, valid AUTOSAR XML for Category 3 (Timing/Latency).
    """
    latency_req = prompt_meta.get("latency_us", random.randint(10, 100))
    cpu_architecture = prompt_meta.get("cpu_arch", "ARMv9 Cortex-A720")
    memory_mb = prompt_meta.get("ram_mb", 256)
    power_mw = prompt_meta.get("power_mw", 100)
    
    core_type = "CortexA72"
    if "A53" in cpu_architecture: core_type = "CortexA53"
    elif "A57" in cpu_architecture: core_type = "CortexA57"
    elif "R52" in cpu_architecture: core_type = "CortexR52"
    
    freq_hz = 1000000000

    used_dummy_ports = set()

    def gen_generic_hw(index):
        latency_val = latency_req if index == 0 else random.randint(5, 50)
        num_ops = random.randint(1, 3)
        ports_xml = ""
        ops_xml = ""
        
        # Use index combined with some unique state to ensure we only do this once
        # Actually, let's just use the first two times this function is called EVER.
        call_count = len(used_dummy_ports)
        
        if call_count == 0:
            used_dummy_ports.add(0)
            ports_xml = """
              <PORTS>
                <P-PORT-PROTOTYPE>
                  <SHORT-NAME name="Out_1" />
                  <PROVIDED-INTERFACE-TREF DEST="/Timing_Interface_1" />
                </P-PORT-PROTOTYPE>
                <R-PORT-PROTOTYPE>
                  <SHORT-NAME name="In_2" />
                  <REQUIRED-INTERFACE-TREF DEST="/Timing_Interface_2" />
                </R-PORT-PROTOTYPE>
              </PORTS>"""
            ops_xml = """
                 <OPERATION>
                   <READ><IREF DEST="/Timing_Monitor_HW_0/In_2" /></READ>
                 </OPERATION>
                 <OPERATION>
                   <WRITE><IREF DEST="/Timing_Monitor_HW_0/Out_1" /></WRITE>
                 </OPERATION>"""
        elif call_count == 1:
            used_dummy_ports.add(1)
            ports_xml = """
              <PORTS>
                <P-PORT-PROTOTYPE>
                  <SHORT-NAME name="Out_2" />
                  <PROVIDED-INTERFACE-TREF DEST="/Timing_Interface_2" />
                </P-PORT-PROTOTYPE>
                <R-PORT-PROTOTYPE>
                  <SHORT-NAME name="In_1" />
                  <REQUIRED-INTERFACE-TREF DEST="/Timing_Interface_1" />
                </R-PORT-PROTOTYPE>
              </PORTS>"""
            ops_xml = """
                 <OPERATION>
                   <READ><IREF DEST="/Timing_Monitor_HW_1/In_1" /></READ>
                 </OPERATION>
                 <OPERATION>
                   <WRITE><IREF DEST="/Timing_Monitor_HW_1/Out_2" /></WRITE>
                 </OPERATION>"""
        else:
            ports_xml = "<PORTS />"

        for i in range(num_ops):
            ops_xml += f"""
               <OPERATION>
                 <LATENCY value="{latency_val + i*5}" unit="us" />
               </OPERATION>"""

        return f"""
           <Generic_Hardware>
             <SHORT-NAME name="Timing_Monitor_HW_{index}" />
             <Frequency value="{random.randint(200, 800) * 1000000}" />
             <AXI-Master-Port priority="{random.randint(0, 5) if index == 0 else random.randint(10, 50)}" />
             <MEMORY-INTERFACE InternalMemory="{"true" if random.random() > 0.5 else "false"}"/>
             <INTERNAL-BEHAVIOR>
               {ports_xml}
               <OPERATIONS-SEQUENCE>{ops_xml}
               </OPERATIONS-SEQUENCE>
               <EVENT>
                  <TIMING-EVENT>
                    <PERIOD value="{random.randint(10, 100)}" unit="ms" />
                  </TIMING-EVENT>
               </EVENT>
             </INTERNAL-BEHAVIOR>
             <POWER-PARAMETERS Split_power_mw="{power_mw * 0.4}" Delay_power_mw="{power_mw * 0.2}" Sequential_power_mw="{power_mw * 0.4}" />
          </Generic_Hardware>"""

    def pattern_multi_soc():
        num_socs = 1  # Standardize for Cat 3
        inner_xml = ""
        for i in range(num_socs):
            hws = "".join([gen_generic_hw(j) for j in range(2)]) # Always generate at least 2 to satisfy Rule 29/30
            inner_xml += f"""
        <SoCs>
          <SHORT-NAME name="SoC_Node_{i}" />
          <AXI-BUS width="64" frequency="{freq_hz}" />
          <ETHERNET-INTERFACE Mode="simulated" />
          <UCIe-INTERFACE Mode="endpoint" />
          {hws}
        </SoCs>"""
        return inner_xml

    def pattern_nested_chiplets():
        num_chiplets = random.randint(1, 2)
        chiplets_xml = ""
        for i in range(num_chiplets):
            hws = "".join([gen_generic_hw(j) for j in range(random.randint(1, 2))])
            chiplets_xml += f"""
        <Chiplet>
          <SHORT-NAME name="Chiplet_Layer_{i}_{random.randint(1, 100)}" />
          <AXI-BUS width="128" frequency="{freq_hz // 2}" />
          <ETHERNET-INTERFACE Mode="simulated" />
          <UCIe-INTERFACE Mode="host" />
          {hws}
        </Chiplet>"""
        
        return f"""
        <SoCs>
          <SHORT-NAME name="SoC_Aggregator" />
          <AXI-BUS width="256" frequency="{freq_hz}" />
          <ETHERNET-INTERFACE Mode="native" />
          <UCIe-INTERFACE Mode="host" />
          {chiplets_xml}
          <CPU_Cluster>
            <Operating-System>
              <Linux Affine-tasks-byOS="true" Show_UART_Terminal="true">
                <Ubuntu_File_System>cluster_fs_{memory_mb}</Ubuntu_File_System>
              </Linux>
            </Operating-System>
            <ARMV8-Family>
              <{core_type} CoresPerCluster="{random.choice(['4','8'])}">
                <SHORT-NAME name="MasterCore" />
                <Frequency value="{freq_hz}" />
              </{core_type}>
            </ARMV8-Family>
          </CPU_Cluster>
        </SoCs>"""

    def pattern_hybrid():
        hws = "".join([gen_generic_hw(j) for j in range(2)]) # Always 2 HW
        return f"""
        <SoCs>
          <SHORT-NAME name="SoC_Hybrid" />
          <AXI-BUS width="64" frequency="{freq_hz}" />
          <ETHERNET-INTERFACE Mode="simulated" />
          <UCIe-INTERFACE Mode="host" />
          <CPU_Cluster>
            <Operating-System>
              <Linux Affine-tasks-byOS="true" Show_UART_Terminal="true">
                <Ubuntu_File_System>custom_fs</Ubuntu_File_System>
              </Linux>
            </Operating-System>
            <ARMV8-Family>
              <{core_type} CoresPerCluster="4">
                <SHORT-NAME name="TargetCore" />
                <Frequency value="{freq_hz}" />
              </{core_type}>
            </ARMV8-Family>
          </CPU_Cluster>
          {hws}
        </SoCs>"""

    pattern_func = random.choice([pattern_multi_soc, pattern_nested_chiplets, pattern_hybrid])
    elements_inner = pattern_func()

    xml = f"""<AR-PACKAGE>
  <ELEMENTS>
    <SENDER-RECEIVER-INTERFACE>
      <SHORT-NAME name="Timing_Interface_1" />
      <DATA-ELEMENTS>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME name="Data" />
          <TYPE-TREF>
            <Array-of-uint8 No_Of_Bytes="256">
                <Random-Values-generated>
                    <Data-Range min="0" max="255" />
                </Random-Values-generated>
            </Array-of-uint8>
          </TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
      </DATA-ELEMENTS>
    </SENDER-RECEIVER-INTERFACE>
    <SENDER-RECEIVER-INTERFACE>
      <SHORT-NAME name="Timing_Interface_2" />
      <DATA-ELEMENTS>
        <VARIABLE-DATA-PROTOTYPE>
          <SHORT-NAME name="Data" />
          <TYPE-TREF>
            <Array-of-uint8 No_Of_Bytes="256">
                <Random-Values-generated>
                    <Data-Range min="0" max="255" />
                </Random-Values-generated>
            </Array-of-uint8>
          </TYPE-TREF>
        </VARIABLE-DATA-PROTOTYPE>
      </DATA-ELEMENTS>
    </SENDER-RECEIVER-INTERFACE>
    <ECUs>
      <SHORT-NAME name="HighPerfECU_{random.randint(1,9999)}" />
      {elements_inner}
    </ECUs>
  </ELEMENTS>
</AR-PACKAGE>"""
    return xml

def export_xml_to_folder(complete_xml, category_id, example_num):
    os.makedirs(GENERATED_XML_DIR, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    import glob
    pattern = os.path.join(GENERATED_XML_DIR, f"category_{category_id}_example_*.xml")
    existing_files = glob.glob(pattern)

    existing_numbers = set()
    for file_path in existing_files:
        filename = os.path.basename(file_path)
        match = re.search(r"category_\d+_example_(\d+)", filename)
        if match:
            existing_numbers.add(int(match.group(1)))

    next_num = 1
    while next_num in existing_numbers:
        next_num += 1

    filename = os.path.join(
        GENERATED_XML_DIR,
        f"category_{category_id}_example_{next_num}_{timestamp}.xml"
    )
    with open(filename, "w", encoding="utf-8") as f:
        f.write(complete_xml)
    print(f"Exported XML to {filename}")
    return filename
