from user_utils.contacts.contact_models.contact import Contact


class AddressBook:

	def __init__(self, contacts: list[Contact]):
		self.contacts = contacts

	def from_bin(self, bin_path: str) -> None:
		pass

	def to_bin(self, bin_path: str) -> None:
		pass