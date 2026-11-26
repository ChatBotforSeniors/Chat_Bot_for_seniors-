import pickle
from typing import Self

from user_utils.contacts.contact_models.contact import Contact


class AddressBook:
    def __init__(self, contacts: list[Contact]):
        self.contacts = contacts

    @classmethod
    def from_bin(cls, bin_path: str) -> Self:
        with open(bin_path, "rb") as file:
            return pickle.load(file)

    def to_bin(self, bin_path: str) -> None:
        with open(bin_path, "wb") as file:
            pickle.dump(self, file)