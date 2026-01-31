import streamlit as st
import os
import tempfile
from pathlib import Path
from validators.validation_pipeline import ValidationPipeline

# ==============================================================================
# PAGE CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="XML Validation Pipeline",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# CORPORATE DESIGN (MATCHING CHAT_APP)
# ==============================================================================
def inject_corporate_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@300;400;600;700&display=swap');

    :root {
        --siemens-petrol: #009999;
        --siemens-deep-petrol: #005F5F;
        --bg-deep-slate: #0F1117;
        --bg-sidebar: #171923;
        --text-off-white: #F7FAFC;
        --text-silver: #A0AEC0;
        --glass-border: rgba(0, 153, 153, 0.3);
    }

    /* Global Base */
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Inter', sans-serif;
        background-color: var(--bg-deep-slate) !important;
        color: var(--text-off-white) !important;
    }

    .stApp {
        background-color: var(--bg-deep-slate);
    }

    /* --- SIDEBAR REFINEMENT --- */
    [data-testid="stSidebar"] {
        background-color: var(--bg-sidebar) !important;
        border-right: 1px solid var(--glass-border) !important;
    }

    /* --- HERO TITLE --- */
    .hero-title {
        font-size: 3.5rem !important;
        font-weight: 800 !important;
        color: #009999 !important; /* Solid Siemens Petrol */
        margin-bottom: 25px !important;
    }

    .section-header {
        color: var(--siemens-petrol);
        border-bottom: 2px solid var(--glass-border);
        padding-bottom: 10px;
        margin-top: 20px;
        margin-bottom: 20px;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    /* Status Boxes */
    .status-box {
        padding: 15px;
        border-radius: 10px;
        border: 1px solid var(--glass-border);
        margin-bottom: 10px;
    }

    .status-pass {
        border-left: 5px solid #28a745;
        background: rgba(40, 167, 69, 0.1);
    }

    .status-fail {
        border-left: 5px solid #dc3545;
        background: rgba(220, 53, 69, 0.1);
    }

    /* Hide redundant elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

inject_corporate_styles()

# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown("<h2 style='color: #009999;'>VALIDATION SYSTEM</h2>", unsafe_allow_html=True)
    st.markdown("### Configuration")
    
    check_fs = st.checkbox("Enable filesystem checks", value=True)
    
    st.divider()
    st.markdown("### About")
    st.info("This tool orchestrates the complete AE validation pipeline: XSD, Schematron, and Python logical rules.")

# ==============================================================================
# MAIN CORE
# ==============================================================================
st.markdown("<h1 class='hero-title'>XML Validation Pipeline</h1>", unsafe_allow_html=True)

st.markdown("<div class='section-header'>File Selection</div>", unsafe_allow_html=True)
uploaded_files = st.file_uploader("Choose XML files to validate", type="xml", accept_multiple_files=True)

if uploaded_files:
    if st.button("Start Validation", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        pipeline = ValidationPipeline(check_filesystem=check_fs)
        all_results = {}
        
        with results_container:
            st.markdown("<div class='section-header'>Processing Logs</div>", unsafe_allow_html=True)
            
            for i, uploaded_file in enumerate(uploaded_files):
                filename = uploaded_file.name
                status_text.text(f"Processing: {filename}")
                
                # Save uploaded file to temp path for pipeline
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                try:
                    # Run actual validation
                    vres = pipeline.validate_file(tmp_path)
                    all_results[filename] = vres
                    
                    # Log result
                    if vres.is_valid():
                        st.success(f"PASSED: {filename}")
                    else:
                        st.error(f"FAILED: {filename} ({vres.total_errors()} errors)")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                
                # Update progress
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("Validation phase complete")
            
            # --- FINAL REPORT SECTION ---
            st.markdown("<div class='section-header'>Validation Report Summary</div>", unsafe_allow_html=True)
            
            total_files = len(uploaded_files)
            passed_count = sum(1 for r in all_results.values() if r.is_valid())
            failed_count = total_files - passed_count
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Files", total_files)
            col2.metric("Passed", passed_count)
            col3.metric("Failed", failed_count, delta_color="inverse" if failed_count > 0 else "normal")
            
            # Detailed Breakdown
            st.markdown("<div class='section-header'>Detailed Results</div>", unsafe_allow_html=True)
            
            for name, res in all_results.items():
                is_valid = res.is_valid()
                status_class = "status-pass" if is_valid else "status-fail"
                status_label = "PASSED" if is_valid else f"FAILED ({res.total_errors()} errors)"
                
                with st.expander(f"File: {name} - {status_label}"):
                    st.markdown(f"#### Validation Stages for {name}")
                    
                    # Stage 1: XSD
                    xsd_status = "PASSED" if res.xsd_passed else "FAILED"
                    xsd_color = "green" if res.xsd_passed else "#dc3545"
                    st.markdown(f"**1. XSD Structure Validation:** <span style='color:{xsd_color}; font-weight:bold;'>{xsd_status}</span>", unsafe_allow_html=True)
                    if not res.xsd_passed:
                        for err in res.xsd_errors:
                            st.code(f"Error: {err}", language="text")
                    
                    # Stage 2: Schematron
                    sch_status = "PASSED" if res.schematron_passed else "FAILED"
                    sch_color = "green" if res.schematron_passed else "#dc3545"
                    st.markdown(f"**2. Schematron Rule Validation:** <span style='color:{sch_color}; font-weight:bold;'>{sch_status}</span>", unsafe_allow_html=True)
                    if not res.schematron_passed:
                        for err in res.schematron_errors:
                            st.code(f"Rule Violation: {err}", language="text")
                            
                    # Stage 3: Python Logic
                    py_status = "PASSED" if res.python_passed else "FAILED"
                    py_color = "green" if res.python_passed else "#dc3545"
                    st.markdown(f"**3. Python Logical Validation:** <span style='color:{py_color}; font-weight:bold;'>{py_status}</span>", unsafe_allow_html=True)
                    if not res.python_passed:
                        for err in res.python_errors:
                            st.code(f"Logic Error: {err}", language="text")
            
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()
        st.markdown("<p style='text-align: center; color: #718096; font-size: 0.9rem;'>AE Validation Utility | Graduation Project 2026</p>", unsafe_allow_html=True)
else:
    st.info("Please upload one or more XML files to begin validation.")

# Footer spacing
st.markdown("<br><br><br>", unsafe_allow_html=True)
