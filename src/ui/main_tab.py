"""Main tab UI component for the PDF Parser application."""

import os
import io
import json
import pandas as pd
import streamlit as st
from anthropic import Anthropic

from src.config.templates import TEMPLATES
from src.config.examples import CALCULATIONS_EXAMPLES, SIMPLE_EXAMPLES
from src.pdf.parser import process_pdf_files

def render_main_tab():
    """Render the main bill parsing tab."""
    st.title('Bill Parser')

    # Template selection
    template_name = st.selectbox(
        "Select Template",
        options=list(TEMPLATES.keys()),
        key="template_selector"
    )

    # Initialize fields based on template
    if 'fields' not in st.session_state or 'current_template' not in st.session_state:
        st.session_state.fields = TEMPLATES[template_name]
        st.session_state.current_template = template_name
    elif st.session_state.current_template != template_name:
        st.session_state.fields = TEMPLATES[template_name]
        st.session_state.current_template = template_name
        st.rerun()

    # Add checkbox here
    col1, col2 = st.columns([3, 2])
    with col1:
        include_calculations = st.checkbox("Include charge calculations and breakdowns", value=False)
    
    col3, col4 = st.columns([1, 2])
    with col3:
        specify_meter = st.checkbox("Specify Meter/Account:", value=False)
    with col4:
        meter_number = st.text_input("", label_visibility="collapsed", disabled=not specify_meter)

    st.write("Enter the fields to be extracted:")

    # Display existing fields
    new_fields = []

    for i, (field, format_hint) in enumerate(st.session_state.fields):
        # Use container to enforce consistent spacing
        container = st.container()

        # Create columns with exact proportions - making buttons narrower
        col1, col2, col3 = container.columns([6, 1.5, 1.2])

        # Main fields in first two columns
        with col1:
            new_field = st.text_input(f"Field {i + 1}", value=field, key=f"field_input_{i}",
                                      label_visibility="collapsed")
        with col2:
            new_format = st.text_input("Format", value=format_hint, key=f"format_input_{i}",
                                       label_visibility="collapsed")

        # Buttons in last column, with fixed small width
        with col3:
            btn_container = st.container()
            # Force buttons to align by using a single line
            c1, c2, c3 = btn_container.columns(3)
            with c1:
                if i > 0 and st.button("↑", key=f"up_{i}", use_container_width=True):
                    fields = list(st.session_state.fields)
                    fields[i], fields[i - 1] = fields[i - 1], fields[i]
                    st.session_state.fields = fields
                    st.rerun()
            with c2:
                if i < len(st.session_state.fields) - 1 and st.button("↓", key=f"down_{i}", use_container_width=True):
                    fields = list(st.session_state.fields)
                    fields[i], fields[i + 1] = fields[i + 1], fields[i]
                    st.session_state.fields = fields
                    st.rerun()
            with c3:
                if st.button("✕", key=f"remove_button_{i}", use_container_width=True):
                    st.session_state.fields.pop(i)
                    st.rerun()

        new_fields.append((new_field, new_format))

    # Update session state with new field values
    st.session_state.fields = new_fields

    # Add new field button
    if st.button("Add Field"):
        st.session_state.fields.append(("", ""))
        st.rerun()

    # Create the prompt string based on fields
    field_dict = {field: "" for field, _ in st.session_state.fields if field}

    tiered_calculation_instructions = """
   a. Use the plain field name for the first tiers/instances/charges (e.g., "FIELD")
   b. Add a suffix for each additional tiers/instances/charges (e.g., "FIELD_2", "FIELD_3")
   c. If there is a total value stated, use it and add a '_Total' suffix for the total (e.g., "FIELD_Total")
   d. If there isn't a clearly stated total, calculate and create one with the sum of the tiers/instances/charges. You MUST add a "CalcTotal" suffix to indicate it was calculated. (e.g., "FIELD_CalcTotal").""" if include_calculations else """
   a. If there is a total value stated, use it and add a '_Total' suffix for the total (e.g., "FIELD_Total")
   b. If there isn't a clearly stated total, calculate and create one with the sum of the tiers/instances/charges. You MUST add a "CalcTotal" suffix to indicate it was calculated. (e.g., "FIELD_CalcTotal")."""

    prompt = f"""Your objective is to extract key information from this utility bill and present it in a standardized JSON format. Follow these steps:

1. Carefully analyze the utility bill content.
2. Identify and extract the required fields.
3. Format the extracted information according to the specifications.
4. Handle any tiered charges appropriately.
5. Compile the final JSON output.

Required Fields{f" to be extracted only for {meter_number}" if specify_meter and meter_number else ""}:
{json.dumps(field_dict, indent=2)}

Special Instructions:
1. For charges that show multiple charges with the main part of the name identical but with seasonal suffixes (e.g., "Charge A Summer", "Charge A Winter"), or tiered charges (like water service charges), or multiple instances of the same charge (when a rate changes in the middle of the bill period), or any other case where the same charge is shown multiple times with different values, use the following instructions:{tiered_calculation_instructions}

2. Formatting Rules:
   - Each field should be a separate key at the root level of the JSON
   - Do not nest the values in sub-objects
   - Return each amount as a plain number
   - Do not include gallons, rates, or date ranges

3. If a field is not found in the bill, use null as the value.

Return the data in this structure (while adding the proper suffixes for different tiers/instances/charges and totals):
{json.dumps(field_dict, indent=2)}

Remember to replace the null values with the actual extracted data or keep as null if the information is not found in the bill.

Provide ONLY the JSON object as your final output, with no additional text."""

    # File upload area
    uploaded_files = st.file_uploader("Upload PDF Bills", type=['pdf'], accept_multiple_files=True)
    
    # Prepare split PDFs for processing
    split_files_to_process = []
    for split_pdf in list(st.session_state.split_pdfs_to_parse):  # Use list() to avoid modification during iteration
        try:
            file_path = os.path.join(os.getcwd(), split_pdf)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    split_files_to_process.append(("split_pdf", split_pdf, f.read()))
            else:
                # File doesn't exist anymore, remove it from the list
                st.session_state.split_pdfs_to_parse.remove(split_pdf)
                st.warning(f"File {split_pdf} no longer exists and has been removed from processing queue.")
        except Exception as e:
            st.error(f"Error loading split PDF {split_pdf}: {str(e)}")
            st.session_state.split_pdfs_to_parse.remove(split_pdf)
            continue

    # Show split PDFs that will be processed
    if split_files_to_process:
        st.write("Split PDFs to be processed:")
        for _, name, _ in split_files_to_process:
            col1, col2 = st.columns([6, 1])
            with col1:
                st.write(f"- {name}")
            with col2:
                if st.button("Remove", key=f"remove_from_parser_{name}"):
                    st.session_state.split_pdfs_to_parse.remove(name)
                    st.rerun()

    # Process Bills button
    if st.button('Process Bills'):
        if uploaded_files or split_files_to_process:
            status_container = st.empty()
            status_container.info("Processing files...")

            try:
                # Process the files
                df = process_pdf_files(uploaded_files, split_files_to_process, prompt, include_calculations)
                
                if df is not None:
                    status_container.success(f"Successfully processed {len(df)} file{'s' if len(df) > 1 else ''}!")
                    st.session_state.results_df = df
                else:
                    status_container.error("No data was successfully extracted from the files.")

            except Exception as e:
                status_container.error(f"Error initializing PDF processing: {str(e)}")
        else:
            st.warning("Please upload files or select split PDFs to process.")

    # Display results if available
    if hasattr(st.session_state, 'results_df'):
        # Get the original field order from session state
        original_fields = [field for field, _ in st.session_state.fields if field]
        
        # Group and sort columns by base names while preserving original field order
        def get_base_name(col):
            # Skip filename column
            if col == 'filename':
                return '000_filename'  # Changed to ensure filename is always first
            # Split on underscore and get base name
            parts = col.split('_')
            base = '_'.join(parts[:-1]) if len(parts) > 1 else col
            # Get the original position of the base field
            try:
                original_pos = original_fields.index(base)
            except ValueError:
                # If base not in original fields, put it at the end
                original_pos = len(original_fields)
            return f"{original_pos + 1:03d}_{base}"  # Added +1 to make room for filename

        def get_suffix_priority(col):
            # Define priority for suffixes (no suffix = 0, _2 = 1, _CalcTotal = 2, etc)
            if col == 'filename':
                return -1  # Ensure filename stays first
            if '_' not in col:
                return 0
            suffix = col.split('_')[-1]
            priorities = {
                '2': 1,
                '3': 2,
                '4': 3,
                'Total': 98,
                'CalcTotal': 99
            }
            return priorities.get(suffix, 50)  # Default priority for unknown suffixes

        # Sort columns first by original field order (via base name), then by suffix priority
        columns = st.session_state.results_df.columns.tolist()
        sorted_columns = sorted(
            columns,
            key=lambda x: (get_base_name(x), get_suffix_priority(x))
        )

        # Reorder the DataFrame columns
        df_sorted = st.session_state.results_df[sorted_columns]
        
        # Create Excel file with sorted columns
        excel_buffer = pd.ExcelWriter('results.xlsx', engine='openpyxl')
        df_sorted.to_excel(excel_buffer, index=False, sheet_name='Extracted Data')

        # Auto-adjust column widths more safely
        worksheet = excel_buffer.sheets['Extracted Data']
        for idx, col in enumerate(df_sorted.columns):
            # Get max length of column data and column header
            max_length = max(
                df_sorted[col].astype(str).apply(len).max(),
                len(str(col))
            )
            # Limit column width to a reasonable maximum (e.g., 50 characters)
            adjusted_width = min(max_length + 2, 50)
            # Convert numeric index to Excel column letter
            col_letter = chr(65 + (idx % 26))
            if idx >= 26:
                col_letter = chr(64 + (idx // 26)) + col_letter
            worksheet.column_dimensions[col_letter].width = adjusted_width

        excel_buffer.close()

        # Add download button
        with open('results.xlsx', 'rb') as f:
            st.download_button(
                'Download Results',
                f,
                'results.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        # Display the results in the app with sorted columns
        st.write("### Extracted Data")
        st.dataframe(df_sorted) 