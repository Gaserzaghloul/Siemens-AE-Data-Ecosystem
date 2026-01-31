# Automation Dataset Categories

This document outlines the dataset categories, their descriptions, and example prompts used for generation.

## Category 3: Timing/Latency Element
**Description**: timing/latency element
**Example Prompt**:
> "Generate a single XML element for {key}.
> Requirements:
> 1. Use the correct schema attributes (value, unit).
> 2. Ensure the unit is valid (s, ms, us, ns).
> 3. Value should be a reasonable positive number.
> 4. Do not wrap in a root element, just the single element."

## Category 4: CPU Cluster Configuration
**Description**: CPU cluster configuration
**Example Prompt**:
> "Design a comprehensive CPU architecture focusing on {key}. Requirements:
> 1. Multiple CPU cores with different performance characteristics
> 2. Proper core scheduling and load balancing mechanisms
> 3. Support for both symmetric and asymmetric multiprocessing
> 4. Advanced cache hierarchy and memory management
> 5. CPU power management and thermal control
> 6. Performance monitoring and optimization
> 7. CPU security and access control mechanisms
> 8. Support for CPU testing and validation
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional CPU design patterns."

## Category 5: Generic Hardware IP
**Description**: generic hardware IP
**Example Prompt**:
> "Design a comprehensive generic hardware architecture focusing on {key}. Requirements:
> 1. Multiple hardware components with different characteristics
> 2. Proper hardware abstraction and driver management
> 3. Support for both standard and custom hardware interfaces
> 4. Advanced hardware resource management and allocation
> 5. Hardware power management and thermal control
> 6. Performance monitoring and optimization
> 7. Hardware security and access control mechanisms
> 8. Support for hardware testing and validation
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional hardware design patterns."

## Category 6: Comprehensive Automotive ECU System
**Description**: comprehensive automotive ECU system with interfaces, software components, runnables, and HW-SW mappings
**Example Prompt**:
> "I need you to design a comprehensive automotive system architecture focusing on {key}. The system should include:
> 1. Multiple ECUs with different configurations and capabilities
> 2. SoC implementations with varying performance characteristics
> 3. Complete hardware abstraction layers
> 4. Proper inter-ECU communication protocols
> 5. Real-time processing capabilities
> 6. Power management and thermal considerations
> 7. Safety-critical system components
> 8. Scalable architecture for future enhancements
> 
> Please generate a complete AUTOSAR AE XML configuration that demonstrates best practices for automotive system design, including proper component relationships, data flow, and system integration patterns."

## Category 7: Network Topology
**Description**: network topology
**Example Prompt**:
> "Design a comprehensive network topology focusing on {key}. Requirements:
> 1. Multiple network segments with different characteristics
> 2. Proper network routing and switching mechanisms
> 3. Support for both wired and wireless communication
> 4. Advanced network security and access control
> 5. Network performance optimization and QoS management
> 6. Fault tolerance and redundancy mechanisms
> 7. Network monitoring and diagnostics
> 8. Support for network testing and validation
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional network design patterns."

## Category 8: Software Component
**Description**: software component
**Example Prompt**:
> "Design a comprehensive software component architecture focusing on {key}. Requirements:
> 1. Multiple SWC types with different functional characteristics
> 2. Proper component interfaces and dependencies
> 3. Support for both periodic and event-driven execution
> 4. Component lifecycle management and state handling
> 5. Error handling and recovery mechanisms
> 6. Performance optimization and resource management
> 7. Component testing and validation frameworks
> 8. Support for component reuse and modularity
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional software component design."

## Category 9: Communication Interface
**Description**: communication interface
**Example Prompt**:
> "Design a comprehensive interface architecture for automotive systems focusing on {key}. Requirements:
> 1. Multiple interface types with different data characteristics
> 2. Proper data validation and error handling mechanisms
> 3. Support for both synchronous and asynchronous communication
> 4. Interface versioning and backward compatibility
> 5. Performance optimization for different data types
> 6. Security measures for sensitive data transmission
> 7. Diagnostic capabilities for interface monitoring
> 8. Support for both local and remote interfaces
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional interface design patterns."

