import calendar
from datetime import date, timedelta
from typing import Self

from user_utils.contacts.contact_models.contact import Contact


class AddressBook:

	def __init__(self, contacts: list[Contact]):
		self.contacts = contacts

	def find_contact(self, predicate: str) -> list[Contact]:
		result: list[Contact] = []
		for contact in self.contacts:
			if contact.name == predicate or predicate in contact.emails or predicate in contact.phone_numbers:
				result.append(contact)
		return result

	def add_contact(
		self, name: str,
		phone: str,
		email: str | None,
		address: str | None,
		birthday: date | None
	) -> None:
		if self.find_contact(name):
			raise ValueError(f'Contact {name} already exists')
		self.contacts.append(
			Contact(
				name = name,
				phone_numbers = [phone],
				emails = [email] if email is not None else [],
				address = address,
				birthday = birthday
			)
		)

	def remove_contact_by_name(self, name: str) -> None:
		counter: int = 0
		while counter < len(self.contacts):
			if self.contacts[counter].name == name:
				del self.contacts[counter]
				break
			else:
				counter += 1
				
	def get_upcoming_birthdays(self, n_days: int) -> list[dict[str, str | date]]:
		result: list[dict[str, str | date]] = []
		now: date = date.today()
		n_days_later: date = date.today() + timedelta(days = n_days)

		for contact in self.contacts:
			if contact.birthday is None:
				continue

			coming_birthday: date = date(
				year = n_days_later.year,
				month = contact.birthday.month,
				day = contact.birthday.day
			) if not contact.birthday.month == 2 and contact.birthday.day == 29 and calendar.isleap(n_days_later.year) else date(
				# leap year case
				year = n_days_later.year,
				month = contact.birthday.month,
				day = contact.birthday.day - 1 if not calendar.isleap(n_days_later.year) else contact.birthday.day
			)

			if now <= coming_birthday < n_days_later:
				result.append(
					{
						'name': contact.name,
						'congratulation_date': coming_birthday,
					}
				)

		return result

	@classmethod
	def from_bin(cls, bin_path: str) -> Self:
		pass

	def to_bin(self, bin_path: str) -> None:
		pass