
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def generate_payslip_pdf(payslip):
    """
    Generate a PDF payslip from an existing Payslip record.

    Returns:
        bytes: PDF file content.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=(595.28, 841.89),
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "PayslipTitle",
        parent=styles["Heading1"],
        alignment=TA_CENTER,
        fontSize=18,
        spaceAfter=18,
        textColor=colors.HexColor("#1E3A5F"),
    )

    right_style = ParagraphStyle(
        "RightAligned",
        parent=styles["Normal"],
        alignment=TA_RIGHT,
    )

    elements = []

    # Document heading
    elements.append(
        Paragraph("EMPLOYEE PAYSLIP", title_style)
    )

    elements.append(Spacer(1, 0.2 * inch))

    # Employee information
    employee_info = [
        ["Employee", str(payslip.employee)],
        ["Payroll Period", str(payslip.run.period)],
        ["Payslip ID", str(payslip.payslip_id)],
    ]

    employee_table = Table(
        employee_info,
        colWidths=[150, 350],
    )

    employee_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ])
    )

    elements.append(employee_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Salary breakdown
    salary_data = [
        ["Description", "Amount (AUD)"],
        ["Gross Pay", f"{payslip.gross_pay:,.2f}"],
        ["Tax", f"{payslip.tax_amount:,.2f}"],
        [
            "Total Deductions",
            f"{payslip.total_deductions:,.2f}",
        ],
        ["Net Pay", f"{payslip.net_pay:,.2f}"],
    ]

    salary_table = Table(
        salary_data,
        colWidths=[300, 200],
    )

    salary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("LINEBELOW", (0, -1), (-1, -1), 1, colors.black),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ])
    )

    elements.append(salary_table)
    elements.append(Spacer(1, 0.4 * inch))

    elements.append(
        Paragraph(
            "This payslip was generated electronically.",
            right_style,
        )
    )

    document.build(elements)

    pdf_content = buffer.getvalue()
    buffer.close()

    return pdf_content
