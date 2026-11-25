# -*- coding: utf-8 -*-
# Python 3.10+; запуск: python personal_assistant.py
# Учебные контакты: python personal_assistant.py --demo


# models/fields.py
import re
from datetime import date, datetime

DATE_FORMAT = "%d.%m.%Y"
MIN_BIRTH_YEAR = 1900

# 10 цифр (0501234567) или международный формат (+380501234567).
PHONE_PATTERN = re.compile(r"[0-9]{10}|\+[0-9]{11,15}")
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)
BIRTHDAY_PATTERN = re.compile(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}")


def normalize_phone(value):
    """Убирает пробелы, дефисы, скобки и точки: '050 123-45-67' -> '0501234567'."""
    return re.sub(r"[\s\-().]", "", str(value))


class Field:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Name(Field):
    def __init__(self, value):
        value = " ".join(str(value).split()) if value is not None else ""
        if not value:
            raise ValueError("The name field is required.")
        if not all(char.isalpha() or char == " " for char in value):
            raise ValueError("Имя и фамилия могут содержать только буквы и пробелы.")
        super().__init__(value)


class Phone(Field):
    def __init__(self, value):
        normalized = normalize_phone(value)
        if not PHONE_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Invalid phone. Use 10 digits (0501234567) or "
                "international format (+380501234567)."
            )
        super().__init__(normalized)


class Email(Field):
    def __init__(self, value):
        value = str(value).strip()
        if len(value) > 254 or not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Invalid email. Example: name@example.com")
        super().__init__(value)


class Address(Field):
    def __init__(self, value):
        value = " ".join(str(value).split()) if value is not None else ""
        if not value:
            raise ValueError("The address cannot be empty.")
        super().__init__(value)


class Birthday(Field):
    def __init__(self, value):
        error_message = "Invalid date format. Use DD.MM.YYYY"

        if not isinstance(value, str) or not BIRTHDAY_PATTERN.fullmatch(value.strip()):
            raise ValueError(error_message)

        try:
            birthday = datetime.strptime(value.strip(), DATE_FORMAT).date()
        except ValueError as error:
            raise ValueError(error_message) from error

        if birthday > date.today():
            raise ValueError("Birthday cannot be in the future.")
        if birthday.year < MIN_BIRTH_YEAR:
            raise ValueError(f"Birthday year must be {MIN_BIRTH_YEAR} or later.")

        super().__init__(birthday)

    def __str__(self):
        return self.value.strftime(DATE_FORMAT)


# models/contact.py
from datetime import date



class Record:
    """Один контакт. id выдаёт AddressBook при добавлении."""

    def __init__(self, name, record_id=None, surname=None):
        self.id = record_id
        self.name = Name(name)
        self.surname = Name(surname) if surname else None
        self.phones = []
        self.email = None
        self.address = None
        self.birthday = None

    # --- простые поля (None очищает значение) ---

    def set_name(self, name):
        self.name = Name(name)

    def set_surname(self, surname):
        self.surname = Name(surname) if surname is not None else None

    @property
    def full_name(self):
        return f"{self.name} {self.surname}" if self.surname else str(self.name)

    def set_email(self, email):
        self.email = None if email is None else Email(email)

    def set_address(self, address):
        self.address = None if address is None else Address(address)

    def set_birthday(self, birthday):
        self.birthday = None if birthday is None else Birthday(birthday)

    def add_birthday(self, birthday):
        self.set_birthday(birthday)

    # --- телефоны ---

    def _ensure_unique_phone(self, new_phone, skip_phone=None):
        for phone_obj in self.phones:
            if phone_obj is skip_phone:
                continue
            if phone_obj.value == new_phone.value:
                raise ValueError(
                    f"This contact already has the phone number {new_phone.value}."
                )

    def add_phone(self, phone):
        new_phone = Phone(phone)
        self._ensure_unique_phone(new_phone)
        self.phones.append(new_phone)

    def remove_phone(self, phone):
        phone_obj = self.find_phone(phone)
        if phone_obj is None:
            raise ValueError(f"Phone {phone} not found.")
        self.phones.remove(phone_obj)

    def edit_phone(self, old_phone, new_phone):
        phone_obj = self.find_phone(old_phone)
        if phone_obj is None:
            raise ValueError(f"Phone {old_phone} not found.")

        new_phone_obj = Phone(new_phone)
        self._ensure_unique_phone(new_phone_obj, skip_phone=phone_obj)

        index = self.phones.index(phone_obj)
        self.phones[index] = new_phone_obj

    def find_phone(self, phone):
        phone = normalize_phone(phone)
        for phone_obj in self.phones:
            if phone_obj.value == phone:
                return phone_obj
        return None

    # --- поиск ---

    def matches(self, query):
        """Есть ли query (без учёта регистра) в имени, телефонах, email, адресе, дате."""
        query = str(query).strip().lower()
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

    # --- сохранение ---

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name.value,
            "surname": self.surname.value if self.surname else None,
            "phones": [phone.value for phone in self.phones],
            "email": self.email.value if self.email else None,
            "address": self.address.value if self.address else None,
            "birthday": self.birthday.value.isoformat() if self.birthday else None,
        }

    @classmethod
    def from_dict(cls, data):
        record = cls(data["name"], record_id=data.get("id"), surname=data.get("surname"))
        for phone in data.get("phones") or []:
            record.add_phone(phone)
        if data.get("email"):
            record.set_email(data["email"])
        if data.get("address"):
            record.set_address(data["address"])
        if data.get("birthday"):
            birthday = date.fromisoformat(data["birthday"])
            record.set_birthday(birthday.strftime(DATE_FORMAT))
        return record

    # --- вывод ---

    def __str__(self):
        phones = "; ".join(p.value for p in self.phones) or "no phones"
        parts = [f"[{self.id}] {self.full_name}", f"phones: {phones}"]
        if self.email is not None:
            parts.append(f"email: {self.email}")
        if self.address is not None:
            parts.append(f"address: {self.address}")
        if self.birthday is not None:
            parts.append(f"birthday: {self.birthday}")
        return " | ".join(parts)

    def details(self):
        phones = "; ".join(p.value for p in self.phones) or "-"
        return "\n".join(
            [
                f"Contact #{self.id}",
                f"  Name:     {self.name}",
                f"  Phones:   {phones}",
                f"  Email:    {self.email or '-'}",
                f"  Address:  {self.address or '-'}",
                f"  Birthday: {self.birthday or '-'}",
            ]
        )


