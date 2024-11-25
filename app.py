import streamlit as st
import pandas as pd
from anthropic import Anthropic
import base64
import json
from typing import List, Dict
import math

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
            CLEARWATER UTILITIES
            123 River Road, Springville, TX 75001

            Customer: Sarah Rodriguez
            Account Number: 1234567890-01
            Service Address: 456 Lakeside Ave, Springville, TX 75001
            Billing Period: 06/20/2023 to 07/19/2023
            Statement Date: 07/20/2023
            Due Date: 08/10/2023

            METER INFORMATION
            Current Read (07/19/2023 14:30 CST): 68,950
            Previous Read (06/20/2023 14:15 CST): 65,200
            Total Usage: 3,750 gallons

            WATER CONSUMPTION CHARGES
            Tier 1 (Essential Use): 0-1,000 gallons @ $2.25/1,000 gal
                Usage: 1,000 gallons = $2.25
            Tier 2 (Standard Use): 1,001-2,000 gallons @ $2.75/1,000 gal
                Usage: 1,000 gallons = $2.75
            Tier 3 (Enhanced Use): 2,001-3,000 gallons @ $3.25/1,000 gal
                Usage: 1,000 gallons = $3.25
            Tier 4 (Peak Use): 3,001-3,750 gallons @ $3.75/1,000 gal
                Usage: 750 gallons = $2.81

            FIXED SERVICE FEES
            Base Infrastructure Maintenance: $8.25
            Smart Meter Technology Fee: $2.50
            System Reliability Charge: $3.75
            Emergency Response Readiness: $1.75
            Total Fixed Service Fees: $16.25

            SEWER SERVICE
            Peak Season Adjustment: June 20-30
                Subtotal June: $8.25
            Standard Season: July 1-19
                Subtotal July: $12.50

            WATER QUALITY ASSURANCE
            Basic Testing: $1.25
            Enhanced Monitoring: $0.75
            Compliance Reporting: $0.50
            Subtotal: $2.50

            STORM WATER MANAGEMENT
            Base Fee: $2.00
            Impervious Surface Charge: $1.25
            Watershed Protection: $0.75

            REGIONAL AUTHORITY CHARGES
            Water Rights Assessment: $0.50
            Infrastructure Cost Share: $0.45
            Drought Management: $0.30
            Conservation Programs: $0.25
            Total Regional Charges: $1.50

            Previous Balance: $55.75
            Payment Received: -$55.75
            Current Charges: $55.81
            Total Amount Due: $56.25
        </utility_bill_content>
        <Field_inputted_by_user>
            {
              "Bill Date": "",
              "Billing Period Start": "",
              "Billing Period End": "",
              "Account Number": "",
              "Current Meter Reading": "",
              "Previous Meter Reading": "",
              "Total Water Consumption": "",
              "Water Usage Charge": "",
              "Fixed Service Fee": "",
              "Sewer Service": "",
              "Water Quality Assurance Fee": "",
              "Storm Water Management": "",
              "Regional Water Authority Charge": "",
              "Total Current Charges": ""
            }
        </Field_inputted_by_user>
        <ideal_output>
            {
              "fields": [
                "Bill Date",
                "Billing Period Start",
                "Billing Period End",
                "Account Number",
                "Current Meter Reading",
                "Previous Meter Reading",
                "Total Water Consumption",
                "Water Usage Charge",
                "Water Usage Charge_2",
                "Water Usage Charge_3",
                "Water Usage Charge_4",
                "Water Usage Charge_CalcTotal",
                "Fixed Service Fee",
                "Fixed Service Fee_2",
                "Fixed Service Fee_3",
                "Fixed Service Fee_4",
                "Fixed Service Fee_Total",
                "Sewer Service",
                "Sewer Service_2",
                "Sewer Service_CalcTotal",
                "Water Quality Assurance Fee",
                "Water Quality Assurance Fee_2",
                "Water Quality Assurance Fee_3",
                "Water Quality Assurance Fee_Total",
                "Storm Water Management",
                "Storm Water Management_2",
                "Storm Water Management_3",
                "Storm Water Management_CalcTotal",
                "Regional Water Authority Charge",
                "Regional Water Authority Charge_2",
                "Regional Water Authority Charge_3",
                "Regional Water Authority Charge_4",
                "Regional Water Authority Charge_Total",
                "Total Current Charges"
              ],
              "bills": [
                [
                  "07/20/2023",
                  "06/20/2023",
                  "07/19/2023",
                  "1234567890-01",
                  68950,
                  65200,
                  3750,
                  2.25,
                  2.75,
                  3.25,
                  2.81,
                  11.06,
                  8.25,
                  2.50,
                  3.75,
                  1.75,
                  16.25,
                  8.25,
                  12.50,
                  20.75,
                  1.25,
                  0.75,
                  0.50,
                  2.50,
                  2.00,
                  1.25,
                  0.75,
                  4.00,
                  0.50,
                  0.45,
                  0.30,
                  0.25,
                  1.50,
                  55.81
                ]
              ]
            }
        </ideal_output>
    </example>
