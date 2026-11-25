# -*- coding: utf-8 -*-
"""Персональний помічник: контакти, дні народження, нотатки й теги.

Python 3.10+, без зовнішніх залежностей.
    python personal_assistant.py             — основна книга
    python personal_assistant.py --demo      — окрема навчальна книга
    python personal_assistant.py --no-color  — без кольорів

Усе керування — цифрами. 0 — назад або скасування поточної дії.
"""

import argparse
import datetime as legacy_datetime
import json
import os
import pickle
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path


# ======================================================================
# Загальні помічники
# ======================================================================

def collapse_spaces(value):
    """'  Олена   Марія ' -> 'Олена Марія'."""
    return " ".join(str(value).split()) if value is not None else ""


def plural(number, one, few, many):
    """plural(3, 'день', 'дні', 'днів') -> 'дні'."""
    number = abs(number) % 100
    if 11 <= number <= 19:
        return many
    number %= 10
    if number == 1:
        return one
    if 2 <= number <= 4:
        return few
    return many


# ======================================================================
# Поля контакту
# ======================================================================

DATE_FORMAT = "%d.%m.%Y"
MIN_BIRTH_YEAR = 1900
MAX_NAME_LENGTH = 50

# 10 цифр (0501234567) або міжнародний формат (+380501234567).
PHONE_PATTERN = re.compile(r"[0-9]{10}|\+[0-9]{11,15}")
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)
BIRTHDAY_PATTERN = re.compile(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}")
# Слово імені: літери; усередині слова — апостроф або дефіс (Мар'яна, Нечуй-Левицький).
NAME_WORD_PATTERN = re.compile(r"[^\W\d_]+(?:['\-][^\W\d_]+)*")

NAME_REQUIRED_MESSAGE = (
    "Ім'я видалити не можна: у кожного контакту має бути ім'я. Його можна лише "
    "замінити. Видалити можна прізвище, телефон, email, адресу й день народження."
)


def normalize_phone(value):
    """Прибирає пробіли, дефіси, дужки й крапки: '050 123-45-67' -> '0501234567'."""
    return re.sub(r"[\s\-().]", "", str(value))


class Field:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)

    @classmethod
    def from_storage(cls, value):
        """Без суворої перевірки: старі записи не губляться під час завантаження."""
        value = collapse_spaces(value)
        if not value:
            raise ValueError("порожнє значення")
        obj = cls.__new__(cls)
        Field.__init__(obj, value)
        return obj


class Name(Field):
    """Ім'я або прізвище: літери, пробіли між словами, апостроф і дефіс усередині слова."""

    def __init__(self, value, label="Ім'я"):
        # Різні види апострофа зводимо до одного.
        value = collapse_spaces(value).replace("’", "'").replace("ʼ", "'")
        if not value:
            raise ValueError(f"{label}: поле не може бути порожнім.")
        if any(char.isdigit() for char in value):
            raise ValueError(
                f"{label}: цифри неприпустимі. Використовуйте лише літери, "
                "пробіли між словами, апостроф або дефіс."
            )
        if not all(NAME_WORD_PATTERN.fullmatch(word) for word in value.split(" ")):
            raise ValueError(
                f"{label}: дозволені лише літери, пробіли між словами, апостроф "
                "(Мар'яна) і дефіс усередині слова (Нечуй-Левицький)."
            )
        if len(value) > MAX_NAME_LENGTH:
            raise ValueError(f"{label}: не довше за {MAX_NAME_LENGTH} символів.")
        super().__init__(value)

    @staticmethod
    def is_valid(value):
        try:
            Name(value)
        except ValueError:
            return False
        return True


class Phone(Field):
    def __init__(self, value):
        normalized = normalize_phone(value)
        if not PHONE_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Невірний телефон. Введіть 10 цифр (0501234567) або "
                "міжнародний формат (+380501234567)."
            )
        super().__init__(normalized)


class Email(Field):
    def __init__(self, value):
        value = str(value).strip()
        if len(value) > 254 or not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Невірний email. Приклад: olena@example.com")
        super().__init__(value)


class Address(Field):
    def __init__(self, value):
        value = collapse_spaces(value)
        if not value:
            raise ValueError("Адреса не може бути порожньою.")
        if not any(char.isalpha() for char in value):
            raise ValueError(
                "Адреса не може складатися лише з цифр і знаків. Вкажіть місто "
                "й вулицю, наприклад: Київ, вул. Садова, 12."
            )
        super().__init__(value)

    @staticmethod
    def is_valid(value):
        try:
            Address(value)
        except ValueError:
            return False
        return True


class Birthday(Field):
    def __init__(self, value):
        error_message = "Невірна дата. Використовуйте формат ДД.ММ.РРРР, наприклад 05.03.1990."

        if not isinstance(value, str) or not BIRTHDAY_PATTERN.fullmatch(value.strip()):
            raise ValueError(error_message)
        try:
            birthday = datetime.strptime(value.strip(), DATE_FORMAT).date()
        except ValueError as error:
            raise ValueError(error_message) from error

        if birthday > date.today():
            raise ValueError("Дата народження не може бути в майбутньому.")
        if birthday.year < MIN_BIRTH_YEAR:
            raise ValueError(f"Рік народження має бути не раніше {MIN_BIRTH_YEAR}.")
        super().__init__(birthday)

    def __str__(self):
        return self.value.strftime(DATE_FORMAT)


# ======================================================================
# Контакт
# ======================================================================

