# Quick Start Guide - AUTOSAR AE Data Studio

## How to Run the System

### 1. Generate Training Data (Main Use Case)

```bash
# Generate 10 examples for category 6
python Studio_CLI.py --category 6 --count 10
```

**What happens:**
- Generates 10 valid XML files for category 6
- Saves to `generated_xml/` directory
- Saves messages to `valid_data.jsonl`
- Shows progress bar and statistics

### 2. View Statistics

```bash
# Show statistics for all categories
python Studio_CLI.py --stats
```

**Output:**
```
================================================================================
Category Statistics
================================================================================
ID   Name                           XML Files    JSONL Records  
--------------------------------------------------------------------------------
3    Timing and Latency            50           50             
4    Interface Types               120          120            
...
```

### 3. Other Commands

```bash
# Synchronize organized data
python Studio_CLI.py --sync

# Clean up duplicate XML files
python Studio_CLI.py --cleanup

# Show help
python Studio_CLI.py --help
```

## GUI Applications

### Dashboard (Visual Interface)
```bash
streamlit run gui_app.py
```

- **Generate Tab**: Select category and count, click generate
- **View Tab**: Browse generated files
- **Edit Tab**: Manage JSONL files

### Copilot (Chat Interface)
```bash
streamlit run chat_app.py
```

### Validator (Professional Verification)
```bash
streamlit run validator_stearmlit_version.py
```

## Project Structure Explained

```
data/
│
├── Studio_CLI.py          ← YOU RUN THIS (main entry point)
│
├── cli/                   ← Command Line Interface
│   ├── command_parser.py  ← Reads your commands
│   └── output_formatter.py ← Shows results to you
│
├── services/              ← Does the actual work
│   ├── generation_service.py  ← Generates XML
│   ├── validation_service.py  ← Validates XML
│   ├── export_service.py      ← Saves files
│   └── statistics_service.py  ← Counts and reports
│
├── managers/              ← Manages data
│   ├── category_manager.py    ← Handles categories
│   ├── jsonl_manager.py       ← Reads/writes JSONL
│   └── file_manager.py        ← File operations
│
├── core/                  ← Core components
│   ├── settings.py        ← Configuration
│   ├── xml_builder.py     ← XML building
│   └── prompt_manager.py  ← Prompt generation
│
└── validators/            ← Validation engine
    └── validation_pipeline.py
```

## What Each Folder Does (Simple)

| Folder | What it does | You need to know |
|--------|--------------|------------------|
| **`cli/`** | Handles commands and output | You interact with this |
| **`services/`** | Does the work (generate, validate, export) | This is the engine |
| **`managers/`** | Organizes data and files | Helper layer |
| **`core/`** | Shared code (XML, prompts, settings) | Reusable components |
| **`validators/`** | Checks if XML is valid | Quality control |

## Common Tasks

### Task 1: Generate Data for a Category
```bash
python Studio_CLI.py --category 6 --count 10
```

### Task 2: Check What You've Generated
```bash
python Studio_CLI.py --stats
```

### Task 3: Generate Reproducible Data
```bash
# Same seed = same results
python Studio_CLI.py --category 3 --count 5 --seed 42
```

### Task 4: Use the GUI
```bash
streamlit run gui_app.py
# Then click "Generate Data" tab
```

## Files Created

After running generation, you'll find:

```
generated_xml/
├── category_6_example_1_20260117_210000.xml
├── category_6_example_2_20260117_210001.xml
└── ...

valid_data.jsonl              ← All training data

messages/
└── Category6/
    └── messages.jsonl         ← Category-specific messages
```

## Python API (Advanced)

You can also use the services directly in Python:

```python
from services import GenerationService
from managers import CategoryManager

# Initialize
gen_service = GenerationService()
cat_manager = CategoryManager()

# Get category config
config = cat_manager.get_category(6)

# Generate
prompt, xml, meta = gen_service.generate_prompt_and_xml(6, config)

print(f"Generated XML: {len(xml)} characters")
```

## Need Help?

```bash
# Show all available commands
python Studio_CLI.py --help

# View documentation
cat SOLID_ARCHITECTURE.md
cat PROJECT_STRUCTURE.md
```

## Migration from Old System

If you used the old `auto_data.py`:

**Old way:**
```bash
python auto_data.py --category 6 --count 10
```

**New way (same result):**
```bash
python Studio_CLI.py --category 6 --count 10
```

Everything works the same, just more organized!

## Summary

**To run the system**: Use `Studio_CLI.py`

**Main command**: 
```bash
python Studio_CLI.py --category [ID] --count [NUMBER]
```

**The `cli/` folder**: Handles your commands and shows you results

