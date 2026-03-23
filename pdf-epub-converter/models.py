from dataclasses import dataclass


@dataclass
class TocEntry:
    title: str
    page: str


@dataclass
class Chapter:
    title: str
    content: str


@dataclass
class BookItem:
    id: str
    href: str
    title: str
    order: int


@dataclass
class BookMetadata:
    title: str
    creator: str
    publisher: str
    year: str
    description: str