class Record:
    """Один контакт. id видає AddressBook під час додавання."""

    def __init__(self, first_name, last_name=None, record_id=None, strict=True):
        if strict:
            make = Name
        else:
            make = lambda value, label: Name.from_storage(value)  # noqa: E731
        self.id = record_id
        self.first_name = make(first_name, "Ім'я")
        self.last_name = make(last_name, "Прізвище") if collapse_spaces(last_name) else None
        self.phones = []
        self.email = None
        self.address = None
        self.birthday = None

    @property
    def full_name(self):
        if self.last_name is None:
            return self.first_name.value
        return f"{self.first_name.value} {self.last_name.value}"

    def names_are_valid(self):
        return Name.is_valid(self.first_name.value) and (
            self.last_name is None or Name.is_valid(self.last_name.value)
        )

    # --- прості поля (None очищає значення) ---

    def set_first_name(self, value):
        if value is None:
            raise ValueError(NAME_REQUIRED_MESSAGE)
        self.first_name = Name(value, "Ім'я")

    def set_last_name(self, value):
        self.last_name = None if value is None else Name(value, "Прізвище")

    def set_email(self, value):
        self.email = None if value is None else Email(value)

    def set_address(self, value):
        self.address = None if value is None else Address(value)

    def set_birthday(self, value):
        self.birthday = None if value is None else Birthday(value)

    # --- телефони ---

    def check_new_phone(self, value, skip_phone=None):
        """Перевіряє номер і його унікальність у контакту; повертає Phone."""
        new_phone = Phone(value)
        for phone_obj in self.phones:
            if phone_obj is not skip_phone and phone_obj.value == new_phone.value:
                raise ValueError(f"У контакту вже є номер {new_phone.value}.")
        return new_phone

    def add_phone(self, value):
        new_phone = self.check_new_phone(value)
        self.phones.append(new_phone)
        return new_phone

    def remove_phone(self, value):
        phone_obj = self.find_phone(value)
        if phone_obj is None:
            raise ValueError(f"Номер {value} не знайдено в контакту.")
        self.phones.remove(phone_obj)

    def edit_phone(self, old_value, new_value):
        phone_obj = self.find_phone(old_value)
        if phone_obj is None:
            raise ValueError(f"Номер {old_value} не знайдено в контакту.")
        new_phone = self.check_new_phone(new_value, skip_phone=phone_obj)
        self.phones[self.phones.index(phone_obj)] = new_phone

    def find_phone(self, value):
        value = normalize_phone(value)
        for phone_obj in self.phones:
            if phone_obj.value == value:
                return phone_obj
        return None

    # --- пошук ---

    def matches(self, query):
        """Чи є query (без урахування регістру) в імені, телефонах, email, адресі, даті."""
        query = collapse_spaces(query).lower().replace("’", "'").replace("ʼ", "'")
        if not query:
            return False

        parts = [self.full_name]
        parts.extend(phone.value for phone in self.phones)
        for optional in (self.email, self.address, self.birthday):
            if optional is not None:
                parts.append(str(optional))
        if any(query in part.lower() for part in parts):
            return True

        digits = normalize_phone(query)
        return bool(digits) and any(digits in phone.value for phone in self.phones)

    # --- збереження ---

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name.value,
            "last_name": self.last_name.value if self.last_name else None,
            "phones": [phone.value for phone in self.phones],
            "email": self.email.value if self.email else None,
            "address": self.address.value if self.address else None,
            "birthday": self.birthday.value.isoformat() if self.birthday else None,
        }

    @classmethod
    def from_dict(cls, data):
        if "first_name" in data:
            first, last = data["first_name"], data.get("last_name")
        else:  # формат версії 1: одне поле name
            first, _, last = collapse_spaces(data["name"]).partition(" ")
        record = cls(first, last or None, record_id=data.get("id"), strict=False)
        for phone in data.get("phones") or []:
            record.add_phone(phone)
        if data.get("email"):
            record.set_email(data["email"])
        if data.get("address"):
            record.address = Address.from_storage(data["address"])
        if data.get("birthday"):
            birthday = date.fromisoformat(data["birthday"])
            record.set_birthday(birthday.strftime(DATE_FORMAT))
        return record

    # --- виведення ---

    def short(self):
        return f"[{self.id}] {self.full_name}"

    def __str__(self):
        phones = ", ".join(p.value for p in self.phones) or "—"
        parts = [self.short(), f"тел.: {phones}"]
        if self.email is not None:
            parts.append(f"email: {self.email}")
        if self.birthday is not None:
            parts.append(f"д. н.: {self.birthday}")
        if self.address is not None:
            parts.append(f"адреса: {self.address}")
        return " | ".join(parts)

    def details(self):
        rows = [
            ("Ім'я", self.first_name),
            ("Прізвище", self.last_name or "—"),
            ("Телефони", ", ".join(p.value for p in self.phones) or "—"),
            ("Email", self.email or "—"),
            ("Адреса", self.address or "—"),
            ("День народження", self.birthday or "—"),
        ]
        lines = [f"Контакт #{self.id}"]
        lines.extend(f"  {label + ':':<17} {value}" for label, value in rows)
        return "\n".join(lines)


# ======================================================================
# Адресна книга
# ======================================================================

def _birthday_in_year(birthday, year):
    try:
        return birthday.replace(year=year)
    except ValueError:  # 29 лютого в невисокосний рік
        return birthday.replace(year=year, day=28)


def next_birthday(birthday, today):
    this_year = _birthday_in_year(birthday, today.year)
    if this_year < today:
        return _birthday_in_year(birthday, today.year + 1)
    return this_year


class AddressBook:
    """Книга контактів. Ключ запису — числовий id, а не ім'я."""

    def __init__(self):
        self._records = {}
        self._next_id = 1

    def __len__(self):
        return len(self._records)

    def records(self):
        return [self._records[key] for key in sorted(self._records)]

    def add_record(self, record):
        record.id = self._next_id
        self._next_id += 1
        self._records[record.id] = record
        return record

    def get(self, record_id):
        return self._records.get(record_id)

    def find_by_name(self, full_name):
        """Усі контакти з таким ім'ям і прізвищем (без урахування регістру)."""
        wanted = collapse_spaces(full_name).casefold()
        return [r for r in self.records() if r.full_name.casefold() == wanted]

    def search(self, query):
        return [record for record in self.records() if record.matches(query)]

    def delete(self, record_id):
        return self._records.pop(record_id, None) is not None

    def get_upcoming_birthdays(self, days=7, today=None):
        """Дні народження в найближчі `days` днів (сьогодні й через `days` — включно).

        Якщо день народження припадає на вихідний, привітання переноситься на понеділок.
        """
        today = today or date.today()
        found = []
        for record in self.records():
            if record.birthday is None:
                continue
            birthday_date = next_birthday(record.birthday.value, today)
            if (birthday_date - today).days > days:
                continue
            congratulation_date = birthday_date
            weekday = birthday_date.weekday()
            if weekday >= 5:
                congratulation_date += timedelta(days=7 - weekday)
            found.append((congratulation_date, birthday_date, record))

        found.sort(key=lambda item: (item[1], item[2].full_name.casefold(), item[2].id))
        return [
            {
                "id": record.id,
                "name": record.full_name,
                "birthday": birthday_date.strftime(DATE_FORMAT),
                "congratulation_date": congratulation_date.strftime(DATE_FORMAT),
            }
            for congratulation_date, birthday_date, record in found
        ]

    # --- збереження ---

    def to_dict(self):
        return {
            "next_id": self._next_id,
            "records": [record.to_dict() for record in self.records()],
        }

    @classmethod
    def from_dict(cls, data, warnings=None):
        warnings = warnings if warnings is not None else []
        book = cls()
        items = data.get("records") if isinstance(data, dict) else None
        if not isinstance(items, list):
            if data:
                warnings.append("Розділ контактів пошкоджено, його пропущено.")
            return book

        for item in items:
            try:
                record = Record.from_dict(item)
            except (KeyError, ValueError, TypeError, AttributeError) as error:
                warnings.append(f"Пропущено пошкоджений контакт: {error}")
                continue
            if (type(record.id) is not int or record.id < 1) or record.id in book._records:
                warnings.append(f"Пропущено контакт «{record.full_name}»: невірний або повторний id.")
                continue
            if not record.names_are_valid():
                warnings.append(
                    f"Контакт {record.short()}: в імені чи прізвищі є цифри або інші "
                    "неприпустимі символи. Виправте: «Контакти» → «Змінити дані»."
                )
            if record.address is not None and not Address.is_valid(record.address.value):
                warnings.append(
                    f"Контакт {record.short()}: адреса «{record.address}» складається лише "
                    "з цифр. Виправте: «Контакти» → «Змінити дані»."
                )
            book._records[record.id] = record

        saved_next = data.get("next_id")
        saved_next = saved_next if isinstance(saved_next, int) else 1
        book._next_id = max(saved_next, max(book._records, default=0) + 1)
        return book