# models/address_book.py
from datetime import date, timedelta



def _birthday_in_year(birthday, year):
    try:
        return birthday.replace(year=year)
    except ValueError:  # 29 февраля в невисокосный год
        return birthday.replace(year=year, day=28)


def _next_birthday(birthday, today):
    this_year = _birthday_in_year(birthday, today.year)
    if this_year < today:
        return _birthday_in_year(birthday, today.year + 1)
    return this_year


class AddressBook:
    """Книга контактов. Ключ записи: числовой id, а не имя."""

    def __init__(self):
        self._records = {}
        self._next_id = 1
        self.demo_initialized = False

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

    def find_by_name(self, name):
        """Все контакты с таким именем (без учёта регистра)."""
        wanted = " ".join(str(name).split()).casefold()
        return [r for r in self.records() if r.full_name.casefold() == wanted]

    def search(self, query):
        return [record for record in self.records() if record.matches(query)]

    def delete(self, record_id):
        return self._records.pop(record_id, None) is not None

    def get_upcoming_birthdays(self, days=7, today=None):
        """Дни рождения за days календарных дат, включая сегодня.

        Если день рождения выпадает на выходной, поздравление переносится на понедельник.
        """
        today = today or date.today()
        if type(days) is not int or not 1 <= days <= 366:
            raise ValueError("Количество дней должно быть целым числом от 1 до 366.")
        found = []

        for record in self.records():
            if record.birthday is None:
                continue

            birthday_date = _next_birthday(record.birthday.value, today)
            if (birthday_date - today).days >= days:
                continue

            congratulation_date = birthday_date
            weekday = birthday_date.weekday()
            if weekday >= 5:
                congratulation_date += timedelta(days=7 - weekday)

            found.append((congratulation_date, birthday_date, record))

        found.sort(key=lambda item: (item[0], item[2].name.value.casefold(), item[2].id))
        return [
            {
                "id": record.id,
                "name": record.full_name,
                "birthday": birthday_date.strftime(DATE_FORMAT),
                "congratulation_date": congratulation_date.strftime(DATE_FORMAT),
            }
            for congratulation_date, birthday_date, record in found
        ]

    # --- сохранение ---

    def to_dict(self):
        return {
            "next_id": self._next_id,
            "records": [record.to_dict() for record in self.records()],
            "demo_initialized": self.demo_initialized,
        }

    @classmethod
    def from_dict(cls, data, warnings=None):
        warnings = warnings if warnings is not None else []
        book = cls()
        if isinstance(data, dict):
            book.demo_initialized = data.get("demo_initialized") is True
        items = data.get("records") if isinstance(data, dict) else None
        if not isinstance(items, list):
            if data:
                warnings.append("Contacts section is damaged and was skipped.")
            return book

        for item in items:
            try:
                record = Record.from_dict(item)
            except (KeyError, ValueError, TypeError, AttributeError) as error:
                warnings.append(f"Skipped a damaged contact: {error}")
                continue
            if (type(record.id) is not int or record.id < 1) or record.id in book._records:
                warnings.append(f"Skipped contact '{record.name}': bad or duplicate id.")
                continue
            book._records[record.id] = record

        saved_next = data.get("next_id")
        saved_next = saved_next if isinstance(saved_next, int) else 1
        book._next_id = max(saved_next, max(book._records, default=0) + 1)
        return book


