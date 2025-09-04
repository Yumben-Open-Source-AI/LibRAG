"""
@Project ：LibRAG
@File    ：ai_answers.py
@IDE     ：PyCharm
@Author  ：7010
@Date    ：2025/9/4
"""
import copy
from datetime import datetime
from string import Template
from typing import Dict, List
from tools.log_tools import selector_logger as logger
from tools.prompt_load import TextFileReader

# 定义系统提示词模板
AI_ANSWER_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/agent/AI_ANSWERS_SYSTEM.txt")
    }
]
# 定义用户提示词模板
AI_ANSWER_USER_MESSAGES = [
    {
        'role': 'user',
        'content': ''
    }
]


class AIAnswerGenerator:
    def __init__(self, llm):
        self.llm = llm

    def generate_answer(self, question: str, context: str, kb_id: int) -> Dict:
        """
        生成AI回答
        Args:
            question: 用户问题
            context: 召回的相关段落内容
            kb_id: 知识库ID

        Returns:
            dict: 包含AI生成的回答和相关信息
        """
        # 组装提示词
        messages = self._build_prompt(question, context, kb_id)
        # 调用LLM生成回答
        response = self.llm.chat(messages)

        logger.debug(f'AI回答生成器 response:{response}')
        return response

    def _build_prompt(self, question: str, context: str, kb_id: int) -> List[Dict]:
        """
        组装提示词
        Args:
            question: 用户问题
            context: 召回的相关段落内容
            kb_id: 知识库ID

        Returns:
            list: 组装好的提示词消息列表
        """
        # 复制系统提示词模板
        system_messages = copy.deepcopy(AI_ANSWER_SYSTEM_MESSAGES)
        template = Template(system_messages[0]['content'])
        system_messages[0]['content'] = template.substitute(
            now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            context=context,
            query=question
        )
        logger.debug(f'AI回答生成器 system prompt:{system_messages}')

        # 复制用户提示词模板
        user_messages = copy.deepcopy(AI_ANSWER_USER_MESSAGES)
        template = Template(user_messages[0]['content'])
        user_messages[0]['content'] = question
        logger.debug(f'AI回答生成器 user prompt:{user_messages}')

        # 组合所有提示词
        return system_messages + user_messages
