import copy
from string import Template
from llm.llmchat import LlmChat
from parser.base import BaseParser
from tools.prompt_load import TextFileReader
from tools.log_tools import selector_logger as logger

# 全局加载提示词模板
RESULT_SCORING_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/agent/INFORMATION_RETRIEVAL_SCORING_SYSTEM.txt")
    },
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/agent/INFORMATION_RETRIEVAL_SCORING_USER.txt")
    }
]


class ResultScoringParser():
    def __init__(self, llm: LlmChat):
        self.llm = llm  # 直接赋值

    def rate(self, user_question: str, search_context: str, **kwargs) -> dict:
        """
        根据用户问题与检索上下文，调用大模型进行打分评估。
        :param user_question: 用户输入的问题
        :param search_context: 与该问题匹配的检索结果片段
        :return: LLM 返回的 JSON 格式评估结果
        """
        # 深拷贝，避免污染全局模板
        result_scoring_messages = copy.deepcopy(RESULT_SCORING_MESSAGES)

        # 使用 string.Template 替换 system prompt 中变量
        template = Template(result_scoring_messages[1]['content'])
        result_scoring_messages[1]['content'] = template.substitute(
            UserQuestion=user_question,
            SearchContext=search_context
        )
        logger.debug(f'召回打分评估 system prompt:{result_scoring_messages}')
        # 调用 LLM 聊天接口
        response = self.llm.chat(result_scoring_messages)

        return response
