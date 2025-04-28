from sqlmodel import Session

from llm.base import BaseLLM


class BaseParser:

    def __init__(self, llm: BaseLLM, kb_id: int, session: Session):
        self.llm = llm
        self.kb_id = kb_id
        self.session = session

    def parse(self, **kwargs):
        pass

    def storage_parser_data(self, parent):
        pass

    def back_fill_parent(self):
        pass
