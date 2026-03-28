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

    def test_multiline_styled_explicit_heading_is_chapter_title(self) -> None:
        first_body = (
            "Текст первой главы, который должен остаться контентом и быть достаточно длинным. "
            * 80
        )
        second_body = "Текст второй главы, достаточный для разбиения. " * 40
        text = (
            "Глава 1. **ПРАВЛЕНИЕ ФИНИКИЙСКОЙ**\n"
            "ПРИНЦЕССЫ\n"
            f"{first_body}\n\n"
            "Глава 2. **СЛЕДУЮЩАЯ ГЛАВА**\n"
            f"{second_body}\n"
        )
        toc_entries = [
            TocEntry(title="Глава 1. ПРАВЛЕНИЕ ФИНИКИЙСКОЙ ПРИНЦЕССЫ", page="1"),
            TocEntry(title="Глава 2. СЛЕДУЮЩАЯ ГЛАВА", page="2"),
        ]

        chapters = identify_chapters(text, toc_entries)

        self.assertGreaterEqual(len(chapters), 2)
        self.assertEqual(chapters[0].title, "Глава 1. ПРАВЛЕНИЕ ФИНИКИЙСКОЙ ПРИНЦЕССЫ")
        self.assertNotIn("**", chapters[0].title)
        self.assertTrue(chapters[0].content.startswith("Текст первой главы"))

    def test_bare_chapter_heading_with_uppercase_next_line_merges_title(self) -> None:
        first_body = "Контент первой главы. " * 160
        second_body = "Контент второй главы. " * 80
        text = (
            "Глава 14\n"
            "ИЗРЕЕЛЬСКИЕ ПСЫ, ЛОШАДЬ ИИУЯ\n"
            f"{first_body}\n\n"
            "Глава 15\n"
            "СЛЕДУЮЩИЙ РАЗДЕЛ\n"
            f"{second_body}\n"
        )
        toc_entries = [
            TocEntry(title="Глава 14. ИЗРЕЕЛЬСКИЕ ПСЫ, ЛОШАДЬ ИИУЯ", page="1"),
            TocEntry(title="Глава 15. СЛЕДУЮЩИЙ РАЗДЕЛ", page="2"),
        ]

        chapters = identify_chapters(text, toc_entries)

        self.assertGreaterEqual(len(chapters), 2)
        self.assertEqual(chapters[0].title, "Глава 14. ИЗРЕЕЛЬСКИЕ ПСЫ, ЛОШАДЬ ИИУЯ")
        self.assertTrue(chapters[0].content.startswith("Контент первой главы"))

    def test_nonbare_explicit_heading_with_wrapped_uppercase_part_merges(self) -> None:
        first_body = "Текст первой главы. " * 160
        second_body = "Текст второй главы. " * 80
        text = (
            "Глава 1. ПРАВЛЕНИЕ ФИНИКИЙСКОЙ\n"
            "ПРИНЦЕССЫ\n"
            f"{first_body}\n\n"
            "Глава 2. СЛЕДУЮЩАЯ ГЛАВА\n"
            f"{second_body}\n"
        )
        toc_entries = [
            TocEntry(title="Глава 1. ПРАВЛЕНИЕ ФИНИКИЙСКОЙ ПРИНЦЕССЫ", page="1"),
            TocEntry(title="Глава 2. СЛЕДУЮЩАЯ ГЛАВА", page="2"),
        ]

        chapters = identify_chapters(text, toc_entries)

        self.assertGreaterEqual(len(chapters), 2)
        self.assertEqual(chapters[0].title, "Глава 1. ПРАВЛЕНИЕ ФИНИКИЙСКОЙ ПРИНЦЕССЫ")
        self.assertTrue(chapters[0].content.startswith("Текст первой главы"))

    def test_bare_heading_with_two_line_title_merges_both(self) -> None:
        first_body = "Я узнаю этот взгляд везде. Изогнутые брови. " * 160
        second_body = "Текст второй главы. " * 80
        text = (
            "Глава 1.\n"
            "ПРАВЛЕНИЕ ФИНИКИЙСКОЙ\n"
            "ПРИНЦЕССЫ\n"
            f"{first_body}\n\n"
            "Глава 2.\n"
            "СЛЕДУЮЩАЯ ГЛАВА\n"
            f"{second_body}\n"
        )
        toc_entries = [
            TocEntry(title="Глава 1. ПРАВЛЕНИЕ ФИНИКИЙСКОЙ ПРИНЦЕССЫ", page="1"),
            TocEntry(title="Глава 2. СЛЕДУЮЩАЯ ГЛАВА", page="2"),
        ]

        chapters = identify_chapters(text, toc_entries)

        self.assertGreaterEqual(len(chapters), 2)
        self.assertEqual(chapters[0].title, "Глава 1. ПРАВЛЕНИЕ ФИНИКИЙСКОЙ ПРИНЦЕССЫ")
        self.assertTrue(chapters[0].content.startswith("Я узнаю этот взгляд везде"))

    def test_posvyashchenie_recognized_as_chapter(self) -> None:
        body = "Посвящается всем, кто искал истину и нашёл её. " * 10
        chapter_body = "Текст первой главы. " * 160
        text = "Посвящение\n" f"{body}\n\n" "Глава 1. Начало\n" f"{chapter_body}\n"
        toc_entries = [
            TocEntry(title="Посвящение", page="1"),
            TocEntry(title="Глава 1. Начало", page="2"),
        ]

        chapters = identify_chapters(text, toc_entries)

        titles = [ch.title for ch in chapters]
        self.assertIn("Посвящение", titles)

    def test_vstuplenie_recognized_as_chapter(self) -> None:
        body = (
            "Вступительное слово автора, достаточно длинное, чтобы образовать раздел. "
            * 10
        )
        chapter_body = "Текст первой главы. " * 160
        text = "Вступление\n" f"{body}\n\n" "Глава 1. Начало\n" f"{chapter_body}\n"
        toc_entries = [
            TocEntry(title="Вступление", page="1"),
            TocEntry(title="Глава 1. Начало", page="2"),
        ]

        chapters = identify_chapters(text, toc_entries)

        titles = [ch.title for ch in chapters]
        self.assertIn("Вступление", titles)


if __name__ == "__main__":
    unittest.main()
