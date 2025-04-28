from typing import List, Dict

from sqlmodel import Session

from llm.base import BaseLLM


class SelectorParam:
    def __init__(self, llm: BaseLLM, kb_id: int, session: Session, question: str):
        self.llm = llm
        self.kb_id = kb_id
        self.session = session
        self.question = question


class BaseSelector:
    """
    选择器基类
    """

    def __init__(self, param: SelectorParam):
        self.params = param

    def get_layer_data(self) -> List[Dict]:
        """ 获取当前层级所有数据 """
        pass

    def start_select(self):
        """ 根据问题返回与问题相关内容 """
        pass

    def collate_select_params(self, params: List[Dict] = None):
        """ 整理选择器所需入参结构 """
        pass

    def collate_select_result(self) -> List:
        """ 整理选择器返回结果 """
        pass
