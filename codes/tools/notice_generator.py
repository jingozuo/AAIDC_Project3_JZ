"""
Notice Generator — single-responsibility tool for generating cancellation notice PDFs.

Role: Produce a PDF cancellation notice in paths.OUTPUTS_DIR with title, boilerplate
description, and notice_text (from Summary agent LLM). Used only by the Summary agent
(see agent_roles.TOOL_RESPONSIBILITIES). Filename: Cancellation_Notice_{policy_number}.pdf.
"""
import os
from datetime import datetime
from typing import Any, Dict

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from codes.paths import OUTPUTS_DIR

# Layout constants for PDF (ReportLab)
MARGIN = 50
LINE_HEIGHT = 15
TITLE_FONT_SIZE = 18
BODY_FONT_SIZE = 11


def _draw_text(c: canvas.Canvas, x: float, y: float, line_height: float, text: str, font_name: str = "Helvetica", font_size: int = BODY_FONT_SIZE) -> float:
    """Draw a single line at (x, y) and return the new y position (y - line_height)."""
    c.setFont(font_name, font_size)
    c.drawString(x, y, text)
    return y - line_height


def _check_new_page(c: canvas.Canvas, y: float, height: float) -> float:
    """If y is below MARGIN, start a new page and return (height - MARGIN); else return y."""
    if y < MARGIN:
        c.showPage()
        return height - MARGIN
    return y


def generate_notice_pdf(policy_details: Dict[str, Any], refund_amount: float, refund_reason: str, notice_text: str) -> str:
    """
    Generate the cancellation notice as a PDF and save to OUTPUTS_DIR.

    Args:
        policy_details: Used for filename (policy_number). Other keys unused.
        refund_amount: Not embedded in this version; can be added to content.
        refund_reason: Not embedded in this version; can be added to content.
        notice_text: Main body content (typically from LLM); rendered line by line.

    Returns:
        Absolute path to the saved PDF file.
    """
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    filename = f"Cancellation_Notice_{policy_details.get('policy_number', '')}.pdf"
    file_path = os.path.join(OUTPUTS_DIR, filename)

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    x = MARGIN
    y = height - MARGIN

    # Title
    y = _draw_text(c, x, y, LINE_HEIGHT + 4, "Insurance Cancellation Notice", "Helvetica-Bold", TITLE_FONT_SIZE)
    y -= 10  # extra space after title

    # Description
    description_lines = [
        "This document confirms the cancellation of your insurance policy and related refund details.",
        "Please retain this notice for your records.",
        "",
    ]
    for line in description_lines:
        y = _draw_text(c, x, y, LINE_HEIGHT, line)
        y = _check_new_page(c, y, height)
    y -= 10  # space before details

    # Section label for details
    y = _draw_text(c, x, y, LINE_HEIGHT + 2, "Details", "Helvetica-Bold", BODY_FONT_SIZE)
    y -= 5

    # Notice details (main content)
    for line in notice_text.split("\n"):
        y = _draw_text(c, x, y, LINE_HEIGHT, line)
        y = _check_new_page(c, y, height)

    c.save()

    return file_path
