from sqlmodel import Session

from llm.llmchat import LlmChat


class BaseParser:

    def __init__(self, llm: LlmChat, kb_id: int, session: Session):
        self.llm = llm
        self.kb_id = kb_id
        self.session = session

    def parse(self, **kwargs):
        pass

    def storage_parser_data(self, parent):
        pass

    def back_fill_parent(self):
        pass