</examples>"""

# Define examples for when calculations are not included
SIMPLE_EXAMPLES = """<examples>
    <example>
        <utility_bill_content>
            CLEARWATER UTILITIES
            123 River Road, Springville, TX 75001

            Customer: Sarah Rodriguez
            Account Number: 1234567890-01
            Service Address: 456 Lakeside Ave, Springville, TX 75001
            Billing Period: 06/20/2023 to 07/19/2023
            Statement Date: 07/20/2023
            Due Date: 08/10/2023

            METER INFORMATION
            Current Read (07/19/2023 14:30 CST): 68,950
            Previous Read (06/20/2023 14:15 CST): 65,200
            Total Usage: 3,750 gallons

            WATER CONSUMPTION CHARGES
            Tier 1 (Essential Use): 0-1,000 gallons @ $2.25/1,000 gal
                Usage: 1,000 gallons = $2.25
            Tier 2 (Standard Use): 1,001-2,000 gallons @ $2.75/1,000 gal
                Usage: 1,000 gallons = $2.75
            Tier 3 (Enhanced Use): 2,001-3,000 gallons @ $3.25/1,000 gal
                Usage: 1,000 gallons = $3.25
            Tier 4 (Peak Use): 3,001-3,750 gallons @ $3.75/1,000 gal
                Usage: 750 gallons = $2.81

            FIXED SERVICE FEES
            Base Infrastructure Maintenance: $8.25
            Smart Meter Technology Fee: $2.50
            System Reliability Charge: $3.75
            Emergency Response Readiness: $1.75
            Total Fixed Service Fees: $16.25

            SEWER SERVICE
            Peak Season Adjustment: June 20-30
                Subtotal June: $8.25
            Standard Season: July 1-19
                Subtotal July: $12.50

            WATER QUALITY ASSURANCE
            Basic Testing: $1.25
            Enhanced Monitoring: $0.75
            Compliance Reporting: $0.50
            Subtotal: $2.50

            STORM WATER MANAGEMENT
            Base Fee: $2.00
            Impervious Surface Charge: $1.25
            Watershed Protection: $0.75

            REGIONAL AUTHORITY CHARGES
            Water Rights Assessment: $0.50
            Infrastructure Cost Share: $0.45
            Drought Management: $0.30
            Conservation Programs: $0.25
            Total Regional Charges: $1.50

            Previous Balance: $55.75
            Payment Received: -$55.75
            Current Charges: $55.81
            Total Amount Due: $56.25
        </utility_bill_content>
        <Field_inputted_by_user>
            {
              "Bill Date": "",
              "Billing Period Start": "",
              "Billing Period End": "",
              "Account Number": "",
              "Current Meter Reading": "",
              "Previous Meter Reading": "",
              "Total Water Consumption": "",
              "Water Usage Charge": "",
              "Fixed Service Fee": "",
              "Sewer Service": "",
              "Water Quality Assurance Fee": "",
              "Storm Water Management": "",
              "Regional Water Authority Charge": "",
              "Total Current Charges": ""
            }
        </Field_inputted_by_user>
        <ideal_output>
            {
              "fields": [
                "Bill Date",
                "Billing Period Start",
                "Billing Period End",
                "Account Number",
                "Current Meter Reading",
                "Previous Meter Reading",
                "Total Water Consumption",
                "Water Usage Charge_CalcTotal",
                "Fixed Service Fee_Total",
                "Sewer Service_CalcTotal",
                "Water Quality Assurance Fee_Total",
                "Storm Water Management_CalcTotal",
                "Regional Water Authority Charge_Total",
                "Total Current Charges"
              ],
              "bills": [
                [
                  "07/20/2023",
                  "06/20/2023",
                  "07/19/2023",
                  "1234567890-01",
                  68950,
                  65200,
                  3750,
                  11.06,
                  16.25,
                  20.75,
                  2.50,
                  4.00,
                  1.50,
                  55.81
                ]
              ]
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
    message_content = []
    
    # Add each PDF document placeholder (showing exact structure)
    for pdf in uploaded_files:
        message_content.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": f"[Base64 encoded content of {pdf.name}]"  # Placeholder
            }
        })

    # Add the examples and prompt - exactly as in the real call
    message_content.extend([
        {
            "type": "text",
            "text": CALCULATIONS_EXAMPLES if include_calculations else SIMPLE_EXAMPLES
        },
        {
            "type": "text",
            "text": prompt
        }
    ])

    # Construct the full API call preview - matching exactly the real call
    api_call_preview = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 8192,  # Fixed token limit
        "temperature": 0,
        "system": "You are an expert utility bill analyst AI specializing in data extraction and standardization. Your primary responsibilities include:\n\n1. Processing multiple utility bills simultaneously while keeping each bill's data separate and organized.\n2. Accurately extracting specific fields from each bill.\n3. Handling complex cases such as tiered charges.\n4. Maintaining consistent formatting across all extracted data.\n5. Returning data as a JSON array where each bill is represented as a separate object.\n\nYour expertise allows you to navigate complex billing structures, identify relevant information quickly, and standardize data across various utility bill formats. You are meticulous in following instructions and maintaining data integrity throughout the extraction and formatting process.",
        "messages": [
            {
                "role": "user",
                "content": message_content
            }
        ],
        "default_headers": {  # Include the custom headers
            "anthropic-beta": "pdfs-2024-09-25"
        }
    }
    
    return api_call_preview


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
                "system": "You are a utility bill analysis expert focused on precise data extraction and standardization. You excel at processing multiple bills simultaneously, handling complex tiered charges, and maintaining consistent data formatting. Your primary goal is to extract specified fields and return properly structured JSON data while maintaining strict data integrity.",
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
    return math.ceil(pdf_size_kb * 60)  # 60 tokens per KB

