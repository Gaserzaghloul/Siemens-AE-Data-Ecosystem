# Siemens Automation - AE Ecosystem

![Project Status](https://img.shields.io/badge/Status-Active-success)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue)
![Siemens](https://img.shields.io/badge/Standard-AUTOSAR-009999)

## Overview

**Siemens Automation AE Ecosystem** is a professional-grade environment designed to synthesize high-fidelity data for the automotive industry. It serves as a comprehensive ecosystem for generating complex **XML scenarios** that strictly adhere to AUTOSAR XSD schemas and Schematron rules.

This system is engineered to create a precise mapping between natural language **prompts** and their corresponding **XML structures**. By supporting varying styles (technical, narrative, direct) and complexity levels (small to large), the ecosystem produces diverse datasets that are ideal for **fine-tuning Large Language Models (LLMs)** like OpenAI's GPT series, effectively bridging the gap between human intent and machine-readable automotive standards.

## Key Features

*   **Schema-Compliant XML Generation**: Produces valid ARXML files by strictly enforcing industry standards through a multi-layer validation pipeline (XSD + Schematron).
*   **Prompt-to-XML Mapping**: Maintains a direct correlation between the input prompt's intent and the generated XML architecture, ensuring high-quality supervised learning data.
*   **Diverse Data Synthesis**: Generates data across 14 specialized automotive categories, with variable styles and sizes to prevent overfitting during model training.
*   **OpenAI Fine-Tuning Ready**: Outputs clean, structured `.jsonl` datasets specifically formatted for optimizing AI models on automotive domain knowledge.
*   **Triple-Layer Validation**:
    1.  **Structure**: XSD Schema conformance.
    2.  **Logic**: Schematron rule enforcement for business constraints.
    3.  **Semantic**: Advanced Python-based logical consistency checks.

## System Architecture

The following diagram illustrates the streamlined flow from data configuration to various validated outputs.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'mainBkg': '#ffffff', 'background': '#ffffff', 'primaryColor': '#ffffff', 'edgeLabelBackground': '#ffffff', 'clusterBkg': '#ffffff', 'clusterBorder': '#333333', 'textColor': '#000000', 'lineColor': '#333333' }}}%%
graph TD
    subgraph Input_Phase [1. Input Definition]
        Input([Configuration & Prompts])
    end

    subgraph Core_Engine [2. Generation Core]
        Engine[Core Generation Logic]
        Builder[XML Builder]
        Map[Prompt Mapper]
        
        Input --> Engine
        Engine --> Map
        Map -->|Map Intent| Builder
    end

    subgraph Validation_Phase [3. Quality Assurance]
        Validator{Validation Pipeline}
        
        Rule1[XSD Schema]
        Rule2[Schematron Rules]
        Rule3[Python Logic]
        
        Builder -->|Draft XML| Validator
        Validator --> Rule1
        Validator --> Rule2
        Validator --> Rule3
    end

    subgraph Output_Phase [4. Knowledge Base & Export]
        Storage[(Validated Database)]
        Output1[OpenAI Fine-Tuning Data]
        Output2[Standard AUTOSAR XML]
        
        Rule1 & Rule2 & Rule3 -->|Pass| Storage
        Storage --> Output1
        Storage --> Output2
    end
    
    Validator -- Fail --> Feedback[Error Feedback Loop]
    Feedback -.-> Engine

    %% Styling for White Background & High Contrast
    style Input_Phase fill:#ffffff,stroke:#333,stroke-width:2px
    style Core_Engine fill:#ffffff,stroke:#333,stroke-width:2px
    style Validation_Phase fill:#ffffff,stroke:#333,stroke-width:2px
    style Output_Phase fill:#ffffff,stroke:#333,stroke-width:2px

    style Input fill:#f9f9f9,stroke:#000,stroke-width:2px,color:#000
    style Engine fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000
    style Builder fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000
    style Map fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000
    
    style Validator fill:#ffebee,stroke:#c62828,stroke-width:3px,color:#000
    style Rule1 fill:#ffcdd2,stroke:#c62828,color:#000
    style Rule2 fill:#ffcdd2,stroke:#c62828,color:#000
    style Rule3 fill:#ffcdd2,stroke:#c62828,color:#000
    
    style Storage fill:#e0f2f1,stroke:#00695c,stroke-width:2px,color:#000
    style Output1 fill:#b2dfdb,stroke:#00695c,color:#000
    style Output2 fill:#b2dfdb,stroke:#00695c,color:#000
    style Feedback fill:#fff3e0,stroke:#e65100,stroke-dasharray: 5 5,color:#000
```

## Project Structure

```text
Siemens-AE-Ecosystem/
├── core/                 # XML generation logic and template mapping
├── services/             # Orchestration services for data export and analysis
├── managers/             # Configuration managers for categories and files
├── validators/           # Triple-layer validation engine
├── cli/                  # Command Line Interface tools
├── Studio_CLI.py         # Primary CLI entry point
├── gui_app.py            # Streamlit-based graphical interface
├── AE_XSD_schema.xsd.xml # AUTOSAR Schema Definition
└── SchematronRules.sch   # Business Logic Rules
```

*Developed for Siemens  *