# ======================================================================
# Нотатки
# ======================================================================

MAX_TAG_LENGTH = 30


def validate_text(raw):
    text = collapse_spaces(raw)
    if not text:
        raise ValueError("Текст нотатки не може бути порожнім.")
    return text


def normalize_tag(raw):
    """'#Покупки' -> 'покупки'."""
    tag = str(raw).strip().lstrip("#").lower()
    if not tag:
        raise ValueError("Тег не може бути порожнім.")
    if len(tag) > MAX_TAG_LENGTH:
        raise ValueError(f"Тег задовгий (не більше {MAX_TAG_LENGTH} символів).")
    if re.search(r"[\s,;#]", tag):
        raise ValueError("У тезі не може бути пробілів, ком і знака #.")
    return tag


def parse_tags(raw):
    """'робота, #терміново дім' -> ['робота', 'терміново', 'дім'] (без повторів)."""
    tags = []
    for part in re.split(r"[\s,;]+", str(raw).strip()):
        if not part:
            continue
        tag = normalize_tag(part)
        if tag not in tags:
            tags.append(tag)
    return tags


def parse_tags_required(raw):
    tags = parse_tags(raw)
    if not tags:
        raise ValueError("Введіть хоча б один тег.")
    return tags


class Note:
    def __init__(self, text, tags=None, note_id=None, created=None):
        self.id = note_id
        self.text = validate_text(text)
        self.tags = []
        for tag in tags or []:
            self.add_tag(tag)
        self.created = created or datetime.now().replace(microsecond=0)

    def set_text(self, text):
        self.text = validate_text(text)

    def add_tag(self, tag):
        """True — тег додано, False — він уже був."""
        tag = normalize_tag(tag)
        if tag in self.tags:
            return False
        self.tags.append(tag)
        return True

    def remove_tag(self, tag):
        tag = normalize_tag(tag)
        if tag not in self.tags:
            raise ValueError(f"У нотатки {self.id} немає тегу #{tag}.")
        self.tags.remove(tag)

    def matches(self, query):
        query = str(query).strip().lower().lstrip("#")
        if not query:
            return False
        return query in self.text.lower() or any(query in tag for tag in self.tags)

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "tags": list(self.tags),
            "created": self.created.isoformat(),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["text"],
            tags=data.get("tags") or [],
            note_id=data.get("id"),
            created=datetime.fromisoformat(data["created"]) if data.get("created") else None,
        )

    def __str__(self):
        tags = " ".join(f"#{tag}" for tag in self.tags)
        header = f"[{self.id}] {self.created:%d.%m.%Y %H:%M}"
        if tags:
            header += f"  {tags}"
        return f"{header}\n    {self.text}"


class Notebook:
    def __init__(self):
        self._notes = {}
        self._next_id = 1

    def __len__(self):
        return len(self._notes)

    def notes(self):
        return [self._notes[key] for key in sorted(self._notes)]

    def add_note(self, text, tags=None):
        note = Note(text, tags=tags, note_id=self._next_id)
        self._notes[note.id] = note
        self._next_id += 1
        return note

    def get(self, note_id):
        return self._notes.get(note_id)

    def delete(self, note_id):
        return self._notes.pop(note_id, None) is not None

    def search(self, query):
        return [note for note in self.notes() if note.matches(query)]

    def by_tag(self, tag):
        tag = normalize_tag(tag)
        return [note for note in self.notes() if tag in note.tags]

    def all_tags(self):
        counts = {}
        for note in self.notes():
            for tag in note.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items()))

    def rename_tag(self, old, new):
        """Перейменовує тег в усіх нотатках. Повертає кількість нотаток."""
        old, new = normalize_tag(old), normalize_tag(new)
        count = 0
        for note in self.notes():
            if old not in note.tags:
                continue
            index = note.tags.index(old)
            if new in note.tags:  # такий тег уже є — просто об'єднуємо
                note.tags.pop(index)
            else:
                note.tags[index] = new
            count += 1
        return count

    def delete_tag(self, tag):
        """Прибирає тег з усіх нотаток (самі нотатки лишаються)."""
        tag = normalize_tag(tag)
        count = 0
        for note in self.notes():
            if tag in note.tags:
                note.tags.remove(tag)
                count += 1
        return count

    # --- збереження ---

    def to_dict(self):
        return {
            "next_id": self._next_id,
            "notes": [note.to_dict() for note in self.notes()],
        }

    @classmethod
    def from_dict(cls, data, warnings=None):
        warnings = warnings if warnings is not None else []
        notebook = cls()
        items = data.get("notes") if isinstance(data, dict) else None
        if not isinstance(items, list):
            if data:
                warnings.append("Розділ нотаток пошкоджено, його пропущено.")
            return notebook

        for item in items:
            try:
                note = Note.from_dict(item)
            except (KeyError, ValueError, TypeError, AttributeError) as error:
                warnings.append(f"Пропущено пошкоджену нотатку: {error}")
                continue
            if (type(note.id) is not int or note.id < 1) or note.id in notebook._notes:
                warnings.append("Пропущено нотатку з невірним або повторним id.")
                continue
            notebook._notes[note.id] = note

        saved_next = data.get("next_id")
        saved_next = saved_next if isinstance(saved_next, int) else 1
        notebook._next_id = max(saved_next, max(notebook._notes, default=0) + 1)
        return notebook


# ======================================================================
# Перенесення зі старого addressbook.pkl (версія до рефакторингу)
# ======================================================================
# Файл читається «безпечним» unpickler'ом: він створює лише порожні заглушки
# замість старих класів і не виконує довільний код із файлу.

LEGACY_FILENAME = "addressbook.pkl"
_LEGACY_CLASSES = {"Field", "Name", "Phone", "Birthday", "Record", "AddressBook"}


class _Stub:
    """Порожня заглушка: pickle заповнить її атрибутами."""


class _SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if name in _LEGACY_CLASSES and (
            module == "__main__" or module.startswith("personal_assistant")
        ):
            return _Stub
        if (module, name) == ("datetime", "date"):
            return legacy_datetime.date
        raise pickle.UnpicklingError(f"Заборонений об'єкт у старому файлі: {module}.{name}")


def find_legacy_file(data_dir):
    for candidate in (Path.cwd() / LEGACY_FILENAME, Path(data_dir) / LEGACY_FILENAME):
        if candidate.is_file():
            return candidate
    return None


def load_legacy_book(path, warnings):
    """Читає старий pickle і повертає нову AddressBook."""
    with open(path, "rb") as f:
        old_book = _SafeUnpickler(f).load()

    old_records = getattr(old_book, "data", None)
    if not isinstance(old_records, dict):
        raise ValueError("неочікувана структура старого файлу")

    book = AddressBook()
    for key, old in old_records.items():
        try:
            first, _, last = collapse_spaces(old.name.value).partition(" ")
            record = Record(first, last or None, strict=False)
        except (AttributeError, ValueError) as error:
            warnings.append(f"Пропущено старий контакт {key!r}: {error}")
            continue

        for old_phone in getattr(old, "phones", []) or []:
            try:
                record.add_phone(old_phone.value)
            except (AttributeError, ValueError) as error:
                warnings.append(f"{record.full_name}: пропущено телефон ({error})")

        old_birthday = getattr(old, "birthday", None)
        if old_birthday is not None:
            try:
                record.set_birthday(old_birthday.value.strftime(DATE_FORMAT))
            except (AttributeError, ValueError) as error:
                warnings.append(f"{record.full_name}: пропущено день народження ({error})")

        book.add_record(record)
    return book


