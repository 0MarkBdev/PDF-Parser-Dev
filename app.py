import streamlit as st
import pandas as pd
from anthropic import Anthropic
import base64
import json
from typing import Any
import math
from datetime import datetime
import PyPDF2
from io import BytesIO
import tempfile
import fitz  # PyMuPDF for PDF thumbnails and previews

TEMPLATES = {
    "Water Bills": [
        ("Start Date", "YYYY-MM-DD"),
        ("End Date", "YYYY-MM-DD"),
        ("Account Number", ""),
        ("Current Meter Read", ""),
        ("Previous Meter Read", ""),
        ("Total Water Usage", ""),
        ("Water Used Charge", ""),
        ("Water Customer Service Charge", ""),
        ("Sewer Customer Service Charge", ""),
        ("Private Fire Protection Charge", ""),
        ("Federal State Regulatory Compliance Fees", ""),
        ("Total Current Charges", "")
    ],
    "Festus Gas": [
        ("Account Number", ""),
        ("Customer Charge", ""),
        ("Usage Charge", ""),
        ("Pipeline Upgrade Charge", ""),
        ("Delivery Subtotal", ""),
        ("Natural Gas Subtotal", ""),
        ("Sales Tax", ""),
        ("State Tax", ""),
        ("Festus Tax", ""),
        ("Taxes Subtotal", ""),
        ("Subtotal", "")
    ],
    "Custom": [
        ("", ""),  # Empty field 1
        ("", ""),  # Empty field 2
        ("", ""),  # Empty field 3
        ("", ""),  # Empty field 4
        ("", "")   # Empty field 5
    ]
}

# Define the examples for when calculations are included
CALCULATIONS_EXAMPLES = """<examples>
    <example>
        <utility_bill_content>
            Bill Date: 2024-03-15
            Account Number: AC-12345-B

            METER INFORMATION
            Current Read: 68,950
            Previous Read: 65,200
            Total Usage: 3,750 gallons

            WATER CONSUMPTION CHARGES
            Tier 1 (0-1,000 gallons): $2.25
            Tier 2 (1,001-2,000 gallons): $2.75
            Tier 3 (2,001+ gallons): $3.25
            Total Water Charges: $8.25

            FIXED SERVICE FEES
            Base Infrastructure: $8.25
            Technology Fee: $2.50
            Technology Fee: $2.50
            Total Fixed Fees: $13.25

            ELECTRICITY CONSUMPTION CHARGES
            Capacity Charge Maximum Demand Winter: $12.50
            Capacity Charge Maximum Demand Summer: $12.50
            Total Electricity Charges: $25.00

            Total Current Charges: $46.50
        </utility_bill_content>
        <Field_inputted_by_user>
            {
              "Bill Date": "",
              "Account Number": "",
              "Current Meter Reading": "",
              "Previous Meter Reading": "",
              "Total Water Consumption": "",
              "Water Usage Charge": "",
              "Technology Fee": "",
              "Capacity Charge Maximum Demand": "",
              "Reactive Power Charge": "",
              "Total Current Charges": ""
            }
        </Field_inputted_by_user>
        <ideal_output>
            {
              "Bill Date": "2024-03-15",
              "Account Number": "AC-12345-B",
              "Current Meter Reading": 68950,
              "Previous Meter Reading": 65200,
              "Total Water Consumption": 3750,
              "Water Usage Charge": 2.25,
              "Water Usage Charge_2": 2.75,
              "Water Usage Charge_3": 3.25,
              "Water Usage Charge_CalcTotal": 8.25,
              "Technology Fee": 2.50,
              "Technology Fee_2": 2.50,
              "Technology Fee_CalcTotal": 5.00,
              "Capacity Charge Maximum Demand": 12.50,
              "Capacity Charge Maximum Demand_2": 12.50,
              "Capacity Charge Maximum Demand_CalcTotal": 25.00,
              "Reactive Power Charge": null,
              "Total Current Charges": 46.50
            }
        </ideal_output>
    </example>
</examples>"""

