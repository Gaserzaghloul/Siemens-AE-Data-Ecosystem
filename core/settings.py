import os
from pathlib import Path

# ==============================================================================
# PROJECT PATHS
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# Directories
GENERATED_XML_DIR = BASE_DIR / "generated_xml"
MESSAGES_DIR = BASE_DIR / "messages"

# Essential Files
TRAINING_DATA_FILE = BASE_DIR / "training_data.jsonl"
VALID_DATA_FILE = BASE_DIR / "valid_data.jsonl"
ORGANIZED_DATA_FILE = BASE_DIR / "organized_valid_data.jsonl"
ORGANIZED_DATA_LAST_FILE = BASE_DIR / "organized_valid_data_last.json"
XSD_SCHEMA_FILE = BASE_DIR / "AE_XSD_schema.xsd.xml"
SCHEMATRON_RULES_FILE = BASE_DIR / "SchematronRules.sch"

# ==============================================================================
# CATEGORY CONFIGURATION
# ==============================================================================
# Categories from 3 to 16
CATEGORIES = {
    3: {
        "name": "TIME AND LATENCY ELEMENTS - HIGH PRIORITY",
        "keys": ["Simulation-Time", "PERIOD", "LATENCY", "Frequency"],
        "type": "atomic", 
        "user_prompt_style": "generate_time_latency",
        "assistant_template": None, 
    },
    4: {
        "name": "CPU CLUSTER CONFIGURATIONS - HIGH PRIORITY",
        "keys": ["CPU_Cluster"],
        "type": "generation", 
        "user_prompt_style": "generate_cpu",
        "assistant_template": "cpu_hierarchy",
    },
    5: {
        "name": "GENERIC HARDWARE COMPONENTS - HIGH PRIORITY",
        "keys": ["Generic_Hardware"],
        "type": "generation",
        "user_prompt_style": "generate_generic_hw",
        "assistant_template": "generic_hw_hierarchy",
    },
    6: {
        "name": "COMPLETE SYSTEM CONFIGURATIONS - HIGH PRIORITY",
        "keys": ["ECUs", "SoCs", "AR-PACKAGE"],
        "type": "generation",
        "user_prompt_style": "generate_core",
        "assistant_template": "core_hierarchy",
    },
    7: {
        "name": "AXI BUS AND NETWORK CONFIGURATIONS - MEDIUM PRIORITY",
        "keys": ["AXI-BUS", "ETHERNET-INTERFACE", "UCIe-INTERFACE", "CAN-BUS"],
        "type": "generation",
        "user_prompt_style": "generate_topology", 
        "assistant_template": "topology_hierarchy",
    },
    8: {
        "name": "SOFTWARE COMPONENTS (SWC) - MEDIUM PRIORITY",
        "keys": ["APPLICATION-SW-COMPONENT-TYPE"],
        "type": "generation",
        "user_prompt_style": "generate_swc",
        "assistant_template": "swc_hierarchy",
    },
    9: {
        "name": "INTERFACE DEFINITIONS - MEDIUM PRIORITY",
        "keys": ["SENDER-RECEIVER-INTERFACE"],
        "type": "generation",
        "user_prompt_style": "generate_interface",
        "assistant_template": "interface_hierarchy",
    },
    10: {
        "name": "OPERATIONS SEQUENCE - MEDIUM PRIORITY",
        "keys": ["OPERATIONS-SEQUENCE", "OPERATION"],
        "type": "generation",
        "user_prompt_style": "generate_operations",
        "assistant_template": "operations_hierarchy",
    },
    11: {
        "name": "POWER PARAMETERS - LOW PRIORITY",
        "keys": ["POWER-PARAMETERS"],
        "type": "generation",
        "user_prompt_style": "generate_power_params",
        "assistant_template": "power_focused_hierarchy",
    },
    12: {
        "name": "HARDWARE-SOFTWARE MAPPING - LOW PRIORITY",
        "keys": ["Core-Runnable-Mapping", "Cluster-PrebuiltApplication-Mapping", "HW-SW-MAPPING"],
        "type": "generation",
        "user_prompt_style": "generate_mapping",
        "assistant_template": "mapping_hierarchy",
    },
    13: {
        "name": "PRE-BUILT APPLICATIONS - LOW PRIORITY",
        "keys": ["PRE-BUILT-APPLICATION"],
        "type": "generation",
        "user_prompt_style": "generate_pre_built",
        "assistant_template": "prebuilt_hierarchy",
    },
    14: {
        "name": "CHIPLET CONFIGURATIONS - LOW PRIORITY",
        "keys": ["Chiplet"],
        "type": "generation",
        "user_prompt_style": "generate_chiplet",
        "assistant_template": "chiplet_full_hierarchy",
    },
    15: {
        "name": "ANALYSIS CONFIGURATIONS - LOW PRIORITY",
        "keys": ["Analysis"],
        "type": "generation",
        "user_prompt_style": "generate_analysis",
        "assistant_template": "analysis_hierarchy",
    },
    16: {
        "name": "SWC CUSTOM BEHAVIOR - LOW PRIORITY",
        "keys": ["SWC-CUSTOM-BEHAVIOR"],
        "type": "generation",
        "user_prompt_style": "generate_swc_behavior",
        "assistant_template": "swc_behavior_hierarchy",
    }
}