# ======================================================================
# Зберігання даних
# ======================================================================

APP_DIR_NAME = ".personal_assistant"
DATA_FILENAME = "data.json"
DEMO_FILENAME = "demo.json"
ENV_DATA_DIR = "PERSONAL_ASSISTANT_HOME"
FORMAT_VERSION = 2


class StorageError(Exception):
    """Не вдалося зберегти дані."""


@dataclass
class LoadResult:
    book: AddressBook
    notebook: Notebook
    warnings: list = field(default_factory=list)
    migrated: bool = False
    seeded: bool = False  # навчальні контакти вже додавалися в цю книгу


def get_data_dir():
    custom = os.environ.get(ENV_DATA_DIR)
    return Path(custom) if custom else Path.home() / APP_DIR_NAME


def get_data_path():
    return get_data_dir() / DATA_FILENAME


def _backup_path(path):
    return path.with_name(path.name + ".bak")


def save_data(book, notebook, path=None):
    """Атомарний запис: у тимчасовий файл, потім заміна. Стара версія йде в .bak."""
    path = Path(path) if path else get_data_path()
    payload = {
        "version": FORMAT_VERSION,
        "seeded": True,
        "contacts": book.to_dict(),
        "notes": notebook.to_dict(),
    }
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            shutil.copy2(path, _backup_path(path))
        os.replace(tmp_path, path)
    except OSError as error:
        raise StorageError(f"Не вдалося зберегти дані в {path}: {error}") from error


def _read_json(path, warnings):
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError) as error:
        warnings.append(f"Не вдалося прочитати {path.name}: {error}")
        return None
    if not isinstance(payload, dict):
        warnings.append(f"Файл {path.name} має неочікувану структуру.")
        return None
    return payload


def _move_aside(path, suffix, warnings):
    """Перейменовує файл, щоб нове збереження його не затерло."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.{suffix}-{stamp}")
    try:
        path.rename(target)
        warnings.append(f"Старий файл збережено як {target.name}.")
    except OSError as error:
        warnings.append(f"Не вдалося перейменувати файл {path.name}: {error}")


def load_data(path=None):
    """Завантажує дані. Будь-яка проблема стає попередженням, а не падінням."""
    path = Path(path) if path else get_data_path()
    warnings = []

    if path.exists():
        payload = _read_json(path, warnings)
        if payload is None:
            backup = _backup_path(path)
            if backup.exists():
                payload = _read_json(backup, warnings)
                if payload is not None:
                    _move_aside(path, "corrupt", warnings)
                    warnings.append("Дані відновлено з резервної копії.")
            if payload is None:
                _move_aside(path, "corrupt", warnings)
        if payload is None:
            return LoadResult(AddressBook(), Notebook(), warnings)
        book = AddressBook.from_dict(payload.get("contacts"), warnings)
        notebook = Notebook.from_dict(payload.get("notes"), warnings)
        return LoadResult(book, notebook, warnings, seeded=bool(payload.get("seeded")))

    legacy_file = find_legacy_file(path.parent)
    if legacy_file is not None:
        try:
            book = load_legacy_book(legacy_file, warnings)
        except Exception as error:  # битий чи чужий файл не має зупиняти запуск
            warnings.append(f"Не вдалося імпортувати {legacy_file}: {error}")
        else:
            warnings.append(
                f"Імпортовано контактів із {legacy_file}: {len(book)}. "
                "Початковий файл не змінено."
            )
            return LoadResult(book, Notebook(), warnings, migrated=True)

    return LoadResult(AddressBook(), Notebook(), warnings)


# ======================================================================
# Навчальні контакти (усі дані вигадані)
# ======================================================================

DEMO_PEOPLE = [
    ("Анна", "Коваленко", "anna.kovalenko", "14.01.1988"),
    ("Олег", "Шевченко", "oleg.shevchenko", "03.02.1991"),
    ("Марія", "Бондаренко", "maria.bondarenko", "27.03.1985"),
    ("Дмитро", "Ткаченко", "dmytro.tkachenko", "09.04.1993"),
    ("Ольга", "Кравченко", "olga.kravchenko", "21.05.1979"),
    ("Сергій", "Мельник", "serhii.melnyk", "30.06.1990"),
    ("Ірина", "Бойко", "iryna.boiko", "11.07.1986"),
    ("Андрій", "Ковальчук", "andrii.kovalchuk", "05.08.1995"),
    ("Наталія", "Олійник", "natalia.oliinyk", "18.09.1982"),
    ("Максим", "Лисенко", "maksym.lysenko", "02.10.1998"),
    ("Катерина", "Руденко", "kateryna.rudenko", "25.11.1975"),
    ("Ігор", "Савченко", "ihor.savchenko", "08.12.1992"),
    ("Світлана", "Петренко", "svitlana.petrenko", "19.01.2000"),
    ("Віктор", "Марченко", "viktor.marchenko", "15.02.1984"),
    ("Юлія", "Павленко", "yulia.pavlenko", "07.03.1996"),
    ("Артем", "Козак", "artem.kozak", "22.04.1989"),
    ("Олена", "Гончаренко", "olena.honcharenko", "13.05.1981"),
    ("Павло", "Мороз", "pavlo.moroz", "26.06.1994"),
    ("Тетяна", "Клименко", "tetiana.klymenko", "04.07.1977"),
    ("Микола", "Литвиненко", "mykola.lytvynenko", "16.08.1990"),
    ("Аліна", "Демченко", "alina.demchenko", "29.09.1987"),
    ("Роман", "Ковтун", "roman.kovtun", "10.10.1983"),
    ("Людмила", "Сидоренко", "liudmyla.sydorenko", "23.11.1999"),
    ("Володимир", "Пономаренко", "volodymyr.ponomarenko", "31.12.1991"),
    ("Дарія", "Харченко", "daria.kharchenko", "01.06.1980"),
]
DEMO_PREFIXES = ["050", "063", "067", "073", "093", "095", "097", "098", "066", "099"]
DEMO_CITIES = ["Київ", "Львів", "Одеса", "Харків", "Дніпро"]
DEMO_STREETS = ["Садова", "Лісова", "Центральна", "Шевченка", "Миру"]
# У перших трьох контактів день народження найближчими днями, щоб
# «Найближчі дні народження» одразу щось показували.
DEMO_SOON_DAYS = (2, 4, 6)

# Навчальні контакти попередньої (російськомовної) версії — для перекладу.
OLD_DEMO_NAMES = [
    "Анна Коваленко", "Олег Шевченко", "Мария Бондаренко", "Дмитрий Ткаченко",
    "Ольга Кравченко", "Сергей Мельник", "Ирина Бойко", "Андрей Ковальчук",
    "Наталья Олейник", "Максим Лысенко", "Екатерина Руденко", "Игорь Савченко",
    "Светлана Петренко", "Виктор Марченко", "Юлия Павленко", "Артём Козак",
    "Елена Гончаренко", "Павел Мороз", "Татьяна Клименко", "Николай Литвиненко",
    "Алина Демченко", "Роман Ковтун", "Людмила Сидоренко", "Владимир Пономаренко",
    "Дарья Харченко",
]
OLD_DEMO_CITIES = ["Киев", "Львов", "Одесса", "Харьков", "Днепр"]
OLD_DEMO_STREETS = ["Садовая", "Лесная", "Центральная", "Шевченко", "Мира"]


def demo_address(index):
    return (
        f"{DEMO_CITIES[index % 5]}, вул. {DEMO_STREETS[index % 5]}, {index + 3}"
    )


def old_demo_address(index):
    return (
        f"{OLD_DEMO_CITIES[index % 5]}, ул. {OLD_DEMO_STREETS[index % 5]}, {index + 3}"
    )


def demo_records(today=None):
    today = today or date.today()
    records = []
    for i, (first, last, login, birthday) in enumerate(DEMO_PEOPLE):
        record = Record(first, last)
        phone = DEMO_PREFIXES[i % len(DEMO_PREFIXES)] + f"{4100000 + i * 1379:07d}"
        record.add_phone("+38" + phone if i % 4 == 3 else phone)
        record.set_email(f"{login}@example.com")
        record.set_address(demo_address(i))
        if i < len(DEMO_SOON_DAYS):
            soon = today + timedelta(days=DEMO_SOON_DAYS[i])
            birthday = date(1992, soon.month, soon.day).strftime(DATE_FORMAT)  # 1992 — високосний
        record.set_birthday(birthday)
        records.append(record)
    return records


def seed_demo_contacts(book):
    records = demo_records()
    for record in records:
        book.add_record(record)
    return len(records)


def translate_old_demo_contacts(book):
    """Перекладає навчальні контакти попередньої версії українською.

    Змінює лише ті імена й адреси, які користувач не редагував.
    """
    by_email = {f"{login}@example.com": i for i, (_, _, login, _) in enumerate(DEMO_PEOPLE)}
    changed = 0
    for record in book.records():
        index = by_email.get(record.email.value if record.email else None)
        if index is None:
            continue
        touched = False
        first, last = DEMO_PEOPLE[index][:2]
        if record.full_name == OLD_DEMO_NAMES[index] != f"{first} {last}":
            record.first_name = Name(first, "Ім'я")
            record.last_name = Name(last, "Прізвище")
            touched = True
        if record.address is not None and record.address.value == old_demo_address(index):
            record.address = Address(demo_address(index))
            touched = True
        changed += touched
    return changed


def prepare_demo():
    """Окрема навчальна книга demo.json. Файл старого формату відкладається вбік."""
    path = get_data_dir() / DEMO_FILENAME
    if path.exists():
        payload = _read_json(path, [])
        if payload and payload.get("version") == FORMAT_VERSION and payload.get("seeded"):
            return path
        _move_aside(path, "old", [])
    book = AddressBook()
    seed_demo_contacts(book)
    save_data(book, Notebook(), path)
    return path


# ======================================================================
# Термінал: кольори, введення й виведення
# ======================================================================

COLORS = {
    "title": "1;35",    # вітання й заголовки — пурпуровий
    "menu": "36",       # пункти меню — бірюзовий
    "prompt": "1;34",   # запитання — синій
    "info": "32",       # результати — зелений
    "success": "1;32",  # успішна зміна — яскраво-зелений
    "warning": "33",    # попередження — жовтий
    "error": "1;31",    # помилки — червоний
}


def _enable_windows_ansi():
    """Вмикає підтримку кольорів у консолі Windows 10+."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):  # stdout, stderr
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def detect_color():
    if "NO_COLOR" in os.environ:
        return False
    wanted = (
        sys.stdout.isatty()
        or bool(os.environ.get("FORCE_COLOR"))
        or bool(os.environ.get("PYCHARM_HOSTED"))
    )
    if wanted:
        _enable_windows_ansi()
    return wanted


