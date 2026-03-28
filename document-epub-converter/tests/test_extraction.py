import unittest

from extraction import _format_pdf_span


class ExtractionFormattingTests(unittest.TestCase):
    def test_format_pdf_span_wraps_bold_core(self) -> None:
        text = "Марина – женщина, у которой было много браков."
        self.assertEqual(
            _format_pdf_span(text, is_bold=True),
            "**Марина – женщина, у которой было много браков.**",
        )

    def test_format_pdf_span_keeps_leading_and_trailing_spaces(self) -> None:
        text = "  Марина – женщина.  "
        self.assertEqual(
            _format_pdf_span(text, is_bold=True),
            "  **Марина – женщина.**  ",
        )

    def test_format_pdf_span_leaves_non_bold_unchanged(self) -> None:
        text = "Обычный текст"
        self.assertEqual(_format_pdf_span(text, is_bold=False), text)


if __name__ == "__main__":
    unittest.main()