# models/note.py
import re
from datetime import datetime

MAX_TAG_LENGTH = 30


def validate_text(raw):
    text = " ".join(str(raw).split())
    if not text:
        raise ValueError("Note text cannot be empty.")
    return text


def normalize_tag(raw):
    """'#Shopping' -> 'shopping'."""
    tag = str(raw).strip().lstrip("#").lower()
    if not tag:
        raise ValueError("Tag cannot be empty.")
    if len(tag) > MAX_TAG_LENGTH:
        raise ValueError(f"Tag is too long (max {MAX_TAG_LENGTH} characters).")
    if re.search(r"[\s,;#]", tag):
        raise ValueError("A tag cannot contain spaces, commas or '#'.")
    return tag


def parse_tags(raw):
    """'work, #urgent home' -> ['work', 'urgent', 'home'] (без повторов)."""
    tags = []
    for part in re.split(r"[\s,;]+", str(raw).strip()):
        if not part:
            continue
        tag = normalize_tag(part)
        if tag not in tags:
            tags.append(tag)
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
        """Возвращает True, если тег добавлен, и False, если он уже был."""
        tag = normalize_tag(tag)
        if tag in self.tags:
            return False
        self.tags.append(tag)
        return True

    def remove_tag(self, tag):
        tag = normalize_tag(tag)
        if tag not in self.tags:
            raise ValueError(f"Tag '#{tag}' is not on note {self.id}.")
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
        header = f"[{self.id}] {self.created:%Y-%m-%d %H:%M}"
        if tags:
            header += f"  {tags}"
        return f"{header}\n    {self.text}"


# models/notebook.py

SORT_MODES = ("id", "date", "tags")


class Notebook:
    def __init__(self):
        self._notes = {}
        self._next_id = 1
        self._tags = set()

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

    def sorted_notes(self, by="id"):
        if by == "date":  # сначала новые
            return sorted(self.notes(), key=lambda n: (n.created, n.id), reverse=True)
        if by == "tags":  # по алфавиту тегов, без тегов в конце
            return sorted(
                self.notes(),
                key=lambda n: (0, sorted(n.tags), n.id) if n.tags else (1, [], n.id),
            )
        if by == "id":
            return self.notes()
        raise ValueError(f"Unknown sort mode '{by}'. Use: {', '.join(SORT_MODES)}.")

    def all_tags(self):
        counts = dict.fromkeys(self._tags, 0)
        for note in self.notes():
            for tag in note.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items()))

    def register_tag(self, raw):
        tag = normalize_tag(raw)
        self._tags.add(tag)
        return tag

    def rename_tag(self, old, new):
        old, new = normalize_tag(old), normalize_tag(new)
        if old not in self.all_tags():
            raise ValueError("Тег не найден.")
        if new != old and new in self.all_tags():
            raise ValueError("Такой тег уже существует.")
        for note in self.notes():
            note.tags = [new if tag == old else tag for tag in note.tags]
        self._tags.discard(old)
        self._tags.add(new)

    def delete_tag(self, raw):
        tag = normalize_tag(raw)
        for note in self.notes():
            if tag in note.tags:
                note.remove_tag(tag)
        self._tags.discard(tag)

    # --- сохранение ---

    def to_dict(self):
        return {
            "next_id": self._next_id,
            "notes": [note.to_dict() for note in self.notes()],
            "tags": sorted(self.all_tags()),
        }

    @classmethod
    def from_dict(cls, data, warnings=None):
        warnings = warnings if warnings is not None else []
        notebook = cls()
        if isinstance(data, dict):
            for tag in data.get("tags") or []:
                try:
                    notebook.register_tag(tag)
                except ValueError as error:
                    warnings.append(f"Skipped tag: {error}")
        items = data.get("notes") if isinstance(data, dict) else None
        if not isinstance(items, list):
            if data:
                warnings.append("Notes section is damaged and was skipped.")
            return notebook

        for item in items:
            try:
                note = Note.from_dict(item)
            except (KeyError, ValueError, TypeError, AttributeError) as error:
                warnings.append(f"Skipped a damaged note: {error}")
                continue
            if (type(note.id) is not int or note.id < 1) or note.id in notebook._notes:
                warnings.append("Skipped a note with a bad or duplicate id.")
                continue
            notebook._notes[note.id] = note

        saved_next = data.get("next_id")
        saved_next = saved_next if isinstance(saved_next, int) else 1
        notebook._next_id = max(saved_next, max(notebook._notes, default=0) + 1)
        return notebook


# legacy.py
"""Перенос данных из старого addressbook.pkl (версия до рефакторинга).

Файл читается «безопасным» unpickler'ом: он создаёт только пустые заглушки
вместо наших старых классов и не выполняет произвольный код из файла.
"""

