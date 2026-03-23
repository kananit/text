# PDF → EPUB Converter

Универсальный конвертер EPUB 2.0.

## Как работает

Скрипт ищет в папке `pdf-epub/`:

- первый файл `*.pdf` — источник
- обложку `*.jpeg` / `*.jpg` (приоритет: `<pdfname>_cover.*`, `<pdfname>.*`, `cover.*`, затем первый jpeg/jpg)
- файл метаданных `meta.json`
- шаблон `meta.example.json` (если отсутствует — создаётся автоматически)

На выходе создаётся EPUB с тем же именем, что и PDF:

- `Book.pdf` → `Book.epub`

## Запуск

1. Сгенерировать/обновить метаданные из PDF:

```bash
python3 pdf-epub-converter/extract_metadata_from_pdf.py
```

2. Проверить и при необходимости вручную поправить `pdf-epub/meta.json`.
   Если `meta.json` отсутствует, скрипт сначала пробует извлечь мету из PDF и только недостающие поля берёт из `pdf-epub-converter/meta.example.json`.

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
- Если обязательные поля не найдены в PDF и/или `meta.json`, они заполняются из `EXAMPLE_META_*` в `config.py`, и скрипт выводит warning.
- При первом запуске автоматически создаётся `meta.example.json` (если отсутствует), а `meta.json` формируется по схеме: PDF → fallback к `meta.example.json`.
- `publisher` и `description` считаются необязательными и будут заполнены автоматически при отсутствии.
- Для извлечения текста нужен `pdftotext` (Poppler):

```bash
brew install poppler
```
