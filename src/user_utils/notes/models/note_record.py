from dataclasses import dataclass


@dataclass(frozen = True, slots = True)
class NoteRecord:
	title: str
	text: str
	tag: str

	def __post_init__(self):
		pass