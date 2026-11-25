from dataclasses import dataclass


@dataclass(frozen = True, slots = True)
class Contact:
	name: str
	phone_number: list[str]
	email: list[str]
	address: str

	def __post_init__(self):
		pass