import datetime as legacy_datetime
import pickle
from pathlib import Path


LEGACY_FILENAME = "addressbook.pkl"
_LEGACY_CLASSES = {"Field", "Name", "Phone", "Birthday", "Record", "AddressBook"}


class _Stub:
    """Пустая заглушка: pickle заполнит её атрибутами."""


class _SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if name in _LEGACY_CLASSES and (
            module == "__main__" or module.startswith("personal_assistant")
        ):
            return _Stub
        if (module, name) == ("datetime", "date"):
            return legacy_datetime.date
        raise pickle.UnpicklingError(f"Forbidden object in legacy file: {module}.{name}")


def find_legacy_file(data_dir):
    for candidate in (Path.cwd() / LEGACY_FILENAME, Path(data_dir) / LEGACY_FILENAME):
        if candidate.is_file():
            return candidate
    return None


def load_legacy_book(path, warnings):
    """Читает старый pickle и возвращает новую AddressBook."""
    with open(path, "rb") as f:
        old_book = _SafeUnpickler(f).load()

    old_records = getattr(old_book, "data", None)
    if not isinstance(old_records, dict):
        raise ValueError("unexpected structure of the old file")

    book = AddressBook()
    for key, old in old_records.items():
        try:
            record = Record(old.name.value)
        except (AttributeError, ValueError) as error:
            warnings.append(f"Skipped old contact {key!r}: {error}")
            continue

        for old_phone in getattr(old, "phones", []) or []:
            try:
                record.add_phone(old_phone.value)
            except (AttributeError, ValueError) as error:
                warnings.append(f"{record.name}: skipped phone ({error})")

        old_birthday = getattr(old, "birthday", None)
        if old_birthday is not None:
            try:
                record.set_birthday(old_birthday.value.strftime(DATE_FORMAT))
            except (AttributeError, ValueError) as error:
                warnings.append(f"{record.name}: skipped birthday ({error})")

        book.add_record(record)
    return book


# storage.py
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


APP_DIR_NAME = ".personal_assistant"
DATA_FILENAME = "data.json"
ENV_DATA_DIR = "PERSONAL_ASSISTANT_HOME"
FORMAT_VERSION = 1


class StorageError(Exception):
    """Не удалось сохранить данные."""


@dataclass
class LoadResult:
    book: AddressBook
    notebook: Notebook
    warnings: list = field(default_factory=list)
    migrated: bool = False
    restored: bool = False


def get_data_dir():
    custom = os.environ.get(ENV_DATA_DIR)
    return Path(custom) if custom else Path.home() / APP_DIR_NAME


def get_data_path():
    return get_data_dir() / DATA_FILENAME


def _backup_path(path):
    return path.with_name(path.name + ".bak")


def save_data(book, notebook, path=None):
    """Атомарная запись: во временный файл, затем замена. Старая версия уходит в .bak."""
    path = Path(path) if path else get_data_path()
    payload = {
        "version": FORMAT_VERSION,
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
        raise StorageError(f"Could not save data to {path}: {error}") from error


def _read_json(path, warnings):
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError) as error:
        warnings.append(f"Could not read {path.name}: {error}")
        return None
    if not isinstance(payload, dict):
        warnings.append(f"{path.name} has an unexpected structure.")
        return None
    return payload


