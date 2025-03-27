from typing import List, Dict

from llm.base import BaseLLM


class BaseSelector:
    """
    Base class for all selectors.
    """

    def __init__(self, llm: BaseLLM):
        """
        :param llm: language model client
        """
        pass

    def get_layer_data(self) -> List[Dict]:
        # Get the data needed for selector
        pass

    def start_select(self, question: str):
        # Search for data related to the current layer
        pass

    def collate_select_params(self, params: List[Dict] = None):
        pass

    def collate_select_result(self) -> List:
        """
        Organize the current selector return results to prepare for the next level of parameters
        """
        pass
