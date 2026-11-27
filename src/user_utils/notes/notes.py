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
				max(note.id for note in self.notes)
				self.notes.append(
					NoteRecord(
						title = title,
						text = [text],
						tags = [tags] if tags is not None else [],
					)
				)

		