def _stdout_write(text):
    sys.stdout.write(text)
    sys.stdout.flush()  # запитання має з'явитися до того, як програма чекає введення


class GoBack(Exception):
    """Назад до попереднього меню (0)."""


class GoMain(Exception):
    """Одразу до головного меню."""


class SessionEnd(Exception):
    """Завершити сеанс (вибір користувача або кінець введення)."""


SKIP = object()  # Enter у списку «без вибору»


class Result:
    """Результат дії: рядки з типом оформлення."""

    def __init__(self):
        self.lines = []

    def add(self, text, kind="info"):
        self.lines.append((str(text), kind))
        return self

    @classmethod
    def info(cls, text):
        return cls().add(text, "info")

    @classmethod
    def ok(cls, text):
        return cls().add(text, "success")

    @classmethod
    def warning(cls, text):
        return cls().add(text, "warning")

    @classmethod
    def error(cls, text):
        return cls().add(text, "error")


class UI:
    def __init__(self, read=input, write=None, color=None):
        self._read = read
        self._write = write or _stdout_write
        self.color = detect_color() if color is None else color

    def paint(self, text, kind):
        code = COLORS.get(kind)
        if not self.color or not code:
            return text
        # Фарбуємо кожен рядок окремо, щоб колір не «протікав» далі.
        return "\n".join(
            f"\033[{code}m{line}\033[0m" if line else line for line in text.split("\n")
        )

    def say(self, text="", kind="info"):
        self._write(self.paint(str(text), kind) + "\n")

    def show(self, result):
        for text, kind in result.lines:
            self.say(text, kind)

    def ask(self, prompt, cancellable=True):
        """Ставить запитання. 0 усередині дії — назад."""
        self._write(self.paint(prompt, "prompt"))
        try:
            value = self._read()
        except EOFError:
            self._write("\n")
            raise SessionEnd() from None
        value = value.strip()
        if cancellable and value == "0":
            raise GoBack()
        return value

    def choose(self, title, options, nav="full", allow_empty=False):
        """Нумерований вибір. options: [(підпис, значення)].

        nav="full":    + «Головне меню», «Завершити сеанс», 0 — «Назад»
        nav="section": + «Завершити сеанс», 0 — «Назад до головного меню» (повертає None)
        nav="main":    0 — «Вийти» (повертає None)
        nav="cancel":  0 — «Назад»
        nav="none":    без додаткових пунктів
        allow_empty:   Enter повертає SKIP.
        """
        count = len(options)
        extra = []
        zero = None
        if nav == "full":
            extra = [("Головне меню", GoMain), ("Завершити сеанс", SessionEnd)]
            zero = ("Назад", GoBack)
        elif nav == "section":
            extra = [("Завершити сеанс", SessionEnd)]
            zero = ("Назад до головного меню", None)
        elif nav == "main":
            zero = ("Вийти", None)
        elif nav == "cancel":
            zero = ("Назад", GoBack)

        self.say()
        self.say(title, "title")
        lines = [f"  {i}. {label}" for i, (label, _) in enumerate(options, 1)]
        lines.extend(f"  {count + i}. {label}" for i, (label, _) in enumerate(extra, 1))
        if zero:
            lines.append(f"  0. {zero[0]}")
        self.say("\n".join(lines), "menu")

        lowest = 0 if zero else 1
        highest = count + len(extra)
        prompt = "Введіть число" + (" (Enter — без вибору)" if allow_empty else "") + ": "
        while True:
            raw = self.ask(prompt, cancellable=False)
            if not raw and allow_empty:
                return SKIP
            if raw.isascii() and raw.isdigit():
                number = int(raw)
                if number == 0 and zero:
                    if zero[1] is None:
                        return None
                    raise zero[1]()
                if 1 <= number <= count:
                    return options[number - 1][1]
                if count < number <= highest:
                    raise extra[number - count - 1][1]()
            self.say(f"Помилка: введіть число від {lowest} до {highest}.", "error")