# Define examples for when calculations are not included
SIMPLE_EXAMPLES = """<examples>
    <example>
        <utility_bill_content>
            Bill Date: 2024-03-15
            Account Number: AC-12345-B

            METER INFORMATION
            Current Read: 68,950
            Previous Read: 65,200
            Total Usage: 3,750 gallons

            WATER CONSUMPTION CHARGES
            Tier 1 (0-1,000 gallons): $2.25
            Tier 2 (1,001-2,000 gallons): $2.75
            Tier 3 (2,001+ gallons): $3.25
            Total Water Charges: $8.25

            FIXED SERVICE FEES
            Base Infrastructure: $8.25
            Technology Fee: $2.50
            Technology Fee: $2.50
            Total Fixed Fees: $13.25

            ELECTRICITY CONSUMPTION CHARGES
            Capacity Charge Maximum Demand Winter: $12.50
            Capacity Charge Maximum Demand Summer: $12.50
            Total Electricity Charges: $25.00

            Total Current Charges: $46.50
        </utility_bill_content>
        <Field_inputted_by_user>
            {
              "Bill Date": "",
              "Account Number": "",
              "Current Meter Reading": "",
              "Previous Meter Reading": "",
              "Total Water Consumption": "",
              "Water Usage Charge": "",
              "Technology Fee": "",
              "Capacity Charge Maximum Demand": "",
              "Reactive Power Charge": "",
              "Total Current Charges": ""
            }
        </Field_inputted_by_user>
        <ideal_output>
            {
              "Bill Date": "2024-03-15",
              "Account Number": "AC-12345-B",
              "Current Meter Reading": 68950,
              "Previous Meter Reading": 65200,
              "Total Water Consumption": 3750,
              "Water Usage Charge_CalcTotal": 8.25,
              "Technology Fee_CalcTotal": 5.00,
              "Capacity Charge Maximum Demand_CalcTotal": 25.00,
              "Reactive Power Charge": null,
              "Total Current Charges": 46.50
            }
        </ideal_output>
    </example>
</examples>"""

# Add password protection
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Remove password from session state
        else:
            st.session_state["password_correct"] = False

    # First run or after logout
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # Show input if password not yet correct
    if not st.session_state["password_correct"]:
        # Show error if password was incorrect
        if "password" in st.session_state:
            st.error("Incorrect password. Please try again.")

        # Show password input
        st.text_input("Please enter the password",
                      type="password",
                      key="password",
                      on_change=password_entered)
        return False

    return True


def move_field(from_idx: int, to_idx: int):
    """Move a field from one position to another"""
    fields = list(st.session_state.fields)
    fields[from_idx], fields[to_idx] = fields[to_idx], fields[from_idx]
    st.session_state.fields = fields
    st.rerun()


def render_field_controls(i: int):
    """Render the up/down/remove buttons for a field"""
    bcol1, bcol2, bcol3 = st.columns([1, 1, 1])

    with bcol1:
        if i > 0 and st.button("↑", key=f"up_{i}", use_container_width=True):
            move_field(i, i - 1)
    with bcol2:
        if i < len(st.session_state.fields) - 1 and st.button("↓", key=f"down_{i}", use_container_width=True):
            move_field(i, i + 1)
    with bcol3:
        if st.button("✕", key=f"remove_button_{i}", use_container_width=True):
            st.session_state.fields.pop(i)
            st.rerun()


def preview_api_call(uploaded_files, prompt, include_calculations):
    """Generate a preview of the API call that would be sent"""
    # Show preview for first file only since files are processed individually
    if not uploaded_files:
        return "Upload files to see API call preview"
    
    pdf_file = uploaded_files[0]
    
    # Prepare message content for single PDF
    message_content = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": f"[Base64 encoded content of {pdf_file.name}]"  # Placeholder
            }
        },
        {
            "type": "text",
            "text": CALCULATIONS_EXAMPLES if include_calculations else SIMPLE_EXAMPLES
        },
        {
            "type": "text",
            "text": prompt
        }
    ]

    # Construct the full API call preview
    api_call_preview = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 8192,
        "temperature": 0,
        "system": "You are an expert utility bill analyst AI specializing in data extraction and standardization. Your primary responsibilities include:\n\n1. Accurately extracting specific fields from utility bills\n2. Handling complex cases such as tiered charges\n3. Maintaining consistent data formatting\n4. Returning data in a standardized JSON format\n\nYour expertise allows you to navigate complex billing structures, identify relevant information quickly, and standardize data in various utility bill formats. You are meticulous in following instructions and maintaining data integrity throughout the extraction and formatting process.",
        "messages": [
            {
                "role": "user",
                "content": message_content
            }
        ]
    }
    
    return {
        "note": "Preview for first file only. Each file is processed individually.",
        "file_being_previewed": pdf_file.name,
        "api_call": api_call_preview
    }


