import os
from llm.base import BaseLLM


class BaseParser:
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))

    def __init__(self, llm: BaseLLM, kb_id: int):
        self.llm = llm
        self.kb_id = kb_id

    def parse(self, **kwargs):
        pass

    def storage_parser_data(self):
        pass

    def back_fill_parent(self, parent):
        pass
