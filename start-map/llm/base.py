from typing import List, Dict


class BaseLLM:
    """
    Base class for all LLMs
    """

    def __init__(self):
        """
        init LLM
        """
        pass

    def chat(self, messages: List[Dict]):
        """
        Send a message to the big language model and get a response.
        :param messages: list of messages
        """
        pass

    @staticmethod
    def literal_eval(response_content: str):
        """
        convert the response content to a literal string
        """
        return response_content