# Modify the count_tokens function to accept client as a parameter
def count_tokens(client, prompt, include_calculations):
    """Generate a token count for the API call without PDFs"""
    # Prepare message content without PDFs
    message_content = [
        {
            "type": "text",
            "text": CALCULATIONS_EXAMPLES if include_calculations else SIMPLE_EXAMPLES
        },
        {
            "type": "text",
            "text": prompt
        }
    ]
    
    try:
        # Use the client's direct request method
        response = client._client.post(
            "https://api.anthropic.com/v1/messages/count_tokens",
            json={
                "model": "claude-3-5-sonnet-20241022",
                "system": "You are an expert utility bill analyst AI specializing in data extraction and standardization. Your primary responsibilities include:\n\n1. Accurately extracting specific fields from utility bills\n2. Handling complex cases such as tiered charges and multiple instances of the same charge\n3. Maintaining consistent data formatting\n4. Returning data in a standardized JSON format\n\nYour expertise allows you to navigate complex billing structures, identify relevant information quickly, and standardize data in various utility bill formats. You are meticulous in following instructions and maintaining data integrity throughout the extraction and formatting process.",
                "messages": [
                    {
                        "role": "user",
                        "content": message_content
                    }
                ],
                "tools": []  # Include empty tools array as per spec
            },
            headers={
                "x-api-key": st.secrets["ANTHROPIC_API_KEY"],
                "anthropic-beta": "token-counting-2024-11-01",
                "anthropic-version": "2023-06-01"
            }
        )
        
        # Print response for debugging
        print("API Response:", response.text)
        
        result = response.json()
        
        # Return the raw result instead of trying to access input_tokens
        return result
        
    except Exception as e:
        # Wrap any errors with more context
        raise Exception(f"Token counting API error: {str(e)}") from e


def calculate_pdf_tokens(pdf_file) -> int:
    """Estimate token count for a PDF based on file size"""
    pdf_size_kb = len(pdf_file.read()) / 1024  # Convert bytes to KB
    pdf_file.seek(0)  # Reset file pointer
    return math.ceil(pdf_size_kb * 75)  # 75 tokens per KB

def log_api_call(file: Any, response: Any, error: str = None) -> dict:
    """Log an API call and its response"""
    return {
        "timestamp": datetime.now().isoformat(),
        "file_processed": file.name,
        "response": response,
        "error": error
    }

def get_pdf_page_count(pdf_file):
    """Get the number of pages in a PDF file."""
    pdf_file.seek(0)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    page_count = len(pdf_reader.pages)
    pdf_file.seek(0)
    return page_count

def get_page_thumbnail(pdf_file, page_num, zoom_percent=100, is_thumbnail=False):
    """Generate a thumbnail or full-size preview for a PDF page."""
    pdf_file.seek(0)
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
        temp_file.write(pdf_file.read())
        temp_file_path = temp_file.name
    
    doc = fitz.open(temp_file_path)
    page = doc[page_num]
    
    if is_thumbnail:
        # Small thumbnail for initial view
        matrix = fitz.Matrix(0.3, 0.3)
    else:
        # Full-size preview with zoom
        zoom_factor = zoom_percent / 100.0
        # Increased base size for better quality at high zooms
        matrix = fitz.Matrix(3.0 * zoom_factor, 3.0 * zoom_factor)
    
    pix = page.get_pixmap(matrix=matrix)
    img_data = pix.tobytes("png")
    doc.close()
    
    return img_data

def extract_pdf_pages(pdf_file, page_numbers):
    """Extract specific pages from a PDF and return as a new PDF file object."""
    pdf_file.seek(0)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    pdf_writer = PyPDF2.PdfWriter()
    
    for page_num in page_numbers:
        pdf_writer.add_page(pdf_reader.pages[page_num])
    
    output = BytesIO()
    pdf_writer.write(output)
    output.seek(0)
    return output

def get_grid_columns(zoom_percent):
    """Determine number of grid columns based on zoom level."""
    if zoom_percent >= 300:  # Single page view
        return 1
    elif zoom_percent >= 200:  # 2x2 grid
        return 2
    elif zoom_percent >= 150:  # 3x3 grid
        return 3
    elif zoom_percent >= 100:  # 4x4 grid
        return 4
    else:  # 5x5 grid for overview
        return 5

