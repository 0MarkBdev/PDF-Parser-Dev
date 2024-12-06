"""Split tab UI component for the PDF Parser application."""

import os
import streamlit as st
from src.pdf.splitter import split_pdf, validate_page_ranges, get_pdf_page_count

def render_split_tab():
    """Render the PDF splitting tab."""
    st.title("PDF Splitting")
    st.markdown("Split your PDF documents into smaller PDFs by selecting page ranges.")

    # Add custom styling
    st.markdown("""
        <style>
        .stButton > button {
            width: 100%;
        }
        .group-header {
            font-size: 1.2em;
            font-weight: 600;
            margin-bottom: 0.5em;
            color: #333;
        }
        .group-container {
            background-color: #f8f9fa;
            padding: 1em;
            border-radius: 0.5em;
            margin: 0.5em 0;
            border: 1px solid #e9ecef;
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize session state
    if 'page_ranges_groups' not in st.session_state:
        st.session_state.page_ranges_groups = [
            {"name": "Group 1", "ranges": [("", "")]}
        ]
    if 'created_pdfs' not in st.session_state:
        st.session_state.created_pdfs = []
    if 'current_pdf' not in st.session_state:
        st.session_state.current_pdf = None
    if 'page_count' not in st.session_state:
        st.session_state.page_count = 0
    if 'split_pdfs_to_parse' not in st.session_state:
        st.session_state.split_pdfs_to_parse = []

    # File upload area
    uploaded_pdf = st.file_uploader("Upload PDF", type=['pdf'], key="pdf_splitter")

    if uploaded_pdf:
        # Update page count if new PDF uploaded
        if st.session_state.current_pdf != uploaded_pdf.name:
            st.session_state.page_count = get_pdf_page_count(uploaded_pdf)
            st.session_state.current_pdf = uploaded_pdf.name

        # Display total page count
        st.write(f"Total pages: {st.session_state.page_count}")

        # Add "New Group" button at the top
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("➕ New Group", use_container_width=True):
                group_num = len(st.session_state.page_ranges_groups) + 1
                st.session_state.page_ranges_groups.append({
                    "name": f"Group {group_num}",
                    "ranges": [("", "")]
                })
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)  # Add spacing

        # Add dark mode compatible styling
        st.markdown("""
            <style>
            div[data-testid="stExpander"] {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(250, 250, 250, 0.1);
                border-radius: 0.5em;
                margin: 0.5em 0;
            }
            [data-testid="stAppViewContainer"] [data-testid="stExpander"] {
                background-color: rgba(255, 255, 255, 0.05);
            }
            [data-testid="stAppViewContainer"] [data-testid="stExpander"] > div[role="button"] {
                color: rgb(250, 250, 250);
            }
            [data-testid="stAppViewContainer"] [data-testid="stExpander"] > div[role="button"]:hover {
                color: rgb(180, 180, 180);
            }
            </style>
        """, unsafe_allow_html=True)

        try:
            # Process each group
            for group_idx, group in enumerate(st.session_state.page_ranges_groups):
                with st.expander(group['name'], expanded=True):
                    # Allow editing group name
                    new_name = st.text_input("Group Name", 
                                           value=group['name'], 
                                           key=f"group_name_{group_idx}")
                    group['name'] = new_name

                    st.write("Enter page ranges:")
                    
                    # Display existing ranges for this group
                    new_ranges = []
                    for i, (start, end) in enumerate(group['ranges']):
                        col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
                        
                        with col1:
                            new_start = st.text_input("Start Page", 
                                                    value=start, 
                                                    key=f"start_range_{group_idx}_{i}", 
                                                    placeholder="e.g., 1")
                        with col2:
                            new_end = st.text_input("End Page", 
                                                  value=end, 
                                                  key=f"end_range_{group_idx}_{i}", 
                                                  placeholder=f"e.g., {st.session_state.page_count}")
                            
                            # Add new group if this is the last range in the last group
                            if (group_idx == len(st.session_state.page_ranges_groups) - 1 and 
                                i == len(group['ranges']) - 1 and 
                                new_start.strip() and new_end.strip()):
                                group_num = len(st.session_state.page_ranges_groups) + 1
                                st.session_state.page_ranges_groups.append({
                                    "name": f"Group {group_num}",
                                    "ranges": [("", "")]
                                })
                                st.rerun()
                        
                        with col3:
                            if st.button("✕", key=f"remove_range_btn_{group_idx}_{i}"):
                                continue
                        with col4:
                            if i > 0 and st.button("↑", key=f"move_up_range_btn_{group_idx}_{i}"):
                                if i > 0:
                                    new_ranges[-1], (new_start, new_end) = (new_start, new_end), new_ranges[-1]
                        
                        new_ranges.append((new_start, new_end))

                    # Update group ranges
                    group['ranges'] = new_ranges

                    # Add new range button
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        if st.button("➕ Add Page Range", key=f"add_range_btn_{group_idx}", use_container_width=True):
                            group['ranges'].append(("", ""))
                            st.rerun()

                    # Delete group button
                    if len(st.session_state.page_ranges_groups) > 1:
                        st.markdown("<br>", unsafe_allow_html=True)
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col2:
                            if st.button("🗑️ Delete Group", key=f"delete_group_{group_idx}", use_container_width=True):
                                st.session_state.page_ranges_groups.pop(group_idx)
                                st.rerun()

        except Exception as e:
            st.error(f"Error processing groups: {str(e)}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Create PDFs button
        button_label = "Create PDFs" if len(st.session_state.page_ranges_groups) > 1 else "Create PDF"
        if st.button(button_label, key="create_pdf_btn", 
                    use_container_width=True,
                    disabled=not any(any(start and end for start, end in group['ranges']) 
                                   for group in st.session_state.page_ranges_groups)):
            valid_ranges_by_group = []
            error_messages = []

            # Validate ranges for each group
            for group in st.session_state.page_ranges_groups:
                valid_ranges, errors = validate_page_ranges(
                    [r for r in group['ranges'] if r[0] and r[1]],  # Only process filled ranges
                    st.session_state.page_count
                )
                if valid_ranges:
                    valid_ranges_by_group.append((group['name'], valid_ranges))
                error_messages.extend(f"{error} in {group['name']}" for error in errors)

            if error_messages:
                for msg in error_messages:
                    st.error(msg)
            else:
                try:
                    # Create new PDFs
                    created_files = split_pdf(uploaded_pdf, valid_ranges_by_group)
                    
                    # Update session state
                    for filename in created_files:
                        if filename not in st.session_state.created_pdfs:
                            st.session_state.created_pdfs.append(filename)
                        else:
                            st.error(f"A file named '{filename}' already exists. Please use a different group name or page ranges.")
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating PDFs: {str(e)}")

    # Display created PDFs
    if st.session_state.created_pdfs:
        st.markdown("---")
        st.subheader("Created PDFs")
        
        for pdf_name in st.session_state.created_pdfs:
            col1, col2, col3 = st.columns([6, 2, 2])
            with col1:
                st.write(pdf_name)
            with col2:
                if st.button("Delete", key=f"del_{pdf_name}"):
                    try:
                        # Only delete file if not in split_pdfs_to_parse
                        if pdf_name not in st.session_state.split_pdfs_to_parse:
                            os.remove(os.path.join(os.getcwd(), pdf_name))
                        st.session_state.created_pdfs.remove(pdf_name)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting file: {str(e)}")
            with col3:
                if pdf_name in st.session_state.split_pdfs_to_parse:
                    st.write("✓ Sent to parser")
                else:
                    if st.button("Send to Parser", key=f"parse_{pdf_name}"):
                        st.session_state.split_pdfs_to_parse.append(pdf_name)
                        st.rerun() 