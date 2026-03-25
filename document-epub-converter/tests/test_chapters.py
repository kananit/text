import unittest

from models import TocEntry
from parsing.chapters import identify_chapters


class IdentifyChaptersRegressionTests(unittest.TestCase):
    def test_explicit_chapter_heading_keeps_first_body_line(self) -> None:
        text = (
            "Глава 10. Победа в конфликте.\n"
            "В предыдущей главе мы рассмотрели путь избавления\n"
            "от одержимости злыми духами. Но главный вопрос теперь:\n"
            '"как быть победителем над силами тьмы в целом"? Как же\n\n'
            "Глава 11. Следующая глава.\n"
            "Текст следующей главы, достаточный по длине для разбиения. "
            "Текст следующей главы, достаточный по длине для разбиения. "
            "Текст следующей главы, достаточный по длине для разбиения. "
            "Текст следующей главы, достаточный по длине для разбиения. "
            "Текст следующей главы, достаточный по длине для разбиения.\n"
        )
        toc_entries = [
            TocEntry(title="Глава 10. Победа в конфликте", page="1"),
            TocEntry(title="Глава 11. Следующая глава", page="2"),
        ]

        chapters = identify_chapters(text, toc_entries)

        self.assertGreaterEqual(len(chapters), 1)
        self.assertEqual(chapters[0].title, "Глава 10. Победа в конфликте")
        self.assertTrue(
            chapters[0].content.startswith(
                "В предыдущей главе мы рассмотрели путь избавления"
            )
        )


if __name__ == "__main__":
    unittest.main()
