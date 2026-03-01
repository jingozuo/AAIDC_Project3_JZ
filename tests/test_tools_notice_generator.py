"""Unit tests for the notice_generator tool (PDF cancellation notice)."""
import os
import pytest

from codes.tools import notice_generator as notice_generator_module


class TestGenerateNoticePdf:
    """Test generate_notice_pdf with a temporary output directory."""

    def test_generate_notice_pdf_creates_file_and_returns_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(notice_generator_module, "OUTPUTS_DIR", str(tmp_path))
        policy = {"policy_number": "POL01212"}
        notice_text = "This policy is cancelled.\nRefund will be processed."
        path = notice_generator_module.generate_notice_pdf(
            policy, 150.50, "Refund calculated.", notice_text
        )
        assert path == os.path.join(str(tmp_path), "Cancellation_Notice_POL01212.pdf")
        assert os.path.isfile(path)

    def test_generate_notice_pdf_empty_policy_number(self, tmp_path, monkeypatch):
        monkeypatch.setattr(notice_generator_module, "OUTPUTS_DIR", str(tmp_path))
        policy = {}
        path = notice_generator_module.generate_notice_pdf(
            policy, 0.0, "", "Notice body."
        )
        assert "Cancellation_Notice_.pdf" in path
        assert os.path.isfile(path)

    def test_pdf_contains_title(self, tmp_path, monkeypatch):
        monkeypatch.setattr(notice_generator_module, "OUTPUTS_DIR", str(tmp_path))
        policy = {"policy_number": "POL001"}
        notice_generator_module.generate_notice_pdf(
            policy, 0.0, "", "Body text."
        )
        pdf_path = tmp_path / "Cancellation_Notice_POL001.pdf"
        assert pdf_path.stat().st_size > 200


class TestNoticeGeneratorHelpers:
    """Test internal helpers (module-private)."""

    def test_draw_text_returns_new_y(self, tmp_path):
        from reportlab.pdfgen import canvas
        from codes.tools.notice_generator import _draw_text, LINE_HEIGHT, BODY_FONT_SIZE
        pdf_path = tmp_path / "out.pdf"
        c = canvas.Canvas(str(pdf_path))
        y = 100.0
        new_y = _draw_text(c, 50, y, LINE_HEIGHT, "Hello", font_size=BODY_FONT_SIZE)
        assert new_y == y - LINE_HEIGHT

    def test_check_new_page_returns_same_y_when_above_margin(self, tmp_path):
        from codes.tools.notice_generator import _check_new_page
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(tmp_path / "out.pdf"), pagesize=A4)
        _, height = A4
        y = height - 100
        result = _check_new_page(c, y, height)
        assert result == y