def show_fullscreen_preview(pdf_file, page_count):
    """Show fullscreen preview with page selection and grouping."""
    st.markdown("""
        <style>
        .stButton button {
            width: 100%;
            border-radius: 4px;
            padding: 0.5rem;
        }
        .zoom-controls .stButton button {
            font-size: 20px;
            font-weight: bold;
        }
        .page-controls {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Header and navigation
    st.markdown("## PDF Management")
    if st.button("← Back to Overview"):
        st.session_state.current_pdf = None
        st.rerun()
    
    # Zoom controls with cleaner layout
    st.markdown("### Preview Controls")
    with st.container():
        col1, col2, col3 = st.columns([1, 8, 1])
        with col1:
            st.markdown('<div class="zoom-controls">', unsafe_allow_html=True)
            if st.button("-"):
                st.session_state.zoom_level = max(25, st.session_state.zoom_level - 25)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.slider("", 25, 400, st.session_state.zoom_level, 25, 
                     key=f"zoom_slider_{pdf_file.name}",
                     on_change=lambda: setattr(st.session_state, 'zoom_level', 
                                             st.session_state[f"zoom_slider_{pdf_file.name}"]))
        with col3:
            st.markdown('<div class="zoom-controls">', unsafe_allow_html=True)
            if st.button("+"):
                st.session_state.zoom_level = min(400, st.session_state.zoom_level + 25)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Page grid
    cols_per_row = get_grid_columns(st.session_state.zoom_level)
    
    # Initialize selected pages if needed
    if f"{pdf_file.name}_selected_pages" not in st.session_state:
        st.session_state[f"{pdf_file.name}_selected_pages"] = set()
    
    st.markdown("### Page Selection")
    # Display pages in grid
    for i in range(0, page_count, cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            page_idx = i + j
            if page_idx < page_count:
                with col:
                    with st.container():
                        # Page preview
                        preview = get_page_thumbnail(pdf_file, page_idx, st.session_state.zoom_level)
                        st.image(preview, use_column_width=True)
                        
                        # Page controls below image
                        select_col1, select_col2 = st.columns([2, 1])
                        with select_col1:
                            st.write(f"Page {page_idx + 1}")
                        with select_col2:
                            is_selected = st.checkbox("Select", 
                                                    value=page_idx in st.session_state[f"{pdf_file.name}_selected_pages"],
                                                    key=f"select_{pdf_file.name}_{page_idx}",
                                                    label_visibility="collapsed")
                        
                        # Update selection state
                        if is_selected:
                            st.session_state[f"{pdf_file.name}_selected_pages"].add(page_idx)
                        else:
                            st.session_state[f"{pdf_file.name}_selected_pages"].discard(page_idx)
    
    # Group management section
    st.markdown("### Group Management")
    
    # Create group interface
    create_col1, create_col2 = st.columns([3, 1])
    with create_col1:
        group_name = st.text_input("Group Name (optional)", key=f"group_name_{pdf_file.name}")
    with create_col2:
        if st.button("Create Group", key=f"create_group_{pdf_file.name}", type="primary"):
            selected_pages = sorted(list(st.session_state[f"{pdf_file.name}_selected_pages"]))
            if selected_pages:
                if pdf_file.name not in st.session_state.pdf_groups:
                    st.session_state.pdf_groups[pdf_file.name] = []
                group = {
                    "name": group_name or f"Group {len(st.session_state.pdf_groups[pdf_file.name]) + 1}",
                    "pages": selected_pages
                }
                st.session_state.pdf_groups[pdf_file.name].append(group)
                st.session_state[f"{pdf_file.name}_selected_pages"] = set()
                st.success(f"Group '{group['name']}' created with {len(selected_pages)} pages")
            else:
                st.warning("Please select at least one page to create a group")
    
    # Show existing groups
    if st.session_state.pdf_groups.get(pdf_file.name):
        st.markdown("#### Existing Groups")
        for i, group in enumerate(st.session_state.pdf_groups[pdf_file.name]):
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{group['name']}**: Pages {[p+1 for p in group['pages']]}")
                with col2:
                    if st.button("Delete", key=f"delete_group_{pdf_file.name}_{i}"):
                        st.session_state.pdf_groups[pdf_file.name].pop(i)
                        st.rerun()

def split_pdf_page():
    """Dedicated page for PDF splitting."""
    st.markdown("## PDF Splitting")
    st.write("Create smaller PDFs from larger documents before processing.")
    
    # File upload with full width
    uploaded_file = st.file_uploader("Upload PDF to Split", type=['pdf'], key="split_pdf_uploader")
    
    if uploaded_file:
        # Get page count
        page_count = get_pdf_page_count(uploaded_file)
        st.write(f"Total pages: {page_count}")
        
        # Preview section with full width
        preview_col1, preview_col2 = st.columns([1, 5])  # Even more space for preview
        with preview_col1:
            preview_page = st.number_input("Preview page", min_value=1, max_value=page_count, value=1) - 1
        with preview_col2:
            preview = get_page_thumbnail(uploaded_file, preview_page, 100, True)
            st.image(preview, use_column_width=True)
        
        # Split options with better spacing
        st.markdown("### Create New PDF")
        split_col1, split_col2, split_col3, split_col4 = st.columns([2, 2, 2, 6])
        with split_col1:
            start_page = st.number_input("Start Page", min_value=1, max_value=page_count, value=1)
        with split_col2:
            end_page = st.number_input("End Page", min_value=start_page, max_value=page_count, value=min(start_page, page_count))
        with split_col3:
            if st.button("Create PDF", type="primary"):
                # Create new PDF
                new_pdf = extract_pdf_pages(uploaded_file, range(start_page-1, end_page))
                
                # Add to session state for main page
                if 'split_pdfs' not in st.session_state:
                    st.session_state.split_pdfs = []
                
                # Generate unique name
                new_name = f"Split_{start_page}-{end_page}_{uploaded_file.name}"
                st.session_state.split_pdfs.append({
                    'name': new_name,
                    'content': new_pdf
                })
                st.success(f"Created PDF with pages {start_page}-{end_page}")
        
        # Show created PDFs in a cleaner layout
        if hasattr(st.session_state, 'split_pdfs') and st.session_state.split_pdfs:
            st.markdown("### Created PDFs")
            for pdf in st.session_state.split_pdfs:
                with st.container():
                    pdf_col1, pdf_col2 = st.columns([6, 1])
                    with pdf_col1:
                        st.write(f"📄 {pdf['name']}")
                    with pdf_col2:
                        if st.button("Delete", key=f"delete_split_{pdf['name']}"):
                            st.session_state.split_pdfs.remove(pdf)
                            st.rerun()

def process_pdfs_with_groups(uploaded_files, client, prompt, include_calculations):
    """Process PDFs considering page groups."""
    individual_results = []
    st.session_state.api_logs = []
    status_container = st.empty()
    
    total_units = sum(1 if get_pdf_page_count(f) == 1 or f.name not in st.session_state.pdf_groups
                     else len(st.session_state.pdf_groups[f.name])
                     for f in uploaded_files)
    
    current_unit = 0
    
    for pdf_file in uploaded_files:
        page_count = get_pdf_page_count(pdf_file)
        
        if page_count == 1 or pdf_file.name not in st.session_state.pdf_groups:
            # Process single-page PDF or ungrouped multi-page PDF as one unit
            current_unit += 1
            status_container.info(f"Processing unit {current_unit} of {total_units}")
            
            result = process_single_pdf(pdf_file, client, prompt, include_calculations)
            if result:
                individual_results.append(result)
        else:
            # Process each group as a separate unit
            for group in st.session_state.pdf_groups[pdf_file.name]:
                current_unit += 1
                status_container.info(f"Processing unit {current_unit} of {total_units}: {group['name']}")
                
                # Extract pages for this group
                group_pdf = extract_pdf_pages(pdf_file, group['pages'])
                result = process_single_pdf(group_pdf, client, prompt, include_calculations, 
                                         filename=f"{pdf_file.name} - {group['name']}")
                if result:
                    individual_results.append(result)
    
    status_container.success(f"Successfully processed {current_unit} units!")
    return individual_results

def process_single_pdf(pdf_file, client, prompt, include_calculations, filename=None):
    """Process a single PDF unit (either a single-page PDF or a group of pages)."""
    try:
        message_content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.b64encode(pdf_file.read() if isinstance(pdf_file, BytesIO) 
                                          else pdf_file.getvalue()).decode()
                }
            },
            {
                "type": "text",
                "text": CALCULATIONS_EXAMPLES if include_calculations else SIMPLE_EXAMPLES
            },
            {
                "type": "text",
                "text": prompt
            }
        ]
        
        if isinstance(pdf_file, BytesIO):
            pdf_file.seek(0)
        else:
            pdf_file.seek(0)
        
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            temperature=0,
            system="You are an expert utility bill analyst AI specializing in data extraction and standardization...",
            messages=[{"role": "user", "content": message_content}]
        )
        
        response_data = json.loads(message.content[0].text)
        if isinstance(response_data, dict):
            response_data['filename'] = filename or pdf_file.name
            return response_data
        elif response_data.get('bills') and len(response_data['bills']) > 0:
            bill_dict = dict(zip(response_data['fields'], response_data['bills'][0]))
            bill_dict['filename'] = filename or pdf_file.name
            return bill_dict
        
        st.session_state.api_logs.append(
            log_api_call(pdf_file, {
                "parsed_response": response_data,
                "raw_response": message.model_dump(),
                "file_processed": filename or pdf_file.name,
                "num_bills_returned": 1 if isinstance(response_data, dict) else len(response_data.get("bills", [])),
                "fields_returned": list(response_data.keys()) if isinstance(response_data, dict) else response_data.get("fields", [])
            })
        )
        
        return None
        
    except Exception as e:
        st.session_state.api_logs.append(
            log_api_call(pdf_file, None, str(e))
        )
        st.error(f"Error processing {filename or pdf_file.name}: {str(e)}")
        return None

def initialize_session_state():
    """Initialize session state variables for PDF handling."""
    if 'pdf_groups' not in st.session_state:
        st.session_state.pdf_groups = {}  # {pdf_name: [{name: str, pages: list[int]}]}
    if 'current_pdf' not in st.session_state:
        st.session_state.current_pdf = None
    if 'zoom_level' not in st.session_state:
        st.session_state.zoom_level = 100

def manage_pdf_groups(uploaded_files):
    """Manage PDF groups in the UI with fullscreen preview."""
    groups_changed = False
    
    # Initialize session state
    if 'zoom_level' not in st.session_state:
        st.session_state.zoom_level = 100
    if 'current_pdf' not in st.session_state:
        st.session_state.current_pdf = None
    
    # Show fullscreen view if a PDF is selected
    if st.session_state.current_pdf:
        current_pdf = next((pdf for pdf in uploaded_files 
                          if pdf.name == st.session_state.current_pdf), None)
        if current_pdf:
            show_fullscreen_preview(current_pdf, get_pdf_page_count(current_pdf))
            return groups_changed
    
    # Show PDF overview
    for pdf_file in uploaded_files:
        if pdf_file.name not in st.session_state.pdf_groups:
            st.session_state.pdf_groups[pdf_file.name] = []
            groups_changed = True
        
        st.write(f"### {pdf_file.name}")
        
        page_count = get_pdf_page_count(pdf_file)
        
        if page_count == 1:
            st.info("Single-page PDF - will be processed as one bill")
            preview = get_page_thumbnail(pdf_file, 0, 100, True)
            st.image(preview, width=300)
            continue
        
        # Show compact preview and fullscreen button
        col1, col2 = st.columns([1, 3])
        with col1:
            preview = get_page_thumbnail(pdf_file, 0, 100, True)
            st.image(preview, use_column_width=True)
        with col2:
            st.write(f"Total Pages: {page_count}")
            if st.button("📄 Open Fullscreen", key=f"fullscreen_{pdf_file.name}", type="primary"):
                st.session_state.current_pdf = pdf_file.name
                st.rerun()
        
        # Show existing groups
        if st.session_state.pdf_groups[pdf_file.name]:
            st.markdown("#### Existing Groups")
            for i, group in enumerate(st.session_state.pdf_groups[pdf_file.name]):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{group['name']}**: Pages {[p+1 for p in group['pages']]}")
                with col2:
                    if st.button("Delete", key=f"delete_group_{pdf_file.name}_{i}"):
                        st.session_state.pdf_groups[pdf_file.name].pop(i)
                        groups_changed = True
                        st.rerun()
        
        st.markdown("---")
    
    return groups_changed

# Main app
def main():
    # Get API key from secrets
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    # Initialize session state
    initialize_session_state()

    # Create tabs with unique keys
    tabs = st.tabs(["Main", "Split PDFs", "Debug Info"])
    
    # Add tab index to session state
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = 0
        
    # Main tab
    with tabs[0]:
        st.session_state.active_tab = 0
        st.title('Bill Parser')
        # ... rest of main tab code ...

    # Split PDFs tab
    with tabs[1]:
        st.session_state.active_tab = 1
        # Inject CSS only for Split PDFs tab
        st.markdown("""
            <style>
            /* Target only the Split PDFs tab content */
            [data-testid="stTabsContent"] > div:nth-of-type(2) .block-container {
                max-width: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
            }

            [data-testid="stTabsContent"] > div:nth-of-type(2) div[data-testid="stVerticalBlock"] {
                padding-left: 0 !important;
                padding-right: 0 !important;
                gap: 0 !important;
            }

            [data-testid="stTabsContent"] > div:nth-of-type(2) div.element-container,
            [data-testid="stTabsContent"] > div:nth-of-type(2) div.row-widget,
            [data-testid="stTabsContent"] > div:nth-of-type(2) div.stMarkdown,
            [data-testid="stTabsContent"] > div:nth-of-type(2) div.stImage,
            [data-testid="stTabsContent"] > div:nth-of-type(2) div.stButton,
            [data-testid="stTabsContent"] > div:nth-of-type(2) div.stNumberInput {
                width: 100% !important;
                max-width: none !important;
                padding: 0 1rem !important;
            }

            [data-testid="stTabsContent"] > div:nth-of-type(2) .stImage > img {
                width: 100% !important;
                max-width: none !important;
            }

            [data-testid="stTabsContent"] > div:nth-of-type(2) .css-1d391kg,
            [data-testid="stTabsContent"] > div:nth-of-type(2) .css-1a1fmpi,
            [data-testid="stTabsContent"] > div:nth-of-type(2) .css-keje6w {
                width: 100% !important;
                max-width: none !important;
            }
            </style>
        """, unsafe_allow_html=True)
        split_pdf_page()

    # Debug tab
    with tabs[2]:
        st.session_state.active_tab = 2
        # ... rest of debug tab code ...
        pass


def split_pdf_page():
    """Dedicated page for PDF splitting."""
    st.markdown("## PDF Splitting")
    st.write("Create smaller PDFs from larger documents before processing.")
    
    # File upload with full width
    uploaded_file = st.file_uploader("Upload PDF to Split", type=['pdf'], key="split_pdf_uploader")
    
    if uploaded_file:
        # Get page count
        page_count = get_pdf_page_count(uploaded_file)
        st.write(f"Total pages: {page_count}")
        
        # Preview section with full width
        preview_col1, preview_col2 = st.columns([1, 5])  # Even more space for preview
        with preview_col1:
            preview_page = st.number_input("Preview page", min_value=1, max_value=page_count, value=1) - 1
        with preview_col2:
            preview = get_page_thumbnail(uploaded_file, preview_page, 100, True)
            st.image(preview, use_column_width=True)
        
        # Split options with better spacing
        st.markdown("### Create New PDF")
        split_col1, split_col2, split_col3, split_col4 = st.columns([2, 2, 2, 6])
        with split_col1:
            start_page = st.number_input("Start Page", min_value=1, max_value=page_count, value=1)
        with split_col2:
            end_page = st.number_input("End Page", min_value=start_page, max_value=page_count, value=min(start_page, page_count))
        with split_col3:
            if st.button("Create PDF", type="primary"):
                # Create new PDF
                new_pdf = extract_pdf_pages(uploaded_file, range(start_page-1, end_page))
                
                # Add to session state for main page
                if 'split_pdfs' not in st.session_state:
                    st.session_state.split_pdfs = []
                
                # Generate unique name
                new_name = f"Split_{start_page}-{end_page}_{uploaded_file.name}"
                st.session_state.split_pdfs.append({
                    'name': new_name,
                    'content': new_pdf
                })
                st.success(f"Created PDF with pages {start_page}-{end_page}")
        
        # Show created PDFs in a cleaner layout
        if hasattr(st.session_state, 'split_pdfs') and st.session_state.split_pdfs:
            st.markdown("### Created PDFs")
            for pdf in st.session_state.split_pdfs:
                with st.container():
                    pdf_col1, pdf_col2 = st.columns([6, 1])
                    with pdf_col1:
                        st.write(f"📄 {pdf['name']}")
                    with pdf_col2:
                        if st.button("Delete", key=f"delete_split_{pdf['name']}"):
                            st.session_state.split_pdfs.remove(pdf)
                            st.rerun()

# Run the app with password protection
# Run the app with password protection
if check_password():
    main()