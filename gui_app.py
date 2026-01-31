import streamlit as st
import os
import json
import glob
import subprocess
import shutil

st.set_page_config(layout="wide", page_title="Data Studio")

# Custom CSS for Font Size (No Colors, No Emojis)
st.markdown("""
<style>
    /* Increase global font size */
    html, body, [class*="css"] {
        font-family: 'Arial', sans-serif;
    }
    
    .stMarkdown, .stText, p, li, .stCode, .stDataFrame {
        font-size: 1.2rem !important;
        line-height: 1.6 !important;
    }
    
    /* Increase headings */
    h1 { font-size: 2.5rem !important; }
    h2 { font-size: 2.0rem !important; }
    h3 { font-size: 1.75rem !important; }
    h4 { font-size: 1.5rem !important; }
    
    /* Make buttons and inputs readable */
    .stButton button {
        font-size: 1.2rem !important;
        padding: 0.5rem 1rem !important;
    }
    .stTextInput input, .stNumberInput input {
        font-size: 1.2rem !important;
    }
    .stSelectbox label, .stMultiSelect label, .stCheckbox label {
        font-size: 1.2rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Constants
BASE_DIR = os.getcwd()
XML_DIR = os.path.join(BASE_DIR, "generated_xml")
MESSAGES_DIR = os.path.join(BASE_DIR, "messages")

st.title("Data Studio")

# Tabs
tab_gen, tab_view, tab_edit = st.tabs(["Generate Data", "View Data", "Edit Data"])

# ==============================================================================
# TAB 1: GENERATE DATA
# ==============================================================================
with tab_gen:
    st.header("Generate New Data")
    
    with st.form("generation_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Configuration")
            # Categories (Hardcoded for now based on auto_data.py but ideally dynamic)
            # 3 to 16 based on previous context
            category_options = {
                3: "Category 3 (Time & Latency) - High Priority",
                4: "Category 4 (CPU Cluster) - High Priority",
                5: "Category 5 (Generic HW) - High Priority",
                6: "Category 6 (Complete System) - High Priority",
                7: "Category 7 (Network/AXI) - Medium Priority",
                8: "Category 8 (SWC Types) - Medium Priority",
                9: "Category 9 (Interfaces) - Medium Priority",
                10: "Category 10 (Operations) - Medium Priority",
                11: "Category 11 (Power Params) - Low Priority",
                12: "Category 12 (HW-SW Map) - Low Priority",
                13: "Category 13 (Pre-built App) - Low Priority",
                14: "Category 14 (Chiplet) - Low Priority",
                15: "Category 15 (Analysis) - Low Priority",
                16: "Category 16 (SWC Behavior) - Low Priority"
            }
            
            selected_cats = st.multiselect(
                "Select Categories", 
                options=list(category_options.keys()),
                format_func=lambda x: category_options[x]
            )
            
            num_examples = st.number_input("Examples per Category", min_value=1, value=1, step=1)
            
        with col2:
            st.subheader("Output")
            filename = st.text_input("Output Filename (optional)", value="generated_data.jsonl", help="If provided, appends to this file in current directory")
            
        submitted = st.form_submit_button("Start Generation")
        
        if submitted:
            if not selected_cats:
                st.error("Please select at least one category.")
            else:
                st.info("Starting generation process...")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, cat_id in enumerate(selected_cats):
                    status_text.text(f"Generating Category {cat_id}...")
                    
                    # Construct command
                    cmd = ["python", "Studio_CLI.py", "--category", str(cat_id), "--count", str(num_examples)]
                    if filename:
                         cmd.extend(["--jsonl-file", filename])
                    
                    try:
                        # Run subprocess
                        result = subprocess.run(
                            cmd, 
                            capture_output=True, 
                            text=True, 
                            cwd=BASE_DIR
                        )
                        
                        if result.returncode == 0:
                            st.text(f"Category {cat_id}: Success")
                            with st.expander("Show Log", expanded=False):
                                st.code(result.stdout)
                        else:
                            st.error(f"Category {cat_id}: Failed")
                            st.code(result.stderr)
                            if result.stdout:
                                st.code(result.stdout)
                            
                    except Exception as e:
                        st.error(f"Error executing script: {e}")
                    
                    progress_bar.progress((idx + 1) / len(selected_cats))
                
                status_text.text("Generation Complete!")
                st.success("All tasks finished.")

# ==============================================================================
# TAB 2: VIEW DATA
# ==============================================================================
with tab_view:
    st.header("Data Viewer")
    
    view_mode = st.radio("Select Type", ["Generated XML", "Messages"], horizontal=True)

    if view_mode == "Generated XML":
        if os.path.exists(XML_DIR):
            files = sorted([f for f in os.listdir(XML_DIR) if f.endswith(".xml")])
            if files:
                selected_file = st.selectbox("Select XML File", files)
                if selected_file:
                    file_path = os.path.join(XML_DIR, selected_file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    st.code(content, language="xml")
            else:
                st.warning("No XML files found.")
        else:
            st.error("XML directory not found.")

    elif view_mode == "Messages":
        if os.path.exists(MESSAGES_DIR):
            categories = sorted([d for d in os.listdir(MESSAGES_DIR) if os.path.isdir(os.path.join(MESSAGES_DIR, d))])
            if categories:
                col_cat, col_file = st.columns(2)
                with col_cat:
                    selected_category = st.selectbox("Category", categories)
                
                cat_path = os.path.join(MESSAGES_DIR, selected_category)
                files = sorted([f for f in os.listdir(cat_path) if f.endswith(".jsonl")])
                
                with col_file:
                    if files:
                        selected_file = st.selectbox("File", files)
                    else:
                        st.warning("No files in category.")
                        selected_file = None
                
                if selected_file:
                    file_path = os.path.join(cat_path, selected_file)
                    messages = []
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip():
                                    messages.append(json.loads(line))
                    except Exception as e:
                        st.error(f"Error: {e}")
                    
                    if messages:
                        st.write(f"Found {len(messages)} examples")
                        page = st.number_input("Example Index", min_value=1, max_value=len(messages), value=1) - 1
                        example = messages[page]
                        
                        if "messages" in example:
                            for msg in example["messages"]:
                                role = msg.get("role", "unknown")
                                content = msg.get("content", "")
                                with st.expander(role.upper(), expanded=True):
                                    if role == "assistant" or content.strip().startswith("<"):
                                        st.code(content, language="xml")
                                    else:
                                        st.markdown(content)
                        else:
                            st.json(example)
            else:
                st.warning("No category folders found.")
        else:
            st.error("Messages directory not found.")

# ==============================================================================
# TAB 3: EDIT DATA
# ==============================================================================
with tab_edit:
    st.header("Edit Data Files")
    
    # File Selection
    edit_dir_options = ["Messages Folder", "Root Folder"]
    dir_choice = st.radio("Source Location", edit_dir_options, horizontal=True)
    
    target_files = []
    if dir_choice == "Messages Folder":
        if os.path.exists(MESSAGES_DIR):
            for root, dirs, files in os.walk(MESSAGES_DIR):
                for file in files:
                    if file.endswith(".jsonl"):
                        target_files.append(os.path.join(root, file))
    else:
         target_files = sorted([f for f in os.listdir(BASE_DIR) if f.endswith(".jsonl")])
         target_files = [os.path.join(BASE_DIR, f) for f in target_files]
         
    if target_files:
        selected_edit_file = st.selectbox("Select File to Edit", target_files)
        
        if selected_edit_file:
            st.divider()
            
            # File Operations
            st.subheader("Rename File")
            new_name = st.text_input("New filename", value=os.path.basename(selected_edit_file))
            if st.button("Rename"):
                if new_name != os.path.basename(selected_edit_file):
                    dir_path = os.path.dirname(selected_edit_file)
                    new_path = os.path.join(dir_path, new_name)
                    try:
                        os.rename(selected_edit_file, new_path)
                        st.success(f"Renamed to {new_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            
            st.divider()
            
            # Load and display entries for editing
            entries = []
            try:
                with open(selected_edit_file, "r", encoding="utf-8") as f:
                    for idx, line in enumerate(f):
                        if line.strip():
                            entries.append((idx, json.loads(line)))
            except Exception as e:
                st.error(f"Error loading file: {e}")
                entries = []
            
            if entries:
                st.write(f"**Total Entries:** {len(entries)}")
                
                # === ACTION BUTTONS AT TOP ===
                st.markdown("### Actions")
                col_select_all, col_delete_selected, col_spacer = st.columns([1, 1, 2])
                
                with col_select_all:
                    if st.button("Select All", use_container_width=True, type="primary"):
                        st.session_state['select_all_toggle'] = True
                        st.rerun()
                
                with col_delete_selected:
                    if st.button("Delete Selected", use_container_width=True, type="secondary"):
                        to_delete = [entry[0] for entry in entries if st.session_state.get(f"delete_{entry[0]}", False)]
                        if to_delete:
                            remaining = [entry for entry in entries if entry[0] not in to_delete]
                            try:
                                with open(selected_edit_file, "w", encoding="utf-8") as f:
                                    for _, data in remaining:
                                        f.write(json.dumps(data, ensure_ascii=False) + "\n")
                                st.success(f"Deleted {len(to_delete)} entries")
                                # Clear all checkboxes
                                for key in list(st.session_state.keys()):
                                    if key.startswith("delete_"):
                                        del st.session_state[key]
                                st.session_state['select_all_toggle'] = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                        else:
                            st.warning("No entries selected")
                
                st.divider()
                
                # === ENTRY LISTING ===
                st.markdown("### Entries")
                
                # Handle Select All toggle
                if st.session_state.get('select_all_toggle', False):
                    for entry_idx, _ in entries:
                        st.session_state[f"delete_{entry_idx}"] = True
                    st.session_state['select_all_toggle'] = False
                
                for entry_idx, entry_data in entries:
                    col_check, col_content = st.columns([1, 20])
                    
                    with col_check:
                        # Checkbox for deletion
                        checked = st.checkbox(
                            "Select", 
                            key=f"delete_{entry_idx}",
                            label_visibility="collapsed"
                        )
                    
                    with col_content:
                        with st.expander(f"Entry {entry_idx + 1}", expanded=False):
                            if "messages" in entry_data:
                                for msg in entry_data["messages"]:
                                    role = msg.get("role", "unknown")
                                    content = msg.get("content", "")
                                    st.markdown(f"**{role.upper()}**")
                                    if len(content) > 500:
                                        st.text_area("Content", content, height=200, key=f"msg_{entry_idx}_{role}", disabled=True)
                                    else:
                                        st.code(content[:500] + ("..." if len(content) > 500 else ""))
                            else:
                                st.json(entry_data)
            else:
                st.info("No entries found in this file")
    else:
        st.warning("No .jsonl files found")
