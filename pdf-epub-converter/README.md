# Document → EPUB Converter

Универсальный конвертер EPUB 2.0.

## Как работает

Скрипт ищет в папке `pdf-epub/`:

- первый подходящий источник: `*.pdf`, `*.docx`, `*.doc`
- обложку `*.jpeg` / `*.jpg` (приоритет: `<source_name>_cover.*`, `<source_name>.*`, `cover.*`, затем первый jpeg/jpg)
- файл метаданных `meta.json`
- шаблон `meta.example.json` (если отсутствует — создаётся автоматически)

На выходе создаётся EPUB с тем же именем, что и исходный файл:

- `Book.pdf` → `Book.epub`
- `Book.docx` → `Book.epub`
- `Book.doc` → `Book.epub`

## Запуск

1. Сгенерировать/обновить метаданные из исходного файла:

```bash
python3 pdf-epub-converter/extract_metadata.py
```

2. Проверить и при необходимости вручную поправить `pdf-epub/meta.json`.
   Если `meta.json` отсутствует, скрипт сначала пробует извлечь мету из исходного файла и только недостающие поля берёт из `pdf-epub-converter/meta.example.json`.

3. Собрать EPUB:

```bash
python3 pdf-epub-converter/main.py
```

Для неинтерактивного режима (CI), чтобы не ждать ручного подтверждения `meta.json`:

```bash
python3 pdf-epub-converter/main.py --yes
```

В интерактивном режиме для продолжения введите `y` или `yes`.
Любая другая команда прерывает сборку.

## Пример `meta.json`

```json
{
  "title": "Название книги",
  "creator": "Имя Автора",
  "publisher": "Название издательства",
  "year": "2000",
  "description": "Краткое описание книги."
}
```

## Примечания

- Обязательные поля для сборки EPUB: `title`, `creator`, `year`.
- Если обязательные поля не найдены в исходном файле и/или `meta.json`, они заполняются из `EXAMPLE_META_*` в `config.py`, и скрипт выводит warning.
- При первом запуске автоматически создаётся `meta.example.json` (если отсутствует), а `meta.json` формируется по схеме: исходный файл → fallback к `meta.example.json`.
- `publisher` и `description` считаются необязательными и будут заполнены автоматически при отсутствии.
- Для извлечения текста из PDF нужен `pdftotext` (Poppler):

```bash
brew install poppler
```

- Для `doc` / `docx` на macOS используется встроенный `textutil`.
