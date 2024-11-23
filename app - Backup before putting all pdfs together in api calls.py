import streamlit as st
import pandas as pd
from anthropic import Anthropic
import base64
import json

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


# Main app
def main():
    # Get API key from secrets
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

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

    prompt = f"""Your objective is to extract key information from this utility bill and present it in a standardized JSON format. Follow these steps:

1. Carefully analyze the utility bill content.
2. Identify and extract the required fields.
3. Format the extracted information according to the specifications.
4. Handle any tiered charges appropriately.
5. Compile the final JSON output.

Required Fields:
{json.dumps(field_dict, indent=2)}

Special Instructions:
1. For charges that show a tiered calculation breakdown (like water service charges):{tiered_calculation_instructions}

2. Formatting Rules:
   - Each field should be a separate key at the root level of the JSON
   - Do not nest the values in sub-objects
   - Return each amount as a plain number
   - Do not include gallons, rates, or date ranges

3. If a field is not found in the bill, use null as the value.

Before providing the final JSON output double-check that all extracted values are correctly formatted.

After your extraction process, provide the final JSON output. The JSON should follow this structure:
{json.dumps(field_dict, indent=2)}

Remember to replace the empty strings and null values with the actual extracted data or leave as null if the information is not found in the bill.

Provide ONLY the JSON object as your final output, with no additional text."""

    # Add file uploader
    uploaded_files = st.file_uploader("Upload PDF Bills", type=['pdf'], accept_multiple_files=True)

    # Define the examples for when calculations are included
    calculations_examples = """<examples>
    <example>
        <utility_bill_content>
            CLEARWATER UTILITIES
            789 River Road, Springville, USA 67890

            Customer: Sarah Johnson
            Account Number: 9876543210
            Service Address: 321 Pine Street, Springville, USA 67890

            Bill Date: 08/20/2023
            Due Date: 09/10/2023

            Billing Period: 07/20/2023 to 08/19/2023

            Meter Readings:
            Current Read (08/19/2023): 73,450
            Previous Read (07/20/2023): 67,800
            Total Usage: 5,650 gallons

            Charges:
            Water Service Charge:
              0-2,000 gallons @ $3.00 per 1,000 gallons: $6.00
              2,001-5,000 gallons @ $3.50 per 1,000 gallons: $10.50
              5,001-5,650 gallons @ $4.00 per 1,000 gallons: $2.60
              Total Water Service Charge: $19.10

            Water Infrastructure Surcharge: $7.50
            Wastewater Treatment Charge: $22.00
            Storm Water Management Fee: $5.00
            Environmental Compliance Fee: $1.75

            Total Current Charges: $55.35

            Previous Balance: $55.35
            Payments Received: $55.35

            Total Amount Due: $55.35

            To avoid service interruption, please pay by the due date.
            For billing inquiries, contact us at 1-888-555-6789.
        </utility_bill_content>
        <Field_inputted_by_user>
            {
              "Start Date": "",
              "End Date": "",
              "Account Number": "",
              "Current Meter Read": "",
              "Previous Meter Read": "",
              "Total Water Usage": "",
              "Water Service Charge": "",
              "Water Infrastructure Surcharge": "",
              "Wastewater Treatment Charge": "",
              "Storm Water Management Fee": "",
              "Environmental Compliance Fee": "",
              "Total Current Charges": ""
            }
        </Field_inputted_by_user>
        <ideal_output>
            {
              "Start Date": "07/20/2023",
              "End Date": "08/19/2023",
              "Account Number": "9876543210",
              "Current Meter Read": 73450,
              "Previous Meter Read": 67800,
              "Total Water Usage": 5650,
              "Water Service Charge": 6.00,
              "Water Service Charge_2": 10.50,
              "Water Service Charge_3": 2.60,
              "Water Service Charge_Total": 19.10,
              "Water Infrastructure Surcharge": 7.50,
              "Wastewater Treatment Charge": 22.00,
              "Storm Water Management Fee": 5.00,
              "Environmental Compliance Fee": 1.75,
              "Total Current Charges": 55.35
            }
        </ideal_output>
    </example>
    <example>
        <utility_bill_content>
            GREENLEAF WATER SERVICES
            456 Elm Avenue, Riverside, CA 90210

            Customer: Emily Thompson
            Account Number: 5678901234
            Service Address: 789 Maple Drive, Riverside, CA 90210

            Bill Date: 09/10/2023
            Due Date: 09/30/2023

            Billing Period: 08/10/2023 to 09/09/2023

            Meter Readings:
            Current Read (09/09/2023): 82,640
            Previous Read (08/10/2023): 77,320
            Total Usage: 5,320 gallons

            Charges:
            Water Consumption Charge:
              0-2,500 gallons @ $2.75 per 1,000 gallons: $6.88
              2,501-5,000 gallons @ $3.25 per 1,000 gallons: $8.13
              5,001-5,320 gallons @ $3.75 per 1,000 gallons: $1.20
              Total Water Consumption Charge: $16.21

            Basic Service Charge:   
            08/10 - 08/18       $18.50
            08/18 - 09/09         $10

            Wastewater Collection Fee:    08/10 - 08/18   $12.50
                                        08/18 - 09/09  $12.50
            Water Quality Improvement Surcharge: $3.75
            Drought Management Fee: $2.00
            State Water Resource Fee: $1.50

            Total Current Charges: $66.96

            Previous Balance: $66.96
            Payments Received: $66.96

            Total Amount Due: $66.96

            To conserve water and reduce your bill, visit www.greenleafwater.com/conservation for tips.
            For account inquiries, please call 1-877-555-4321 or email support@greenleafwater.com.
        </utility_bill_content>
        <Field_inputted_by_user>
            {
              "Start Date": "",
              "End Date": "",
              "Account Number": "",
              "Current Meter Read": "",
              "Previous Meter Read": "",
              "Total Water Usage": "",
              "Water Consumption Charge": "",
              "Basic Service Charge": "",
              "Wastewater Collection Fee": "",
              "Water Quality Improvement Surcharge": "",
              "Drought Management Fee": "",
              "State Water Resource Fee": "",
              "Total Current Charges": ""
            }
        </Field_inputted_by_user>
        <ideal_output>
            {
              "Start Date": "08/10/2023",
              "End Date": "09/09/2023",
              "Account Number": "5678901234",
              "Current Meter Read": 82640,
              "Previous Meter Read": 77320,
              "Total Water Usage": 5320,
              "Water Consumption Charge": 6.88,
              "Water Consumption Charge_2": 8.13,
              "Water Consumption Charge_3": 1.20,
              "Water Consumption Charge_Total": 16.21,
              "Basic Service Charge": 18.50,
              "Basic Service Charge_2": 10.00,
              "Basic Service Charge_CalcTotal": 28.50,
              "Wastewater Collection Fee": 12.50,
              "Wastewater Collection Fee_2": 12.50,
              "Wastewater Collection Fee_CalcTotal": 25.00,
              "Water Quality Improvement Surcharge": 3.75,
              "Drought Management Fee": 2.00,
              "State Water Resource Fee": 1.50,
              "Total Current Charges": 66.96
            }
        </ideal_output>
    </example>
    <example>
        <utility_bill_content>
            CLEARWATER UTILITIES
            123 River Road, Springville, TX 75001
            www.clearwaterutilities.com

            DETAILED UTILITY STATEMENT
            Customer: Sarah Rodriguez
            Account Number: 1234567890-01
            Service Address: 456 Lakeside Ave, Springville, TX 75001
            Billing Period: 06/20/2023 to 07/19/2023
            Statement Date: 07/20/2023
            Due Date: 08/10/2023

            METER INFORMATION
            Meter ID: WM-458792
            Current Read (07/19/2023 14:30 CST): 68,950
            Previous Read (06/20/2023 14:15 CST): 65,200
            Total Usage: 3,750 gallons
            Average Daily Usage: 125 gallons
            Peak Usage Date: 07/03/2023 (180 gallons)

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

            SEWER SERVICE (Time-of-Use Rates)
            Peak Season Adjustment: June 20-30
                Base Rate: $6.00
                Peak Loading Factor (1.25x): $1.50
                Infrastructure Recovery: $0.75
                Subtotal June: $8.25

            Standard Season: July 1-19
                Base Rate: $9.00
                Volume-Based Processing: $2.25
                Treatment Surcharge: $1.25
                Subtotal July: $12.50

            ENVIRONMENTAL AND REGULATORY FEES
            Water Quality Assurance:
                Basic Testing: $1.25
                Enhanced Monitoring: $0.75
                Compliance Reporting: $0.50
                Subtotal: $2.50

            Storm Water Management:
                Base Fee: $2.00
                Impervious Surface Charge (1,200 sq ft): $1.25
                Watershed Protection: $0.75

            REGIONAL AUTHORITY CHARGES
            Water Rights Assessment: $0.50
            Infrastructure Cost Share: $0.45
            Drought Management: $0.30
            Conservation Programs: $0.25
            Total Regional Charges: $1.50

            SEASONAL ADJUSTMENTS
            Summer Peak Usage Surcharge (June 20-30): $0.75
            Holiday Weekend Rate Adjustment (July 4): $0.25

            CONSERVATION INCENTIVES
            Smart Irrigation Discount: -$1.25
            Low-Flow Fixture Credit: -$0.75
            Total Conservation Credits: -$2.00

            ACCOUNT SUMMARY
            Previous Balance: $55.75
            Payment Received - Thank You (07/05/2023): -$55.75
            Current Charges: $55.81
            Emergency Services Fee*: $0.44
            Total Amount Due: $56.25

            *Emergency Services Fee breakdown:
                911 Water Services: $0.19
                Critical Infrastructure: $0.15
                Emergency Response: $0.10

            Payment is due by 08/10/2023. A 1.5% late fee ($0.84) will be 
            assessed on any unpaid balance after this date.

            USAGE COMPARISON
            Current Month Average Daily Usage: 125 gal
            Previous Month Average: 115 gal
            Same Month Last Year: 132 gal
            Neighborhood Average: 128 gal

            IMPORTANT NOTICES
            - Peak summer rates in effect from June 15 - September 15
            - Smart Meter upgrades scheduled for your area in August 2023
            - Water quality report available at: clearwaterutilities.com/quality
            - Sign up for paperless billing to receive a $1.00 monthly credit

            Conservation Tip: Installing a smart irrigation controller can 
            reduce outdoor water usage by up to 15%

            Customer Support:
            Phone: 1-888-987-6543
            Email: support@clearwaterutilities.com
            Emergency: 1-888-987-6544
            Online Portal: my.clearwaterutilities.com

            Payment Options:
            - Online: clearwaterutilities.com/pay
            - Phone: 1-888-PAY-BILL
            - Mail: PO Box 45678, Springville, TX 75002
            - In-Person: 123 River Road (M-F, 8:00-5:00)

            Account Notice: Your usage triggered our leak detection system 
            on 07/03/2023. Please check for possible leaks or unintended 
            water usage.
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
              "Bill Date": "07/20/2023",
              "Billing Period Start": "06/20/2023",
              "Billing Period End": "07/19/2023",
              "Account Number": "1234567890-01",
              "Current Meter Reading": 68950,
              "Previous Meter Reading": 65200,
              "Total Water Consumption": 3750,
              "Water Usage Charge": 2.25,
              "Water Usage Charge_2": 2.75,
              "Water Usage Charge_3": 3.25,
              "Water Usage Charge_4": 2.81,
              "Water Usage Charge_CalcTotal": 11.06,
              "Fixed Service Fee": 8.25,
              "Fixed Service Fee_2": 2.50,
              "Fixed Service Fee_3": 3.75,
              "Fixed Service Fee_4": 1.75,
              "Fixed Service Fee_Total": 16.25,
              "Sewer Service": 8.25,
              "Sewer Service_2": 12.50,
              "Sewer Service_CalcTotal": 20.75,
              "Water Quality Assurance Fee": 1.25,
              "Water Quality Assurance Fee_2": 0.75,
              "Water Quality Assurance Fee_3": 0.50,
              "Water Quality Assurance Fee_Total": 2.50,
              "Storm Water Management": 2.00,
              "Storm Water Management_2": 1.25,
              "Storm Water Management_3": 0.75,
              "Storm Water Management_CalcTotal": 4.00,
              "Regional Water Authority Charge": 0.50,
              "Regional Water Authority Charge_2": 0.45,
              "Regional Water Authority Charge_3": 0.30,
              "Regional Water Authority Charge_4": 0.25,
              "Regional Water Authority Charge_Total": 1.50,
              "Total Current Charges": 55.81
            }
        </ideal_output>
    </example>
</examples>"""

    # Define examples for when calculations are not included
    simple_examples = """<examples>
    <example>
    <utility_bill_content>
    # Add your simple example here
    </utility_bill_content>
    <Field_inputted_by_user>
    # Add corresponding input fields
    </Field_inputted_by_user>
    <ideal_output>
    # Add simple JSON output
    </ideal_output>
    </example>
    </examples>
    """

    # Add this near the start of main() function
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = None

    # Process Bills button logic
    if st.button('Process Bills'):
        if uploaded_files:
            all_results = []
            progress_bar = st.progress(0)
            status_container = st.empty()

            for idx, pdf in enumerate(uploaded_files):
                try:
                    status_container.text(f"Processing {pdf.name}...")

                    # Create the client with custom headers for each request
                    pdf_client = Anthropic(
                        api_key=st.secrets["ANTHROPIC_API_KEY"],
                        default_headers={"anthropic-beta": "pdfs-2024-09-25"}
                    )

                    # Create message content based on checkbox
                    message_content = [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64.b64encode(pdf.read()).decode()
                            }
                        },
                        {
                            "type": "text",
                            "text": calculations_examples if include_calculations else simple_examples
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]

                    # Send to Claude API
                    message = pdf_client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1024,
                        temperature=0,
                        system="You are an expert utility bill analyst specializing in data extraction and standardization. Your task is to accurately extract specific fields from utility bills while handling complex cases like split charges and maintaining consistent formatting.",
                        messages=[
                            {
                                "role": "user",
                                "content": message_content
                            }
                        ]
                    )

                    # Parse the JSON response
                    try:
                        extracted_data = json.loads(message.content[0].text)
                        # Add filename to the extracted data
                        extracted_data['filename'] = pdf.name
                        all_results.append(extracted_data)
                    except json.JSONDecodeError as je:
                        st.warning(f"Could not parse JSON from {pdf.name}. Raw response: {message.content[0].text}")
                        continue

                    # Update progress
                    progress_bar.progress((idx + 1) / len(uploaded_files))

                except Exception as e:
                    st.error(f"Error processing {pdf.name}: {str(e)}")

            if all_results:
                # Update processing status
                st.session_state.processing_status = f"{len(uploaded_files)} file{'s' if len(uploaded_files) > 1 else ''} processed!"
                status_container.text(st.session_state.processing_status)
                
                # Convert to DataFrame and store in session state
                df = pd.DataFrame(all_results)
                columns = ['filename'] + [col for col in df.columns if col != 'filename']
                df = df[columns]
                st.session_state.results_df = df

    # Display processing status if it exists
    if st.session_state.get('processing_status'):
        st.text(st.session_state.processing_status)

    # Reset processing status if new files are uploaded
    if uploaded_files:
        st.session_state.processing_status = None

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