def _quarantine(path, warnings):
    """Повреждённый файл переименовываем, чтобы новое сохранение его не затёрло."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        path.rename(target)
        warnings.append(f"The damaged file was kept as {target.name}.")
    except OSError as error:
        warnings.append(f"Could not move the damaged file aside: {error}")


def _build(payload, warnings):
    book = AddressBook.from_dict(payload.get("contacts"), warnings)
    notebook = Notebook.from_dict(payload.get("notes"), warnings)
    return book, notebook


def load_data(path=None):
    """Загружает данные. Любая проблема превращается в предупреждение, а не в падение."""
    path = Path(path) if path else get_data_path()
    warnings = []

    if path.exists() or _backup_path(path).exists():
        restored = False
        payload = _read_json(path, warnings) if path.exists() else None
        if payload is None:
            backup = _backup_path(path)
            if backup.exists():
                payload = _read_json(backup, warnings)
                if payload is not None:
                    if path.exists():
                        _quarantine(path, warnings)
                    restored = True
                    warnings.append("Data was restored from the backup copy.")
            if payload is None:
                if path.exists():
                    _quarantine(path, warnings)
        if payload is None:
            return LoadResult(AddressBook(), Notebook(), warnings)
        book, notebook = _build(payload, warnings)
        return LoadResult(book, notebook, warnings, restored=restored)

    legacy_file = find_legacy_file(path.parent)
    if legacy_file is not None:
        try:
            book = load_legacy_book(legacy_file, warnings)
        except Exception as error:  # битый или чужой файл не должен ронять запуск
            warnings.append(f"Could not import {legacy_file}: {error}")
        else:
            warnings.append(
                f"Imported {len(book)} contact(s) from {legacy_file}. "
                "The original file was left untouched."
            )
            return LoadResult(book, Notebook(), warnings, migrated=True)

    return LoadResult(AddressBook(), Notebook(), warnings)


# Консольный интерфейс
import argparse
import sys

COLORS = {
    "menu": "36", "title": "95", "question": "33",
    "result": "37", "success": "32", "error": "31", "warning": "33",
}


def enable_terminal_colors():
    """Включает ANSI-цвета в стандартной консоли Windows."""
    if os.name == "nt":
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel.SetConsoleMode(handle, mode.value | 4)


def paint(text, kind="result", enabled=None):
    if enabled is None:
        # PyCharm Run может поддерживать ANSI, даже когда isatty() == False.
        enabled = "NO_COLOR" not in os.environ
    return f"\033[{COLORS[kind]}m{text}\033[0m" if enabled else str(text)


class MenuCancelled(Exception):
    pass


def seed_contacts(book):
    """Добавляет 25 вымышленных контактов только в новую учебную книгу."""
    people = [
        ("Анна", "Коваленко"), ("Иван", "Петренко"), ("Мария", "Бондаренко"),
        ("Олег", "Шевченко"), ("Елена", "Мельник"), ("Андрей", "Ткаченко"),
        ("Ирина", "Кравченко"), ("Дмитрий", "Олейник"), ("Наталья", "Поліщук"),
        ("Сергей", "Савченко"), ("Ольга", "Романенко"), ("Николай", "Лисенко"),
        ("Татьяна", "Мороз"), ("Василий", "Гончаренко"), ("Юлия", "Бойко"),
        ("Алексей", "Захаренко"), ("Виктория", "Клименко"), ("Роман", "Левченко"),
        ("София", "Сидоренко"), ("Максим", "Руденко"), ("Дарья", "Павленко"),
        ("Богдан", "Дорошенко"), ("Алина", "Черненко"), ("Павел", "Волков"),
        ("Катерина", "Гриценко"),
    ]
    for index, (name, surname) in enumerate(people, 1):
        record = Record(name, surname=surname)
        record.add_phone(f"050000{index:04}")
        record.set_email(f"student{index:02}@example.com")
        record.set_address(f"Учебная улица, дом {index}")
        record.set_birthday(f"{index:02}.{(index - 1) % 12 + 1:02}.{1980 + index}")
        book.add_record(record)
    book.demo_initialized = True


class ConsoleAssistant:
    def __init__(self, path=None, ask=input, say=print):
        self.path = Path(path) if path else get_data_path()
        self.ask = ask
        self.say = say
        loaded = load_data(self.path)
        self.book = loaded.book
        self.notebook = loaded.notebook
        self.dirty = loaded.migrated or loaded.restored
        for warning in loaded.warnings:
            self.output(warning, "warning")
        # Метка предотвращает повторное заполнение после удаления всех контактов.
        if not self.book.demo_initialized and not loaded.warnings:
            if len(self.book) == 0 and not loaded.migrated:
                seed_contacts(self.book)
                self.output("Создана учебная книга: 25 вымышленных контактов.", "warning")
            self.book.demo_initialized = True
            self.dirty = True

    def output(self, text, kind="result"):
        self.say(paint(str(text), kind))

    def read(self, prompt, cancel=True):
        raw = self.ask(paint(prompt, "question")).strip()
        if cancel and raw == "0":
            raise MenuCancelled()
        return raw

    def menu(self, title, labels, back="Назад", cancel=True):
        self.output("\n" + title, "title")
        for number, label in enumerate(labels, 1):
            self.output(f"{number}. {label}", "menu")
        self.output(f"0. {back}", "menu")
        while True:
            answer = self.read("Выберите число: ", cancel=False)
            if answer == "0":
                if cancel:
                    raise MenuCancelled()
                return 0
            if answer.isascii() and answer.isdigit() and 1 <= int(answer) <= len(labels):
                return int(answer)
            self.output("Ошибка: введите число из меню.", "error")

    def value(self, label, factory=str, optional=False):
        hint = " (Enter — пропустить)" if optional else ""
        self.output("0 — назад.", "menu")
        while True:
            raw = self.read(label + hint + ": ")
            if not raw:
                if optional:
                    return None
                self.output("Ошибка: это поле обязательно.", "error")
                continue
            try:
                return factory(raw)
            except ValueError as error:
                self.output("Ошибка: " + str(error), "error")

    def confirm(self, question):
        return self.menu(question, ["Да", "Нет"]) == 1

    def select_contact(self):
        if not len(self.book):
            self.output("Адресная книга пуста.", "warning")
            return None
        while True:
            query = self.value("Введите имя и фамилию. Например: Анна Коваленко")
            wanted = " ".join(query.split()).casefold()
            records = self.book.find_by_name(query)
            if not records:
                records = [
                    record for record in self.book.records()
                    if wanted in record.full_name.casefold()
                ]
            if not records:
                self.output("Контакт не найден. Проверьте имя и фамилию.", "warning")
                continue
            if len(records) == 1:
                return records[0]
            try:
                index = self.menu(
                    "Найдено несколько контактов. Выберите нужный",
                    [f"[{r.id}] {r.full_name} | "
                     f"{'; '.join(p.value for p in r.phones) or 'нет телефона'} | "
                     f"{r.email or 'нет email'} | {r.address or 'нет адреса'}"
                     for r in records],
                )
                return records[index - 1]
            except MenuCancelled:
                continue

    def select_phone(self, record):
        if not record.phones:
            self.output("У контакта нет телефонов.", "warning")
            return None
        index = self.menu("Выберите телефон", [p.value for p in record.phones])
        return record.phones[index - 1].value

    def contact_details(self, record):
        self.output(
            f"Контакт №{record.id}\n"
            f"  Имя: {record.name}\n"
            f"  Фамилия: {record.surname or '—'}\n"
            f"  Телефоны: {'; '.join(p.value for p in record.phones) or '—'}\n"
            f"  Email: {record.email or '—'}\n"
            f"  Адрес: {record.address or '—'}\n"
            f"  День рождения: {record.birthday or '—'}"
        )

    def add_contact(self):
        self.output("Новый контакт. Введите данные по очереди.", "title")
        name = self.value("Введите имя. Например: Анна", Name)
        surname = self.value("Введите фамилию. Например: Иванова", Name)
        phone = self.value("Введите телефон. Например: 0501234567", Phone)
        email = self.value("Email", Email, optional=True)
        address = self.value("Адрес", Address, optional=True)
        birthday = self.value("День рождения (ДД.ММ.ГГГГ)", Birthday, optional=True)
        # Запись попадает в книгу после завершения всей формы.
        record = Record(str(name), surname=str(surname))
        record.add_phone(str(phone))
        record.set_email(str(email) if email else None)
        record.set_address(str(address) if address else None)
        record.set_birthday(str(birthday) if birthday else None)
        self.book.add_record(record)
        self.output(f"Контакт №{record.id} сохранён.", "success")

    def edit_contact(self, record):
        fields = [
            ("Имя", "name", Name), ("Фамилия", "surname", Name),
            ("Телефон", "phone", Phone), ("Email", "email", Email),
            ("Адрес", "address", Address), ("День рождения", "birthday", Birthday),
        ]
        while True:
            index = self.menu("Изменить данные", [item[0] for item in fields] + [
                "Добавить номер", "Удалить контакт",
            ])
            try:
                if index == len(fields) + 1:
                    phone = self.value("Введите телефон. Например: 0501234567", Phone)
                    record.add_phone(str(phone))
                    self.output("Телефон добавлен.", "success")
                elif index == len(fields) + 2:
                    if self.confirm(f"Удалить контакт «{record.full_name}»?"):
                        self.book.delete(record.id)
                        self.output("Контакт удалён.", "success")
                else:
                    label, field_name, factory = fields[index - 1]
                    self.edit_field(record, label, field_name, factory)
                return
            except MenuCancelled:
                continue

    def edit_field(self, record, label, field_name, factory):
        while True:
            action = self.menu(label, ["Заменить", "Удалить"])
            try:
                if field_name == "name" and action == 2:
                    self.output("Ошибка: имя обязательно. Его можно заменить.", "error")
                    return
                if field_name == "phone":
                    old_phone = self.select_phone(record)
                    if old_phone is None:
                        return
                    if action == 1:
                        new_phone = self.value("Введите новый телефон. Например: 0501234567", Phone)
                        record.edit_phone(old_phone, str(new_phone))
                    elif self.confirm("Удалить выбранный телефон?"):
                        record.remove_phone(old_phone)
                    else:
                        self.output("Удаление отменено.", "warning")
                        return
                elif action == 1:
                    prompts = {
                        "name": "Введите новое имя. Например: Анна",
                        "surname": "Введите новую фамилию. Например: Иванова",
                    }
                    new_value = self.value(prompts.get(field_name, "Новое значение"), factory)
                    getattr(record, f"set_{field_name}")(str(new_value))
                elif self.confirm(f"Удалить поле «{label}»?"):
                    getattr(record, f"set_{field_name}")(None)
                else:
                    self.output("Удаление отменено.", "warning")
                    return
                self.output("Данные контакта обновлены.", "success")
                return
            except MenuCancelled:
                continue

    def contacts(self):
        while True:
            action = self.menu("Контакты", [
                "Добавить контакт", "Все контакты", "Найти и показать контакт",
                "Изменить данные",
            ])
            try:
                if action == 1:
                    self.add_contact()
                    return
                if action == 2:
                    for record in self.book.records():
                        self.contact_details(record)
                    if not len(self.book):
                        self.output("Адресная книга пуста.", "warning")
                    return
                record = self.select_contact()
                if record is None:
                    return
                if action == 3:
                    self.contact_details(record)
                elif action == 4:
                    self.edit_contact(record)
                return
            except MenuCancelled:
                continue

    def birthday_actions(self):
        while True:
            action = self.menu("Дни рождения", [
                "Установить день рождения", "Показать день рождения", "Ближайшие дни рождения",
            ])
            try:
                if action == 3:
                    days = self.value("Количество дней (1–366)", int)
                    entries = self.book.get_upcoming_birthdays(days)
                    if not entries:
                        self.output("В указанном периоде дней рождения нет.", "warning")
                    for entry in entries:
                        self.output(
                            f"{entry['name']} — день рождения {entry['birthday']}; "
                            f"поздравить {entry['congratulation_date']}"
                        )
                    return
                record = self.select_contact()
                if record is None:
                    return
                self.output(f"Выбран контакт: {record.full_name}", "title")
                if action == 1:
                    birthday = self.value("Введите дату рождения (ДД.ММ.ГГГГ)", Birthday)
                    record.set_birthday(str(birthday))
                    self.output(f"День рождения сохранён: {record.birthday}", "success")
                else:
                    self.output(f"День рождения: {record.birthday}" if record.birthday else
                                "День рождения не указан.")
                return
            except MenuCancelled:
                continue

    def note_actions(self):
        while True:
            action = self.menu("Заметки", ["Добавить заметку", "Все заметки", "Найти заметку"])
            try:
                if action == 1:
                    text = self.value("Текст заметки", validate_text)
                    self.output("Теги — ключевые слова для поиска и группировки заметок.", "result")
                    tags = self.value(
                        "Введите теги через пробел. Например: работа покупки идеи",
                        parse_tags, optional=True,
                    )
                    note = self.notebook.add_note(text, tags or [])
                    self.output(
                        f"Заметка №{note.id} сохранена. Создана: {note.created:%d.%m.%Y %H:%M}",
                        "success",
                    )
                    return
                if action == 2:
                    self.browse_notes()
                else:
                    self.find_note()
                return
            except MenuCancelled:
                continue

    def browse_notes(self):
        while True:
            order = self.menu("Сортировка заметок", ["По номеру", "Сначала новые", "По тегам"])
            notes = self.notebook.sorted_notes(("id", "date", "tags")[order - 1])
            try:
                self.select_note(notes)
                return
            except MenuCancelled:
                continue

    def find_note(self):
        while True:
            query = self.value("Текст или тег для поиска")
            try:
                self.select_note(self.notebook.search(query))
                return
            except MenuCancelled:
                continue

    def select_note(self, notes):
        if not notes:
            self.output("Заметки не найдены.", "warning")
            return
        while True:
            index = self.menu("Выберите заметку", [
                f"[{n.id}] {n.created:%d.%m.%Y %H:%M} | {n.text}" for n in notes
            ])
            note = notes[index - 1]
            try:
                self.manage_note(note)
                return
            except MenuCancelled:
                continue

    def manage_note(self, note):
        self.output(
            f"Заметка №{note.id}\nСоздана: {note.created:%d.%m.%Y %H:%M}\n{note.text}\n"
            f"Теги: {', '.join('#' + tag for tag in note.tags) or '—'}"
        )
        while True:
            action = self.menu("Действия с заметкой", [
                "Изменить заметку", "Удалить заметку", "Завершить просмотр",
            ])
            try:
                if action == 1:
                    note.set_text(self.value("Новый текст", validate_text))
                    self.output("Заметка изменена.", "success")
                elif action == 2 and self.confirm("Удалить заметку?"):
                    self.notebook.delete(note.id)
                    self.output("Заметка удалена.", "success")
                return
            except MenuCancelled:
                continue

    def tag_actions(self):
        while True:
            action = self.menu("Теги", ["Все теги", "Добавить тег"])
            try:
                if action == 2:
                    self.add_tag()
                else:
                    self.select_tag()
                return
            except MenuCancelled:
                continue

    def add_tag(self):
        tag = self.value("Новый тег", normalize_tag)
        self.notebook.register_tag(tag)
        self.output(f"Тег #{tag} сохранён.", "success")
        notes = self.notebook.notes()
        if notes and self.confirm("Прикрепить тег к заметке?"):
            index = self.menu("Выберите заметку", [f"[{n.id}] {n.text}" for n in notes])
            notes[index - 1].add_tag(tag)
            self.output("Тег добавлен к заметке.", "success")

    def select_tag(self):
        tags = self.notebook.all_tags()
        if not tags:
            self.output("Тегов пока нет.", "warning")
            return
        names = list(tags)
        while True:
            index = self.menu("Выберите тег", [f"#{tag} — заметок: {tags[tag]}" for tag in names])
            tag = names[index - 1]
            try:
                self.manage_tag(tag)
                return
            except MenuCancelled:
                continue

    def manage_tag(self, tag):
        for note in self.notebook.by_tag(tag):
            self.output(f"[{note.id}] {note.text}")
        while True:
            action = self.menu(f"Тег #{tag}", [
                "Изменить тег", "Удалить тег", "Добавить к заметке", "Убрать из заметки",
                "Завершить просмотр",
            ])
            try:
                if action == 1:
                    new_tag = self.value("Новое название тега", normalize_tag)
                    self.notebook.rename_tag(tag, new_tag)
                    self.output("Тег изменён во всех заметках.", "success")
                elif action == 2 and self.confirm("Удалить тег из всех заметок?"):
                    self.notebook.delete_tag(tag)
                    self.output("Тег удалён.", "success")
                elif action in (3, 4):
                    notes = self.notebook.notes() if action == 3 else self.notebook.by_tag(tag)
                    if not notes:
                        self.output("Подходящих заметок нет.", "warning")
                        return
                    index = self.menu("Выберите заметку", [f"[{n.id}] {n.text}" for n in notes])
                    if action == 3:
                        notes[index - 1].add_tag(tag)
                        self.output("Тег прикреплён.", "success")
                    else:
                        self.notebook.register_tag(tag)
                        notes[index - 1].remove_tag(tag)
                        self.output("Тег убран из заметки.", "success")
                return
            except MenuCancelled:
                continue

    def save(self):
        if not self.dirty:
            return True
        try:
            save_data(self.book, self.notebook, self.path)
        except StorageError as error:
            self.output("Ошибка сохранения: " + str(error), "error")
            self.output("Изменения остаются в памяти. Повторите сохранение.", "warning")
            return False
        self.dirty = False
        return True

    def finish_action(self):
        while True:
            self.output("Вы хотите вернуться в главное меню или закончить сессию?", "question")
            self.output(
                "1. Главное меню\n2. Закончить сессию\n"
                "0. Назад", "menu",
            )
            answer = self.read("Выберите число: ")
            if answer == "1":
                return False
            if answer == "2":
                if self.save():
                    return True
            else:
                self.output("Ошибка: выберите число из меню.", "error")

    def run(self):
        self.output("\nДобро пожаловать в персональный помощник!", "title")
        self.output("Контакты, дни рождения, заметки и теги — в одном месте.", "menu")
        self.output(
            "Выбор действий — цифрами. В подменю 0 — назад.",
            "warning",
        )
        self.save()
        sections = (self.contacts, self.birthday_actions, self.note_actions, self.tag_actions)
        finished = False
        while not finished:
            try:
                section = self.menu("Главное меню", [
                    "Контакты", "Дни рождения", "Заметки", "Теги",
                ], back="Закончить сессию", cancel=False)
                if section == 0:
                    finished = self.save()
                    continue
                while True:
                    before = (self.book.to_dict(), self.notebook.to_dict())
                    try:
                        sections[section - 1]()
                    except MenuCancelled:
                        break
                    except ValueError as error:
                        self.output("Ошибка: " + str(error), "error")
                    finally:
                        after = (self.book.to_dict(), self.notebook.to_dict())
                        self.dirty = self.dirty or before != after
                        self.save()
                    try:
                        finished = self.finish_action()
                        break
                    except MenuCancelled:
                        # После результата 0 возвращает в раздел, где выполнялось действие.
                        continue
            except (KeyboardInterrupt, EOFError):
                self.output("\nЗавершение ввода.", "warning")
                if not self.save():
                    raise StorageError("Сессию не удалось сохранить. Проверьте доступ к папке данных.")
                break
        self.output("Сессия завершена. Данные сохранены. До встречи!", "success")


def run(ask=input, say=print, data_path=None):
    enable_terminal_colors()
    ConsoleAssistant(data_path, ask, say).run()


def prepare_demo():
    """Отдельная учебная книга при запуске с --demo."""
    path = get_data_dir() / "demo.json"
    if not path.exists():
        book = AddressBook()
        seed_contacts(book)
        save_data(book, Notebook(), path)
    return path


def main():
    parser = argparse.ArgumentParser(description="Консольный персональный помощник")
    parser.add_argument("--demo", action="store_true", help="Отдельная учебная адресная книга")
    parser.add_argument("--data", type=Path, help="Путь к JSON-файлу данных")
    args = parser.parse_args()
    if args.demo and args.data:
        parser.error("Выберите только один параметр: --demo или --data.")
    try:
        run(data_path=prepare_demo() if args.demo else args.data)
    except StorageError as error:
        print(paint("Ошибка: " + str(error), "error"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
