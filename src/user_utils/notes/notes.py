import pickle
from typing import Self

from user_utils.notes.models.note_record import NoteRecord


class Notes:

	def __init__(self, notes: list[NoteRecord]):
		self.notes = notes

	@classmethod
	def from_bin(cls, bin_path: str) -> Self:
		with open(bin_path, "rb") as file:
			return pickle.load(file)

	def to_bin(self, bin_path: str) -> None:
		with open(bin_path, "wb") as file:
			pickle.dump(self, file)