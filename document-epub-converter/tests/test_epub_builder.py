import unittest

from epub_builder import render_blocks_to_xhtml


class EpubBuilderInlineFormattingTests(unittest.TestCase):
    def test_paragraph_preserves_inline_bold_markdown(self) -> None:
        blocks = [
            {
                "type": "p",
                "text": "До **Марина – женщина, у которой было много браков.** После",
            }
        ]

        html = render_blocks_to_xhtml(blocks)

        self.assertIn(
            "<p>До <strong>Марина – женщина, у которой было много браков.</strong> После</p>",
            html,
        )

    def test_list_item_preserves_inline_bold_html_marker(self) -> None:
        blocks = [
            {
                "type": "list",
                "ordered": True,
                "show_markers": False,
                "items": [
                    {"marker": "1.", "text": "Обычный пункт"},
                    {"marker": "2.", "text": "Пункт с <b>жирным текстом</b> внутри"},
                ],
            }
        ]

        html = render_blocks_to_xhtml(blocks)

        self.assertIn("<li>Обычный пункт</li>", html)
        self.assertIn(
            "<li>Пункт с <strong>жирным текстом</strong> внутри</li>",
            html,
        )

    def test_inline_bold_content_is_escaped_safely(self) -> None:
        blocks = [{"type": "p", "text": "**x < y & z**"}]

        html = render_blocks_to_xhtml(blocks)

        self.assertIn("<strong>x &lt; y &amp; z</strong>", html)


if __name__ == "__main__":
    unittest.main()
