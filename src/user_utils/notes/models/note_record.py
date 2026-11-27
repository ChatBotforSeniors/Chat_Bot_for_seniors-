from dataclasses import dataclass, field


@dataclass
class NoteRecord:
	title: str
	text: str
	tags: list[str] = field(default_factory=list)


	def __post_init__(self):
		self.__validate_title(self.title)
		self.__validate_text(self.text)
		self.__validate_tags(self.tags)


	def __validate_title(self, title: str) -> None:
		if not isinstance(title, str):
			raise TypeError('Title must be a string')
		if title.strip() == '':
			raise ValueError('Title cannot be empty or white space')


	def __validate_text(self, text: str) -> None:
			if not isinstance(text, str):
				raise TypeError('Text must be a string')
			if text.strip() == '':
				raise ValueError('Text cannot be empty or white space')


	def __validate_tags(self, tags: list[str]) -> None:
			if not isinstance(tags, list):
				raise TypeError('Tags must be a list')
			for tag in tags:
				if not isinstance(tag, str):
					raise TypeError('Tags must be a string')
				if tags.strip() == '':
							raise ValueError('Tags cannot be empty or white space')



	def add_title(self, title: str) -> None:
			self.__validate_title(title)
			self.title = title


	def add_text(self, text: str) -> None:
				self.__validate_text(text)
				self.text = text


	def add_tag(self, tag: str) -> None:
			self.__validate_tags([tag])
			self.tags.append(tag)


	def remove_tag(self, tag: str) -> None:
			if tag not in self.tags:
				raise ValueError(f'tag {tag} not found in tags {self.tags}')
			self.tags.remove(tag)