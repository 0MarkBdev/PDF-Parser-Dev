"""Example definitions for the PDF Parser application."""

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
              "Current Meter Reading": "68950",
              "Previous Meter Reading": "65200",
              "Total Water Consumption": "3750",
              "Water Usage Charge": "2.25",
              "Water Usage Charge_2": "2.75",
              "Water Usage Charge_3": "3.25",
              "Water Usage Charge_CalcTotal": "8.25",
              "Technology Fee": "2.50",
              "Technology Fee_2": "2.50",
              "Technology Fee_CalcTotal": "5.00",
              "Capacity Charge Maximum Demand": "12.50",
              "Capacity Charge Maximum Demand_2": "12.50",
              "Capacity Charge Maximum Demand_CalcTotal": "25.00",
              "Reactive Power Charge": null,
              "Total Current Charges": "46.50"
            }
        </ideal_output>
    </example>
</examples>"""

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
              "Current Meter Reading": "68950",
              "Previous Meter Reading": "65200",
              "Total Water Consumption": "3750",
              "Water Usage Charge_CalcTotal": "8.25",
              "Technology Fee_CalcTotal": "5.00",
              "Capacity Charge Maximum Demand_CalcTotal": "25.00",
              "Reactive Power Charge": null,
              "Total Current Charges": "46.50"
            }
        </ideal_output>
    </example>
</examples>""" 