# Rule-Engine Overview

## Что изменилось

Логика разбора блоков в [parsing/formatting.py](./parsing/formatting.py) переведена из длинной цепочки условных проверок в явную rule-engine схему.

Раньше `flush_buffer()` содержал последовательность `if/return` с несколькими уровнями вложенности.
Теперь те же эвристики оформлены как набор именованных правил, которые применяются по порядку.

## Основные элементы

### 1. Rule model

В [parsing/formatting.py](./parsing/formatting.py) добавлен `BlockRule`.

- `BlockRule.name`: человекочитаемое имя правила
- `BlockRule.handler`: функция, которая получает `non_empty` и возвращает `True`, если правило сработало

Это делает порядок эвристик явным и позволяет изменять поведение через список правил, а не через переписывание `flush_buffer()`.

### 2. Ordered rule list

Внутри `chapter_blocks()` собран `block_rules`.

Он задаёт приоритет правил в одном месте. Это важно, потому что парсер эвристический: одно и то же содержимое может выглядеть как `h2`, `p` или `list`, и итог зависит от порядка проверок.

Текущий порядок такой:

1. table
2. heading с italic tail
3. heading с paragraph tail
4. numbered subheading with tail
5. three-line heading
6. two-line heading with italic tail
7. heading plus list
8. prefix and list
9. split list and tail
10. plain list block
11. single numeric marker list
12. short subheading
13. fallback paragraph

### 3. Small rule handlers

Каждая крупная ветка теперь вынесена в отдельный `try_*` helper в [parsing/formatting.py](./parsing/formatting.py):

- `try_emit_table`
- `try_emit_heading_dot_with_italic_tail`
- `try_emit_heading_dot_with_paragraph_tail`
- `try_emit_numbered_subheading_with_tail`
- `try_emit_three_line_heading`
- `try_emit_two_line_heading_with_italic_tail`
- `try_emit_heading_plus_list`
- `try_emit_prefix_and_list`
- `try_emit_split_list_and_tail`
- `try_emit_list_block`
- `try_emit_single_numeric_marker_list`
- `try_emit_short_subheading`

`flush_buffer()` теперь только:

1. нормализует буфер
2. прогоняет список правил по порядку
3. если ни одно не сработало, вызывает fallback paragraph

## Сопутствующие структурные изменения

### Централизация list marker logic

В [parsing/formatting.py](./parsing/formatting.py) добавлен `match_list_marker()`.

Он стал единой точкой для распознавания list marker'ов и поддерживает режим `require_standalone_numeric=True` для отсечения inline-перечислений вида:

- `..., (2) согласится доверять ...`

### State object for list parsing

В [parsing/formatting.py](./parsing/formatting.py) добавлен `ListParsingState`.

Он собирает состояние, которое раньше жило в отдельных локальных переменных:

- `current_item`
- `current_item_text`
- `current_marker`
- `marker_count`
- `list_kind`
- `list_start`
- `has_non_marker_continuation`
- `is_numbered_list`

Это используется в:

- `build_list_block()`
- `split_list_and_tail()`

## Почему это лучше

### Читаемость

Теперь видно не только _как_ работает парсер, но и _в каком порядке_ применяются эвристики.

### Локальность изменений

Если нужно поправить одно правило, обычно достаточно изменить один `try_*` handler, не трогая весь `flush_buffer()`.

### Безопасность рефакторинга

После перехода на rule-engine добавлены регрессионные тесты в [tests/test_formatting.py](./tests/test_formatting.py), которые фиксируют ключевые кейсы:

- inline `(1)` после `то есть,`
- список с `Различные виды демонов`
- вопросительные заголовки
- quoted heading
- numbered heading, который не должен становиться list

## Как расширять дальше

Если появляется новый эвристический кейс:

1. сначала добавить регрессионный тест в [tests/test_formatting.py](./tests/test_formatting.py)
2. затем решить, это:
   - новый `try_*` rule
   - изменение существующего rule
   - изменение helper-функции вроде `match_list_marker()`
3. если это новый rule, вставить его в `block_rules` строго в том месте, где он должен иметь приоритет

## Текущее состояние

Rule-engine уже используется в рабочем пайплайне EPUB-сборки.

Проверено:

- `python3.12 -m unittest discover -s tests -p 'test*.py'`
- `python3.12 main.py --yes`

Обе проверки проходят успешно.
