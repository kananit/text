import unittest

from parsing.formatting import chapter_blocks


class ChapterBlocksRegressionTests(unittest.TestCase):
    def test_heading_with_lowercase_numbered_items_forms_list(self) -> None:
        text = (
            "Неправильное толкование\n"
            "1. оставляет человека безгрешным\n"
            "2. Человек не должен ни говорить, ни"
        )

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["h2", "list"])
        self.assertTrue(blocks[1]["ordered"])
        self.assertEqual([item["marker"] for item in blocks[1]["items"]], ["1.", "2."])

    def test_heading_with_inline_second_numbered_item_forms_list(self) -> None:
        text = (
            "Неправильное толкование\n"
            "1. оставляет человека безгрешным 2. Человек не должен ни говорить, ни"
        )

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["h2", "list"])
        self.assertEqual([item["marker"] for item in blocks[1]["items"]], ["1.", "2."])
        self.assertTrue(blocks[1]["items"][0]["text"].startswith("оставляет"))

    def test_inline_numeric_enumeration_after_to_est_stays_paragraph(self) -> None:
        text = (
            "защиты. Иногда их доверие покрывает неправильное\n"
            "состояние в самих себе, которое скрыто от их знания, то есть,\n"
            "(1) Они имеют тайную самоуверенность, что способны\n"
            "рассудить о том, что они видят и слышат, что не имеет\n"
            "никакого основания в истинной уверенности в Боге, (2) тайный дух\n"
            "любопытства."
        )

        blocks = chapter_blocks(text)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["type"], "p")
        self.assertIn("тайную самоуверенность", blocks[0]["text"])

    def test_parenthesized_numbered_demon_items_stay_paragraphs(self) -> None:
        text = (
            "(1) Проявление силы демона.\n"
            "Дела демонов всегда становятся более заметны вниманию.\n"
            "(2) Различные виды демонов.\n"
            "Демонов бывает множество, великое разнообразие.\n"
            "Они имеют различные типы и больше в разнообразии, чем люди.\n\n"
            "(3) Как демоны сосредотачиваются в людях.\n"
            "Они ищут тех, чье состояние наиболее благоприятно им."
        )

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["p", "p"])
        self.assertIn("(1) Проявление силы демона", blocks[0]["text"])
        self.assertIn("(2) Различные виды демонов", blocks[0]["text"])
        self.assertIn("(3) Как демоны сосредотачиваются в людях", blocks[1]["text"])

    def test_question_headings_become_h2(self) -> None:
        text = (
            'Могут ли "честные души" быть обмануты?\n\n'
            "Есть одна превалирующая идея.\n\n"
            'Духовно ли высказывание о подчинению "Духу"?\n\n'
            '"Святого Духа, Которого Бог дал повинующимся Ему".'
        )

        blocks = chapter_blocks(text)

        self.assertEqual(blocks[0]["type"], "h2")
        self.assertEqual(blocks[0]["text"], 'Могут ли "честные души" быть обмануты?')
        self.assertEqual(blocks[2]["type"], "h2")
        self.assertEqual(
            blocks[2]["text"],
            'Духовно ли высказывание о подчинению "Духу"?',
        )

    def test_quoted_heading_becomes_h2(self) -> None:
        text = '"Гудение" злых духов.\n\nЭто постоянное "гудение" в ушах.'

        blocks = chapter_blocks(text)

        self.assertEqual(blocks[0]["type"], "h2")
        self.assertEqual(blocks[0]["text"], '"Гудение" злых духов')

    def test_numbered_heading_with_tail_stays_heading_not_list(self) -> None:
        text = (
            '2. Предполагаемое единство для "Пробуждения".\n\n'
            "В течение некоторого времени у меня было на сердце попробовать описать нечто."
        )

        blocks = chapter_blocks(text)

        self.assertEqual(blocks[0]["type"], "h2")
        self.assertEqual(
            blocks[0]["text"],
            '2. Предполагаемое единство для "Пробуждения"',
        )


if __name__ == "__main__":
    unittest.main()
