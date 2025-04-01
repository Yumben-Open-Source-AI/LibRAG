from llm.base import BaseLLM


class BaseParser:
    def __init__(self, llm: BaseLLM):
        pass

    def parse(self, **kwargs):
        pass

    def storage_parser_data(self):
        pass

    def back_fill_parent(self, parent):
        pass