def ask_value(ui, label, factory, hint=None, optional=False, skip_hint="Enter — пропустити"):
    """Запитує значення, доки воно не пройде перевірку.

    hint — приклад або формат, показується одразу в запитанні.
    Порожнє введення: None для необов'язкового поля, інакше запитання повторюється.
    """
    notes = [part for part in (hint, skip_hint if optional else None) if part]
    prompt = f"{label} ({'; '.join(notes)}): " if notes else f"{label}: "
    while True:
        raw = ui.ask(prompt)
        if not raw:
            if optional:
                return None
            ui.say("Це поле обов'язкове. Введіть значення або 0, щоб повернутися.", "error")
            continue
        try:
            return factory(raw)
        except ValueError as error:
            ui.say(str(error), "error")


def parse_days(raw):
    try:
        days = int(raw)
    except ValueError:
        raise ValueError("Введіть ціле число днів від 1 до 366.") from None
    if not 1 <= days <= 366:
        raise ValueError("Кількість днів має бути від 1 до 366.")
    return days


def format_notes(notes):
    return "\n".join(str(note) for note in notes)


def short_list(records):
    return "\n".join(f"  {record.short()}" for record in records)


def days_word(days):
    return plural(days, "день", "дні", "днів")


def when_text(days):
    if days == 0:
        return "сьогодні"
    if days == 1:
        return "завтра"
    return f"через {days} {days_word(days)}"


# Поля контакту: ключ -> (назва, підказка з прикладом, перевірка)
FIELDS = {
    "first_name": ("Ім'я", "наприклад: Олена", lambda value: Name(value, "Ім'я")),
    "last_name": ("Прізвище", "наприклад: Коваленко", lambda value: Name(value, "Прізвище")),
    "phone": (
        "Телефон",
        "10 цифр, наприклад 0501234567, або міжнародний формат +380501234567",
        Phone,
    ),
    "email": ("Email", "наприклад: olena@example.com", Email),
    "address": ("Адреса", "наприклад: Київ, вул. Садова, 12", Address),
    "birthday": ("День народження", "ДД.ММ.РРРР, наприклад: 05.03.1990", Birthday),
}


def ask_field(ui, key, optional=False, label=None, factory=None):
    name, hint, check = FIELDS[key]
    return ask_value(ui, label or name, factory or check, hint=hint, optional=optional)


# ======================================================================
# Застосунок: меню й дії
# ======================================================================