def batch_pdfs(uploaded_files, token_limit=40000) -> List[List]:
    """
    Group PDFs into batches that stay under the token limit.
    Returns list of lists, where each inner list contains PDFs for one batch.
    """
    batches = []
    current_batch = []
    current_batch_tokens = 0
    
    # Calculate base tokens from examples and system message (approximate)
    base_tokens = 3000  # Adjust this based on actual usage
    
    for pdf in uploaded_files:
        pdf_tokens = calculate_pdf_tokens(pdf)
        
        # If adding this PDF would exceed limit, start new batch
        if current_batch_tokens + pdf_tokens + base_tokens > token_limit:
            if current_batch:  # Only append if batch has files
                batches.append(current_batch)
            current_batch = [pdf]
            current_batch_tokens = pdf_tokens
        else:
            current_batch.append(pdf)
            current_batch_tokens += pdf_tokens
    
    # Add final batch if not empty
    if current_batch:
        batches.append(current_batch)
    
    return batches

def merge_responses(responses: List[Dict]) -> Dict:
    """
    Merge multiple API responses into a single consistent format,
    handling different column structures.
    """
    # Collect all unique fields across all responses
    all_fields = set()
    for response in responses:
        all_fields.update(response['fields'])
    
    # Sort fields to maintain consistent order
    # Keep base fields first, then numbered variations
    def field_sort_key(field):
        # Split field into base name and suffix
        parts = field.split('_')
        base = parts[0]
        suffix = parts[1] if len(parts) > 1 else ''
        # Sort by base name first, then suffix
        return (base, suffix)
    
    sorted_fields = sorted(all_fields, key=field_sort_key)
    
    # Merge all bills data
    merged_bills = []
    for response in responses:
        field_map = {f: i for i, f in enumerate(response['fields'])}
        
        for bill_values in response['bills']:
            # Create a dict with all fields set to null
            merged_bill = [None] * len(sorted_fields)
            
            # Fill in the values we have
            for new_idx, field in enumerate(sorted_fields):
                if field in field_map:
                    orig_idx = field_map[field]
                    if orig_idx < len(bill_values):
                        merged_bill[new_idx] = bill_values[orig_idx]
            
            merged_bills.append(merged_bill)
    
    return {
        'fields': sorted_fields,
        'bills': merged_bills
    }

