import unittest

from parsing.formatting import chapter_blocks


class ChapterBlocksRegressionTests(unittest.TestCase):
    def test_bullet_symbol_lines_form_unordered_list(self) -> None:
        text = (
            "• Признавать постоянно истинную причину рабства; то\n"
            "есть, работу злого духа или духов.\n"
            "• Выбрать отказ от абсолютно всего, связанного с\n"
            "силами тьмы. Часто объявляйте это.\n"
            "• Не говорите или не беспокойтесь об их проявлениях.\n"
            "Распознавайте, отвергайте и затем игнорируйте их.\n"
            "• Отвергайте и отклоняйте всю их ложь и отговорки как\n"
            "только их распознаете.\n"
            "• Замечайте мысли и путь, по которому они приходят и\n"
            "сразу объявляйте"
        )

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["list"])
        self.assertFalse(blocks[0]["ordered"])
        self.assertFalse(blocks[0]["show_markers"])
        self.assertEqual(len(blocks[0]["items"]), 5)
        self.assertTrue(blocks[0]["items"][2]["text"].startswith("Не говорите"))

    def test_two_bullet_symbol_lines_are_enough_for_list(self) -> None:
        text = "• Первый пункт\n• Второй пункт"

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["list"])
        self.assertEqual(len(blocks[0]["items"]), 2)

    def test_chapter_heading_with_immediate_paragraph_tail(self) -> None:
        text = (
            "Глава 10. Победа в конфликте.\n"
            "В предыдущей главе мы рассмотрели путь избавления\n"
            "от одержимости злыми духами. Но главный вопрос теперь:\n"
            '"как быть победителем над силами тьмы в целом"? Как же'
        )

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["h2", "p"])
        self.assertEqual(blocks[0]["text"], "Глава 10. Победа в конфликте.")
        self.assertTrue(
            blocks[1]["text"].startswith(
                "В предыдущей главе мы рассмотрели путь избавления"
            )
        )

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

    def test_malformed_numeric_marker_spacing_is_normalized(self) -> None:
        text = (
            "Оправдания.\n"
            "Или причины, внушенные лживыми духами,\n"
            "чтобы скрыть их дела.\n"
            "1 .Обнаружение оправданий, произведенных\n"
            "2 .Продолжение описания\n"
            "3 .Завершение"
        )

        blocks = chapter_blocks(text)

        self.assertIn("list", [block["type"] for block in blocks])
        list_block = next(block for block in blocks if block["type"] == "list")
        self.assertEqual(
            [item["marker"] for item in list_block["items"]], ["1.", "2.", "3."]
        )

    def test_ocr_upper_i_marker_is_normalized_to_one(self) -> None:
        text = "Подделка\nI. Первый пункт\n2. Второй пункт"

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["h2", "list"])
        self.assertEqual([item["marker"] for item in blocks[1]["items"]], ["1.", "2."])

    def test_ocr_lower_l_marker_is_normalized_to_one(self) -> None:
        text = "Подделка\nl. Первый пункт\n2. Второй пункт"

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["h2", "list"])
        self.assertEqual([item["marker"] for item in blocks[1]["items"]], ["1.", "2."])

    def test_non_sequential_numbered_items_are_not_list(self) -> None:
        text = "1. Первый\n3. Третий"

        blocks = chapter_blocks(text)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["type"], "p")
        self.assertIn("1. Первый", blocks[0]["text"])
        self.assertIn("3. Третий", blocks[0]["text"])

    def test_multiline_numbered_list_with_inline_next_marker_forms_list(self) -> None:
        text = (
            "Основание. И как с ним разбираться\n"
            "1. Устойчивое отвержение основания определенно\n"
            "пунктов, в чем верующий видит, что он был обманут и их\n"
            "причину и результаты. 2. Наблюдать, чтобы не предоставить\n"
            "нового основания.\n"
            "3. Ощущает и видит кажущиеся ухудшение, но в\n"
            "действительности это улучшение.\n"
            "4. Каждый пункт должен быть побежден постоянным\n"
            "отвержением (Также действием, например восстановленного\n"
            "разума.)"
        )

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["h2", "list"])
        list_block = blocks[1]
        self.assertEqual(
            [item["marker"] for item in list_block["items"]], ["1.", "2.", "3.", "4."]
        )
        self.assertIn("причину и результаты.", list_block["items"][0]["text"])
        self.assertTrue(list_block["items"][1]["text"].startswith("Наблюдать"))

    def test_continued_numbered_list_ignores_page_number_line(self) -> None:
        text = (
            '4. Я отвергаю "управление" злыми духами\n'
            '5. Я отвергаю "повиновение" злым духам\n'
            '6. Я отвергаю "молиться" злым духам\n'
            '7. Я отвергаю "вопрошать" что-нибудь у злых духов.\n'
            "207\n"
            '8. Я отвергаю "сдаваться" злым духам.\n'
            '9. Я отвергаю все "знание" от злых духов.\n'
            "10. Я отвергаю слушать злых духов.\n"
            '11. Я отвергаю "видения" от злых духов.\n'
            '12. Я отвергаю "контакты" со злыми духам'
        )

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["list"])
        self.assertEqual(blocks[0]["start"], 4)
        self.assertEqual(
            [item["marker"] for item in blocks[0]["items"]],
            ["4.", "5.", "6.", "7.", "8.", "9.", "10.", "11.", "12."],
        )
        self.assertNotIn("207", blocks[0]["items"][3]["text"])

    def test_numbered_list_splits_completed_tail_paragraph(self) -> None:
        text = (
            '11. Я отвергаю "видения" от злых духов.\n'
            '12. Я отвергаю "контакты" со злыми духами.\n'
            '13. Я отвергаю "сообщения" от злых духов.\n'
            '14. Я отвергаю всю "помощь" от злых духов.\n'
            "Верующий должен отменить согласие, которое он\n"
            "несознательно дал работе обманщиков. Они стремились\n"
            'работать через него и он теперь объявляет: "я сам желаю\n'
            "делать свою собственную работу."
        )

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["list", "p"])
        self.assertEqual(blocks[0]["start"], 11)
        self.assertEqual(
            [item["marker"] for item in blocks[0]["items"]],
            ["11.", "12.", "13.", "14."],
        )
        self.assertEqual(
            blocks[0]["items"][-1]["text"], 'Я отвергаю всю "помощь" от злых духов.'
        )
        self.assertTrue(
            blocks[1]["text"].startswith("Верующий должен отменить согласие")
        )

    def test_heading_plus_numbered_list_recovers_small_numbering_break(self) -> None:
        text = (
            "Подделка\n"
            "1. Первый пункт.\n"
            "2. Второй пункт.\n"
            "3. Третий пункт.\n"
            "5. Сломанный следующий номер.\n"
            "6. Еще один пункт вне последовательности"
        )

        blocks = chapter_blocks(text)

        self.assertEqual([block["type"] for block in blocks], ["h2", "list"])
        self.assertEqual(
            [item["marker"] for item in blocks[1]["items"]],
            ["1.", "2.", "3.", "4.", "5."],
        )
        self.assertTrue(blocks[1]["items"][3]["text"].startswith("Сломанный"))

    def test_short_heavily_broken_numbered_items_stay_paragraph(self) -> None:
        text = "1. Первый\n3. Третий\n5. Пятый"

        blocks = chapter_blocks(text)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["type"], "p")
        self.assertIn("1. Первый", blocks[0]["text"])
        self.assertIn("5. Пятый", blocks[0]["text"])

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
