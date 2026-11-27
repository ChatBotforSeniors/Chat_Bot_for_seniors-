from typing import Self

from user_utils.notes.models.note_record import NoteRecord


class Notes:

	def __init__(self, notes: list[NoteRecord]):
		self.notes = notes


	def add_note(
			self, title: str,
			text: str,
			tags: str | None,
		) -> None:
			self.notes.append(
				NoteRecord(
					title = title,
					text = text,
					tags = [tags] if tags is not None else [],
				)
			)

	
	def show_notes(self) -> list[NoteRecord]:
		return self.notes


	def find_note(self, literal: str) -> NoteRecord | None:
			for note in self.notes:
				if note.title == literal:
					return note
			return None


	def remove_note(self, title: str) -> None:
		note = self.find_note(title)
		if note is None:
			raise ValueError("(Note is not finded")
		self.notes.remove(note)


	def edit_note(self, title: str, text: str) -> None:
		note = self.find_note(title)
		if note is None:
			raise ValueError("Note is not found")
		note.add_text(text)


	def find_by_tags(self, tag: str) -> list[NoteRecord]:
		result = []
		for note in self.notes:
			if tag in note.tags:
				result.append(note)
		return result


	def sort_by_tags(self):
		return sorted(self.notes, key=lambda note: note.tags)


	@classmethod
	def from_bin(cls, bin_path: str) -> Self:
		pass

	def to_bin(self, bin_path: str) -> None:
		pass