## Category 10: Hardware Operations Sequence
**Description**: hardware operations sequence
**Example Prompt**:
> "Design a comprehensive operations sequence focusing on {key}. Requirements:
> 1. Multiple operation types with different execution characteristics
> 2. Proper operation sequencing and dependency management
> 3. Support for both sequential and parallel operation execution
> 4. Advanced timing and synchronization mechanisms
> 5. Operation error handling and recovery
> 6. Performance optimization and resource management
> 7. Operation monitoring and diagnostics
> 8. Support for operation testing and validation
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional operation design patterns."

## Category 11: Power Parameters
**Description**: power parameters
**Example Prompt**:
> "Design a comprehensive power management system focusing on {key}. Requirements:
> 1. Multiple power domains with different characteristics
> 2. Proper power sequencing and dependency management
> 3. Support for both static and dynamic power management
> 4. Advanced power monitoring and optimization
> 5. Power security and access control mechanisms
> 6. Thermal management and cooling strategies
> 7. Power testing and validation frameworks
> 8. Support for power evolution and updates
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional power management design."

## Category 12: Hardware-Software Mapping
**Description**: hardware-software mapping
**Example Prompt**:
> "Design a comprehensive hardware-software mapping system focusing on {key}. Requirements:
> 1. Multiple mapping strategies with different characteristics
> 2. Proper resource allocation and load balancing
> 3. Support for both static and dynamic mapping
> 4. Advanced mapping optimization and performance tuning
> 5. Mapping security and access control mechanisms
> 6. Performance monitoring and diagnostics
> 7. Mapping testing and validation frameworks
> 8. Support for mapping evolution and updates
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional mapping design."

## Category 13: Pre-Built Application
**Description**: pre-built application
**Example Prompt**:
> "Design a comprehensive pre-built application system focusing on {key}. Requirements:
> 1. Multiple application types with different characteristics
> 2. Proper application lifecycle and state management
> 3. Support for both embedded and cloud-based applications
> 4. Advanced application optimization and performance tuning
> 5. Application security and access control mechanisms
> 6. Performance monitoring and diagnostics
> 7. Application testing and validation frameworks
> 8. Support for application evolution and updates
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional application design."

## Category 14: Chiplet Architecture
**Description**: chiplet architecture
**Example Prompt**:
> "Design a comprehensive chiplet configuration system focusing on {key}. Requirements:
> 1. Multiple chiplet types with different characteristics
> 2. Proper chiplet integration and communication protocols
> 3. Support for both homogeneous and heterogeneous chiplets
> 4. Advanced chiplet optimization and performance tuning
> 5. Chiplet security and access control mechanisms
> 6. Performance monitoring and diagnostics
> 7. Chiplet testing and validation frameworks
> 8. Support for chiplet evolution and updates
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional chiplet design."

## Category 15: Analysis Configuration
**Description**: analysis configuration
**Example Prompt**:
> "Design a comprehensive analysis configuration system focusing on {key}. Requirements:
> 1. Multiple analysis types with different characteristics
> 2. Proper analysis data collection and processing
> 3. Support for both real-time and batch analysis
> 4. Advanced analysis optimization and performance tuning
> 5. Analysis security and access control mechanisms
> 6. Performance monitoring and diagnostics
> 7. Analysis testing and validation frameworks
> 8. Support for analysis evolution and updates
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional analysis design."

## Category 16: Software Component Behavior
**Description**: software component behavior
**Example Prompt**:
> "Design a comprehensive SWC custom behavior system focusing on {key}. Requirements:
> 1. Multiple behavior types with different characteristics
> 2. Proper behavior composition and orchestration
> 3. Support for both deterministic and probabilistic behaviors
> 4. Advanced behavior optimization and performance tuning
> 5. Behavior security and access control mechanisms
> 6. Performance monitoring and diagnostics
> 7. Behavior testing and validation frameworks
> 8. Support for behavior evolution and updates
> 
> Generate a detailed AUTOSAR AE XML configuration that demonstrates professional behavior design."
