from typing import Self

from user_utils.notes.models.note_record import NoteRecord


class Notes:

	def __init__(self, notes: list[NoteRecord]):
		self.notes = notes

	def from_bin(self, bin_path: str) -> Self:
		pass

	def to_bin(self, bin_path: str) -> None:
		pass