class App:
    def __init__(self, ui, book, notebook, data_path=None):
        self.ui = ui
        self.book = book
        self.notebook = notebook
        self.data_path = data_path

    # --- збереження ---

    def save(self):
        try:
            save_data(self.book, self.notebook, self.data_path)
        except StorageError as error:
            self.ui.say(f"Попередження: {error}", "warning")
            return False
        return True

    def changed(self):
        """Зберігаємо одразу після зміни — щоб нічого не втратити в разі збою."""
        self.save()

    # --- головний цикл ---

    def sections(self):
        return [
            ("Контакти", [
                ("Додати контакт", self.add_contact),
                ("Усі контакти", self.show_all_contacts),
                ("Знайти контакт", self.search_contacts),
                ("Змінити дані", self.edit_contact),
            ]),
            ("Дні народження", [
                ("Встановити день народження", self.set_birthday),
                ("Показати день народження", self.show_birthday),
                ("Найближчі дні народження (від 1 до 366 днів)", self.upcoming_birthdays),
            ]),
            ("Нотатки", [
                ("Додати нотатку", self.add_note),
                ("Усі нотатки", self.show_all_notes),
                ("Знайти нотатку", self.search_notes),
            ]),
            ("Теги", [
                ("Усі теги", self.show_all_tags),
                ("Додати тег", self.add_tag),
            ]),
        ]

    def loop(self):
        sections = self.sections()
        try:
            while True:
                section = self.ui.choose(
                    "Головне меню",
                    [(title, (title, actions)) for title, actions in sections],
                    nav="main",
                )
                if section is None:
                    break
                title, actions = section
                if self.run_section(title, actions):
                    break
        except (SessionEnd, KeyboardInterrupt):
            self.ui.say()
        self.finish()

    def run_section(self, title, actions):
        """Повертає True, якщо користувач вирішив завершити сеанс."""
        while True:
            handler = self.ui.choose(f"Меню «{title}»", actions, nav="section")
            if handler is None:
                return False
            try:
                result = handler()
            except GoBack:
                self.ui.say(f"Повернення до меню «{title}».", "warning")
                continue
            except KeyboardInterrupt:
                self.ui.say("\nДію скасовано.", "warning")
                continue
            except GoMain:
                return False
            except SessionEnd:
                raise
            except ValueError as error:
                result = Result.error(str(error))
            except Exception as error:  # страховка: одна помилка не має зупиняти програму
                result = Result.error(f"Неочікувана помилка: {error}")
            if result is not None:
                self.ui.show(result)
            return self.ask_finish()

    def ask_finish(self):
        return self.ui.choose(
            "Повернутися до головного меню чи завершити сеанс?",
            [("Головне меню", False), ("Завершити сеанс", True)],
            nav="none",
        )

    def finish(self):
        if self.save():
            self.ui.say("Зміни збережено. До побачення!", "success")
        else:
            self.ui.say("До побачення!", "title")

    # --- спільні запитання ---

    def confirm(self, question):
        return self.ui.choose(question, [("Так", True), ("Ні", False)], nav="cancel")

    def pick_contact(self):
        if not len(self.book):
            raise ValueError("Адресна книга порожня. Спочатку додайте контакт.")
        while True:
            raw = self.ui.ask(
                "Оберіть контакт: ID, ім'я та прізвище або телефон "
                "(наприклад: 5 або Олена Коваленко; Enter — список, 0 — назад): "
            )
            if not raw:
                self.ui.say(short_list(self.book.records()), "info")
                continue
            if raw.isdigit() and len(raw) <= 6:
                record = self.book.get(int(raw))
                if record is not None:
                    self.ui.say(f"Обрано контакт: {record.short()}", "info")
                    return record
                self.ui.say(f"Контакт з ID {raw} не знайдено.", "error")
                continue
            found = self.book.search(raw)
            if len(found) == 1:
                self.ui.say(f"Обрано контакт: {found[0].short()}", "info")
                return found[0]
            if not found:
                self.ui.say(f"За запитом «{raw}» нічого не знайдено.", "error")
                continue
            self.ui.say("Знайдено кілька контактів — введіть ID потрібного:", "warning")
            self.ui.say(short_list(found), "info")

    def pick_note(self):
        if not len(self.notebook):
            raise ValueError("Нотаток поки немає. Спочатку додайте нотатку в розділі «Нотатки».")
        while True:
            raw = self.ui.ask("ID нотатки (Enter — список, 0 — назад): ")
            if not raw:
                self.ui.say(format_notes(self.notebook.notes()), "info")
                continue
            note = self.notebook.get(int(raw)) if raw.isdigit() else None
            if note is not None:
                return note
            self.ui.say("Помилка: введіть ID нотатки зі списку.", "error")

    # --- Контакти ---

    def add_contact(self):
        self.ui.say("Новий контакт. 0 — назад у будь-який момент.", "title")
        first = ask_field(self.ui, "first_name")
        last = ask_field(self.ui, "last_name", optional=True)

        full_name = first.value if last is None else f"{first.value} {last.value}"
        same = self.book.find_by_name(full_name)
        if same:
            ids = ", ".join(str(record.id) for record in same)
            self.ui.say(f"Увага: контакт із таким ім'ям уже є (ID {ids}).", "warning")

        record = Record(first.value, last.value if last else None)
        phone = ask_field(self.ui, "phone", optional=True)
        email = ask_field(self.ui, "email", optional=True)
        address = ask_field(self.ui, "address", optional=True)
        birthday = ask_field(self.ui, "birthday", optional=True)

        if phone:
            record.add_phone(phone.value)
        if email:
            record.set_email(email.value)
        if address:
            record.set_address(address.value)
        if birthday:
            record.set_birthday(str(birthday))
        self.book.add_record(record)
        self.changed()
        return Result.ok(f"Контакт додано (ID {record.id}).").add(record.details())

    def show_all_contacts(self):
        records = self.book.records()
        if not records:
            return Result.info("Адресна книга порожня.")
        header = f"Усі контакти ({len(records)}):"
        return Result.info(header + "\n" + "\n".join(str(record) for record in records))

    def search_contacts(self):
        query = ask_value(
            self.ui, "Що знайти? Введіть ім'я та прізвище", str,
            hint="наприклад: Олена Коваленко; можна також телефон, email, адресу чи дату",
        )
        found = self.book.search(query)
        if not found:
            return Result.warning(f"За запитом «{query}» нічого не знайдено.")
        header = f"Знайдено: {len(found)}"
        return Result.info(header + "\n" + "\n".join(str(record) for record in found))

    def edit_contact(self):
        record = self.pick_contact()
        items = [(label, key) for key, (label, _, _) in FIELDS.items()]
        items += [("Додати номер до контакту", "add_phone"), ("Видалити контакт", "delete")]
        while True:
            self.ui.say(record.details(), "info")
            choice = self.ui.choose(f"Що змінити в контакті {record.short()}?", items)
            try:
                if choice == "add_phone":
                    return self._add_phone(record)
                if choice == "delete":
                    return self._delete_contact(record)
                return self._edit_field(record, choice)
            except GoBack:  # назад до списку полів цього контакту
                continue

    def _edit_field(self, record, key):
        label = FIELDS[key][0]
        action = self.ui.choose(
            f"Поле «{label}»: що зробити?", [("Замінити", "replace"), ("Видалити", "delete")]
        )
        if key == "phone":
            if action == "replace":
                return self._replace_phone(record)
            return self._delete_phone(record)

        current = getattr(record, key)
        setter = getattr(record, f"set_{key}")

        if action == "delete":
            if key == "first_name":
                return Result.error(NAME_REQUIRED_MESSAGE)
            if current is None:
                return Result.warning(f"Поле «{label}» вже порожнє — видаляти нічого.")
            if not self.confirm(f"Видалити поле «{label}» («{current}») у контакту {record.full_name}?"):
                return Result.warning("Видалення скасовано.")
            setter(None)
            self.changed()
            return Result.ok(f"Поле «{label}» видалено.").add(record.details())

        self.ui.say(f"Зараз: {current if current is not None else '—'}", "info")
        new_value = ask_field(self.ui, key, label=f"Нове значення — {label}")
        setter(str(new_value))
        self.changed()
        return Result.ok(f"Поле «{label}» оновлено.").add(record.details())

    def _choose_phone(self, record, question):
        if len(record.phones) == 1:
            self.ui.say(f"Номер: {record.phones[0].value}", "info")
            return record.phones[0]
        return self.ui.choose(question, [(phone.value, phone) for phone in record.phones])

    def _add_phone(self, record):
        phone = ask_field(self.ui, "phone", label="Новий телефон", factory=record.check_new_phone)
        record.add_phone(phone.value)
        self.changed()
        return Result.ok(f"Номер {phone.value} додано до контакту {record.short()}.")

    def _replace_phone(self, record):
        if not record.phones:
            self.ui.say("У контакту немає телефонів — введений номер буде додано.", "warning")
            return self._add_phone(record)
        old = self._choose_phone(record, "Який номер замінити?")
        new = ask_field(
            self.ui, "phone", label="Новий телефон",
            factory=lambda value: record.check_new_phone(value, skip_phone=old),
        )
        old_value = old.value
        record.edit_phone(old_value, new.value)
        self.changed()
        return Result.ok(f"Номер {old_value} замінено на {new.value}.")

    def _delete_phone(self, record):
        if not record.phones:
            return Result.warning("У контакту немає телефонів — видаляти нічого.")
        phone = self._choose_phone(record, "Який номер видалити?")
        if not self.confirm(f"Видалити номер {phone.value} у контакту {record.full_name}?"):
            return Result.warning("Видалення скасовано.")
        record.remove_phone(phone.value)
        self.changed()
        return Result.ok(f"Номер {phone.value} видалено.")

    def _delete_contact(self, record):
        if not self.confirm(f"Видалити контакт {record.short()}?"):
            return Result.warning("Видалення скасовано.")
        self.book.delete(record.id)
        self.changed()
        return Result.ok(f"Контакт {record.short()} видалено.")

    # --- Дні народження ---

    def set_birthday(self):
        record = self.pick_contact()
        current = record.birthday if record.birthday is not None else "не вказано"
        self.ui.say(f"Поточний день народження: {current}", "info")
        birthday = ask_field(self.ui, "birthday")
        record.set_birthday(str(birthday))
        self.changed()
        return Result.ok(f"День народження {record.full_name} встановлено: {birthday}.")

    def show_birthday(self):
        record = self.pick_contact()
        if record.birthday is None:
            return Result.warning(f"У контакту {record.full_name} день народження не вказано.")
        today = date.today()
        upcoming = next_birthday(record.birthday.value, today)
        days = (upcoming - today).days
        age = upcoming.year - record.birthday.value.year
        return Result.info(
            f"{record.full_name}: {record.birthday}\n"
            f"Наступний день народження {upcoming.strftime(DATE_FORMAT)} ({when_text(days)}), "
            f"виповниться {age} {plural(age, 'рік', 'роки', 'років')}."
        )

    def upcoming_birthdays(self):
        days = ask_value(
            self.ui, "За скільки днів показати", parse_days,
            hint="від 1 до 366", optional=True, skip_hint="Enter — 7",
        ) or 7
        upcoming = self.book.get_upcoming_birthdays(days)
        period = f"{days} {days_word(days)}"
        if not upcoming:
            return Result.info(f"У найближчі {period} днів народження немає.")
        lines = [f"Дні народження в найближчі {period}:"]
        for entry in upcoming:
            line = f"  {entry['birthday']} — {entry['name']} (ID {entry['id']})"
            if entry["congratulation_date"] != entry["birthday"]:
                line += f", вихідний: привітати {entry['congratulation_date']}"
            lines.append(line)
        return Result.info("\n".join(lines))

    # --- Нотатки ---

    def add_note(self):
        self.ui.say("Нова нотатка. 0 — назад у будь-який момент.", "title")
        text = ask_value(self.ui, "Текст", validate_text, hint="наприклад: Купити молоко")
        tags = ask_value(
            self.ui, "Теги через пробіл або кому", parse_tags,
            hint="наприклад: дім, покупки", optional=True,
        )
        note = self.notebook.add_note(text, tags or [])
        self.changed()
        return Result.ok(f"Нотатку додано (ID {note.id}).").add(str(note))

    def _select_and_act(self, notes):
        """Після списку нотаток: обрати нотатку й змінити чи видалити її."""
        ids = {note.id for note in notes}
        while True:
            raw = self.ui.ask(
                "ID нотатки, щоб змінити чи видалити (Enter — нічого не обирати, 0 — назад): "
            )
            if not raw:
                return None
            if not (raw.isdigit() and int(raw) in ids):
                self.ui.say("Помилка: введіть ID однієї з показаних нотаток.", "error")
                continue

            note = self.notebook.get(int(raw))
            self.ui.say(str(note), "info")
            try:
                action = self.ui.choose(
                    f"Нотатка [{note.id}]: що зробити?",
                    [("Змінити нотатку", "edit"), ("Видалити нотатку", "delete")],
                )
                if action == "edit":
                    new_text = ask_value(self.ui, "Новий текст", validate_text)
                    note.set_text(new_text)
                    self.changed()
                    return Result.ok("Нотатку змінено.").add(str(note))
                if not self.confirm(f"Видалити нотатку [{note.id}] «{note.text}»?"):
                    return Result.warning("Видалення скасовано.")
            except GoBack:  # назад до вибору нотатки
                continue
            self.notebook.delete(note.id)
            self.changed()
            return Result.ok(f"Нотатку [{note.id}] видалено.")

    def show_all_notes(self):
        notes = self.notebook.notes()
        if not notes:
            return Result.info("Нотаток поки немає.")
        self.ui.say(f"Усі нотатки ({len(notes)}):\n" + format_notes(notes), "info")
        return self._select_and_act(notes)

    def search_notes(self):
        if not len(self.notebook):
            return Result.info("Нотаток поки немає.")
        query = ask_value(
            self.ui, "Що знайти", str, hint="текст або тег, наприклад: молоко чи #дім"
        )
        found = self.notebook.search(query)
        if not found:
            return Result.warning(f"За запитом «{query}» нотаток не знайдено.")
        self.ui.say(f"Знайдено нотаток: {len(found)}\n" + format_notes(found), "info")
        return self._select_and_act(found)

    # --- Теги ---

    def show_all_tags(self):
        while True:
            tags = self.notebook.all_tags()
            if not tags:
                return Result.info("Тегів поки немає. Додайте тег: «Теги» → «Додати тег».")
            options = [
                (f"#{tag} — {count} {plural(count, 'нотатка', 'нотатки', 'нотаток')}", tag)
                for tag, count in tags.items()
            ]
            tag = self.ui.choose(
                "Усі теги. Оберіть тег, щоб змінити чи видалити його",
                options, allow_empty=True,
            )
            if tag is SKIP:
                return None
            try:
                return self._tag_action(tag, tags[tag], tags)
            except GoBack:  # назад до списку тегів
                continue

    def _tag_action(self, tag, count, tags):
        self.ui.say(f"Нотатки з тегом #{tag}:\n" + format_notes(self.notebook.by_tag(tag)), "info")
        action = self.ui.choose(
            f"Тег #{tag}: що зробити?", [("Змінити тег", "rename"), ("Видалити тег", "delete")]
        )
        where = f"{count} {plural(count, 'нотатці', 'нотатках', 'нотатках')}"

        if action == "rename":
            new_tag = ask_value(
                self.ui, "Нова назва тегу", normalize_tag, hint="одне слово, наприклад: робота"
            )
            if new_tag == tag:
                return Result.warning("Назва тегу не змінилася.")
            merged = new_tag in tags
            self.notebook.rename_tag(tag, new_tag)
            self.changed()
            message = f"Тег #{tag} перейменовано на #{new_tag} у {where}."
            if merged:
                message += f" Тег #{new_tag} уже був — теги об'єднано."
            return Result.ok(message)

        if not self.confirm(f"Видалити тег #{tag} у {where}? Самі нотатки залишаться."):
            return Result.warning("Видалення скасовано.")
        self.notebook.delete_tag(tag)
        self.changed()
        return Result.ok(f"Тег #{tag} видалено.")

    def add_tag(self):
        note = self.pick_note()
        self.ui.say(str(note), "info")
        tags = ask_value(
            self.ui, "Теги через пробіл або кому", parse_tags_required,
            hint="наприклад: робота, терміново",
        )
        added = [tag for tag in tags if note.add_tag(tag)]
        if not added:
            return Result.warning("Ці теги вже є в нотатки.")
        self.changed()
        return Result.ok("Додано теги: " + " ".join(f"#{tag}" for tag in added)).add(str(note))