# ==============================================================================
# SCHEMA & MAPPING RULES
# ==============================================================================
SCHEMA_RULES = {
    "ECUs": {"min": 1, "max": 100},
    "SoCs": {"min": 1, "max": 100},
    "APPLICATION-SW-COMPONENT-TYPE": {"keys": ["SHORT-NAME"]},
    "INTERNAL-BEHAVIOR": {"keys": ["PORTS"]},
    "OPERATIONS-SEQUENCE": {"keys": ["OPERATION"]},
    "Network-Topology": {"keys": ["InterECU_communication"]},
    "CPU_Cluster": {"keys": ["ARMV9-Family"]},
    "Generic_Hardware": {"keys": ["SHORT-NAME"]},
    "POWER-PARAMETERS": {"min": 0.0},
    "Core-Runnable-Mapping": {
        "min_CoreId": 0,
        "max_CoreId": 7,
        "min_Priority": 1,
        "max_Priority": 99,
    },
    "Cluster-PrebuiltApplication-Mapping": {"keys": ["PrebuiltApplicationRef"]},
    "PRE-BUILT-APPLICATION": {"keys": ["SHORT-NAME", "PATH"]},
    "Chiplet": {"keys": ["SHORT-NAME"]},
    "Analysis": {"keys": ["SW-Analysis-Enable"]},
    "SWC-CUSTOM-BEHAVIOR": {"keys": ["SHORT-NAME", "OPERATIONS-SEQUENCE"]},
    "CONVOLUTION": {"min_kernelSize": 1},
    "MAX-POOL": {"min_stride": 1},
}

LABEL_OVERRIDES = {
    "AR-PACKAGE": "Pkg",
    "ELEMENTS": "Element",
    "SENDER-RECEIVER-INTERFACE": "Interface",
    "CLIENT-SERVER-INTERFACE": "Interface",
    "VARIABLE-DATA-PROTOTYPE": "Data",
    "P-PORT-PROTOTYPE": "Port",
    "R-PORT-PROTOTYPE": "Port",
    "ECUs": "ECU",
    "SoCs": "SoC",
    "Chiplet": "Chiplet",
    "Generic_Hardware": "HWIP",
    "CPU_Cluster": "Cluster",
    "APPLICATION-SW-COMPONENT-TYPE": "SWC",
    "SWC-IMPLEMENTATION": "SWCImpl",
    "INTERNAL-BEHAVIOR": "Behavior",
    "RUNNABLE-ENTITY": "Runnable",
    "OPERATION": "Operation",
    "EVENT": "Event",
    "TIMING-EVENT": "TimingEvent",
    "HW-SW-MAPPING": "Mapping",
    "CORE-RUNNABLE-MAPPING": "RunnableMapping",
    "ANALYSIS": "Analysis",
    "ANALYSIS-RULE": "AnalysisRule",
    "POWER-PARAMETERS": "Power",
    "PORT-PROTOTYPE": "Port",
    "RUNNABLE": "Runnable",
    "SWC-TASK": "SwcTask",
}

# ==============================================================================
# PROMPT SETTINGS
# ==============================================================================
PROMPT_SIZE_CYCLE = ["large", "large", "medium", "small"]
STYLE_SEQUENCE = [
    "formal",
    "user_friendly",
    "concise",
    "conversational",
    "professional",
]

FRIENDLY_ADJECTIVES = [
    "Aero", "Bright", "Calm", "Daring", "Edge", "Fleet", "Grand", "Horizon", 
    "Ion", "Jade", "Kinetic", "Lunar", "Metro", "Nova", "Orion", "Pulse", 
    "Quantum", "Rapid", "Solar", "Titan", "Urban", "Vivid", "Wave", "Zenith"
]

FRIENDLY_NOUNS = [
    "Bridge", "Circuit", "Drive", "Engine", "Force", "Grid", "Harbor", "Matrix", 
    "Network", "Orbit", "Path", "Relay", "Signal", "Torque", "Vector", "Wing"
]
