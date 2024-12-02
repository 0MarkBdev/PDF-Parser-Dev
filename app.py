"""Main entry point for the PDF Parser application."""

import streamlit as st
from anthropic import Anthropic

from src.auth.password import check_password
from src.ui.main_tab import render_main_tab
from src.ui.split_tab import render_split_tab
from src.ui.debug_tab import render_debug_tab

def main():
    """Main application entry point."""
    # Get API key from secrets
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    # Create tabs based on admin status
    if st.session_state.get("is_admin", False):
        main_tab, split_tab, debug_tab = st.tabs(["Main", "PDF Splitting", "Debug Info"])
    else:
        main_tab, split_tab = st.tabs(["Main", "PDF Splitting"])

    # Render each tab
    with split_tab:
        render_split_tab()

    with main_tab:
        render_main_tab()

    # Render debug tab if admin
    if st.session_state.get("is_admin", False):
        with debug_tab:
            # Get prompt and include_calculations from main tab
            prompt = st.session_state.get('prompt', '')
            include_calculations = st.session_state.get('include_calculations', False)
            uploaded_files = st.session_state.get('uploaded_files', [])
            
            render_debug_tab(uploaded_files, prompt, include_calculations, client)

# Run the app with password protection
if check_password():
    main()