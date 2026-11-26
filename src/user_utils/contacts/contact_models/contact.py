import re
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class Contact:
	name: str
	phone_numbers: list[str]
	emails: list[str]
	address: str | None = None
	birthday: date | None = None

	def __post_init__(self):
		self.__validate_name(self.name)
		self.__validate_phone_number(self.phone_numbers)
		self.__validate_email(self.emails)
		self.__validate_address(self.address)
		_ = self.__validate_birthday(self.birthday)
	
	def __validate_name(self, name: str) -> None:
		if not isinstance(name, str):
			raise TypeError('Name must be a string')
		if name.strip() == '':
			raise ValueError('Name cannot be empty or white space')
		
	def __validate_phone_number(self, phone_number: list[str]) -> None:
		if not isinstance(phone_number, list):
			raise TypeError('Phone number must be a list')
		for number in phone_number:
			if not isinstance(number, str):
				raise TypeError('Phone number must be a string')
			if re.match(r'^\d{10}$', number) is None:
				raise ValueError(f'Phone number must be a 10-digit number. Bad value: {number}')

	def __validate_email(self, email: list[str]) -> None:
		email_re = re.compile(
			r"^(?=.{1,254}$)"  # overall length limit
			r"(?=.{1,64}@)"  # local part length limit
			r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"  # local part start
			r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"  # dot-separated local parts
			r"@"
			r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"  # domain labels
			r"[A-Za-z]{2,63}$"  # top-level domain
		)

		if not isinstance(email, list):
			raise TypeError('Email must be a list')
		for email_address in email:
			if not isinstance(email_address, str):
				raise TypeError('Email must be a string')
			if email_re.fullmatch(email_address) is None:
				raise ValueError(f'Email must be a valid email address. Bad value: {email_address}')

	def __validate_address(self, address: str | None) -> None:
		if address is not None and not isinstance(address, str):
			raise TypeError('Address must be a string or None')

	def __validate_birthday(self, birthday: str | date | None) -> date | None:
		if birthday is None or isinstance(birthday, date):
			return birthday
		if isinstance(birthday, str):
			try:
				birthday_as_date = datetime.strptime(birthday, '%d.%m.%Y')
				return birthday_as_date
			except ValueError:
				raise ValueError("Invalid date format. Use DD.MM.YYYY")

	def add_email(self, email: str) -> None:
		self.__validate_email([email])
		self.emails.append(email)

	def remove_email(self, email: str) -> None:
		if email not in self.emails:
			raise ValueError(f'Email {email} not found in contact {self.name}')
		self.emails.remove(email)

	def add_address(self, address: str) -> None:
		self.__validate_address(address)
		self.address = address

	def remove_address(self) -> None:
		self.address = None

	def add_birthday(self, birthday: str) -> None:
		validated_birthday = self.__validate_birthday(birthday)
		self.birthday = validated_birthday

	def remove_birthday(self) -> None:
		self.birthday = None

	def add_phone_number(self, number: str) -> None:
		self.__validate_phone_number([number])
		self.phone_numbers.append(number)

	def remove_phone_number(self, number: str) -> None:
		if number not in self.phone_numbers:
			raise ValueError(f'Phone number {number} not found in contact {self.name}')
		self.phone_numbers.remove(number)

	def purge_phone_numbers(self) -> None:
		self.phone_numbers = []
			