# Main app
def main():
    # Get API key from secrets
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    # Create tabs for main content and debug info
    main_tab, debug_tab = st.tabs(["Main", "Debug Info"])

    with main_tab:
        # Create the interface
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
        include_calculations = st.checkbox("Include charge calculations and breakdowns", value=False)

        st.write("Enter the fields you want to extract:")

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
       a. Use the plain field name for the first charge (e.g., "FIELD")
       b. Add a suffix for each additional charge (e.g., "FIELD_2", "FIELD_3")
       c. If there is a total value stated, use it and add a '_Total' suffix for the total (e.g., "FIELD_Total")
       d. If there isn't a clearly stated total, calculate and create one with the sum of the tiers. You MUST add a "CalcTotal" suffix to indicate it was calculated. (e.g., "FIELD_CalcTotal").""" if include_calculations else """
       a. If there is a total value stated, use it and add a '_Total' suffix for the total (e.g., "FIELD_Total")
       b. If there isn't a clearly stated total, calculate and create one with the sum of the tiers. You MUST add a "CalcTotal" suffix to indicate it was calculated. (e.g., "FIELD_CalcTotal")."""

        prompt = f"""Your objective is to extract key information from utility bills and present it in a standardized nested JSON format. Follow these steps:

1. Carefully analyze each utility bill content separately.
2. Identify and extract the required fields for each bill.
3. Format the extracted information according to the specifications.
4. Handle any tiered charges appropriately.
5. Compile the final JSON output in a nested format.

Required Fields for each bill:
[${list(field_dict.keys())[0]}, ${list(field_dict.keys())[1]}, ${list(field_dict.keys())[2]}, ...]

Special Instructions:
1. For charges that show a tiered calculation breakdown (like water service charges):{tiered_calculation_instructions}

2. Formatting Rules:
   - Use a nested format with "fields" and "bills" as main keys
   - Place field definitions once in the "fields" array
   - Place each bill's data in the "bills" array
   - Return each amount as a plain number
   - Do not include gallons, rates, or date ranges

3. If a field is not found in the bill, use null as the value.

Return the data in this structure:
{{
    "fields": [Field1, Field2, ...],  // Field names in order
    "bills": [
        [null, null, ...],  // Bill 1 values in same order as fields
        [null, null, ...],  // Bill 2 values
        // ... one array per bill ...
    ]
}}

Remember to replace the null values with the actual extracted data or keep as null if the information is not found in the bill.

Provide ONLY the JSON object as your final output, with no additional text."""

        # Add file uploader
        uploaded_files = st.file_uploader("Upload PDF Bills", type=['pdf'], accept_multiple_files=True)

        # Process Bills button logic
        if st.button('Process Bills'):
            if uploaded_files:
                status_container = st.empty()
                status_container.info("Processing files...")

                try:
                    # Create the client with custom headers
                    pdf_client = Anthropic(
                        api_key=st.secrets["ANTHROPIC_API_KEY"],
                        default_headers={"anthropic-beta": "pdfs-2024-09-25"}
                    )

                    # Replace the existing PDF processing code with this:
                    batches = batch_pdfs(uploaded_files)
                    all_responses = []
                    
                    # Process each batch
                    for i, batch in enumerate(batches):
                        status_container.info(f"Processing batch {i+1} of {len(batches)}...")
                        
                        # Prepare message content for this batch
                        message_content = []
                        
                        # Add PDFs for this batch
                        for pdf in batch:
                            message_content.append({
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": base64.b64encode(pdf.read()).decode()
                                }
                            })
                            pdf.seek(0)  # Reset file pointer
                        
                        # Add examples and prompt
                        message_content.extend([
                            {
                                "type": "text",
                                "text": CALCULATIONS_EXAMPLES if include_calculations else SIMPLE_EXAMPLES
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ])

                        # Send to Claude API
                        message = pdf_client.messages.create(
                            model="claude-3-5-sonnet-20241022",
                            max_tokens=8192,
                            temperature=0,
                            system="You are a utility bill analysis expert focused on precise data extraction and standardization. You excel at processing multiple bills simultaneously, handling complex tiered charges, and maintaining consistent data formatting. Your primary goal is to extract specified fields and return properly structured JSON data while maintaining strict data integrity.",
                            messages=[
                                {
                                    "role": "user",
                                    "content": message_content
                                }
                            ]
                        )

                        # Parse response and add to responses list
                        response_data = json.loads(message.content[0].text)
                        all_responses.append(response_data)

                    # Merge all responses
                    merged_response = merge_responses(all_responses)
                    
                    # Convert merged response to DataFrame format
                    all_results = []
                    for bill_values, pdf in zip(merged_response['bills'], uploaded_files):
                        bill_dict = dict(zip(merged_response['fields'], bill_values))
                        bill_dict['filename'] = pdf.name
                        all_results.append(bill_dict)

                    # Create DataFrame and store in session state
                    df = pd.DataFrame(all_results)
                    columns = ['filename'] + [col for col in df.columns if col != 'filename']
                    df = df[columns]
                    st.session_state.results_df = df
                    
                    status_container.success(f"Successfully processed {len(uploaded_files)} file{'s' if len(uploaded_files) > 1 else ''}!")

                except Exception as e:
                    status_container.error(f"Error processing files: {str(e)}")

        # Debug tab content
        with debug_tab:
            # Create sections using expanders
            with st.expander("📤 API Call Preview", expanded=True):
                st.write("Preview the API call that will be sent when processing files")
                
                if uploaded_files:
                    col1, col2 = st.columns([1, 1])
                    
                    # Create buttons side by side but keep display area unified
                    preview_clicked = col1.button("Generate API Call Preview")
                    count_tokens_clicked = col2.button("Preview Api Call & Count Tokens")
                    
                    if preview_clicked or count_tokens_clicked:
                        # If token counting was requested, show it first
                        if count_tokens_clicked:
                            try:
                                token_count = count_tokens(client, prompt, include_calculations)
                                st.success("Token Count Results:")
                                # Print the full response for debugging
                                print("Token count response:", token_count)
                                st.json(token_count)  # Show the full response
                                st.info("Note: This count excludes PDF content as it's not yet supported by the token counting API")
                            except Exception as e:
                                st.error(f"Error counting tokens: {str(e)}")
                                st.error("Please check the API documentation or try again later.")
                            
                            # Add a visual separator
                            st.markdown("---")
                        
                        # Show the API preview (same for both buttons)
                        preview = preview_api_call(uploaded_files, prompt, include_calculations)
                        st.session_state.api_preview = preview
                        st.json(preview)
                else:
                    st.info("Upload files in the main tab to preview the API call")
            
            with st.expander("📊 Last API Call Statistics", expanded=False):
                if hasattr(st.session_state, 'last_usage'):
                    st.write("Last API Call Statistics:")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Input Tokens", st.session_state.last_usage['input_tokens'])
                    with col2:
                        st.metric("Output Tokens", st.session_state.last_usage['output_tokens'])
                    
                    # Add stop reason explanation
                    stop_reason = st.session_state.last_usage['stop_reason']
                    explanation = {
                        "end_turn": "The model completed its response naturally.",
                        "max_tokens": "The response was cut off due to reaching the token limit.",
                        "stop_sequence": "The model stopped at a designated stop sequence.",
                        "error": "The response was terminated due to an error."
                    }.get(stop_reason, f"Unknown stop reason: {stop_reason}")
                    
                    st.write("**Stop Reason:**")
                    st.info(explanation)
                else:
                    st.write("No API calls made yet.")
            
            with st.expander("📝 Raw JSON Response", expanded=False):
                if hasattr(st.session_state, 'raw_json_response'):
                    st.write("Raw JSON Response from last API call:")
                    st.code(st.session_state.raw_json_response, language='json')
                else:
                    st.write("No API response data available yet.")

    # Move Excel creation and download button outside the Process Bills button block
    if hasattr(st.session_state, 'results_df'):
        # Create Excel file
        excel_buffer = pd.ExcelWriter('results.xlsx', engine='openpyxl')
        st.session_state.results_df.to_excel(excel_buffer, index=False, sheet_name='Extracted Data')

        # Auto-adjust column widths
        worksheet = excel_buffer.sheets['Extracted Data']
        for idx, col in enumerate(st.session_state.results_df.columns):
            max_length = max(
                st.session_state.results_df[col].astype(str).apply(len).max(),
                len(str(col))
            )
            worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2

        excel_buffer.close()

        # Add download button
        with open('results.xlsx', 'rb') as f:
            st.download_button(
                'Download Results',
                f,
                'results.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        # Display the results in the app
        st.write("### Extracted Data")
        st.dataframe(st.session_state.results_df)


# Run the app with password protection
# Run the app with password protection
if check_password():
    main()