# ======================================================================
# Запуск
# ======================================================================

GREETING = "Ласкаво просимо до персонального помічника!"


def run(read=input, write=None, data_path=None, color=None, demo=False):
    ui = UI(read, write, color)
    result = load_data(data_path)

    ui.say(GREETING, "title")
    ui.say("Контакти, дні народження, нотатки й теги. "
           "Обирайте пункти цифрами; 0 — назад.", "menu")
    if demo:
        ui.say(f"Відкрито навчальну книгу: {data_path}", "warning")
    for warning in result.warnings:
        ui.say(f"Попередження: {warning}", "warning")

    app = App(ui, result.book, result.notebook, data_path)
    need_save = result.migrated
    if not result.seeded and len(result.book) == 0:
        added = seed_demo_contacts(result.book)
        ui.say(f"До адресної книги додано {added} навчальних контактів (дані вигадані).", "success")
        need_save = True
    translated = translate_old_demo_contacts(result.book)
    if translated:
        ui.say(f"Навчальні контакти перекладено українською: {translated}.", "success")
        need_save = True
    if need_save:
        app.save()

    app.loop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Контакти, дні народження, нотатки й теги")
    parser.add_argument("--demo", action="store_true",
                        help="окрема навчальна книга з 25 вигаданими контактами")
    parser.add_argument("--no-color", action="store_true", help="виведення без кольорів")
    args = parser.parse_args(argv)
    color = False if args.no_color else None
    try:
        data_path = prepare_demo() if args.demo else None
        run(data_path=data_path, color=color, demo=args.demo)
    except StorageError as error:
        UI(color=color).say(str(error), "error")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
