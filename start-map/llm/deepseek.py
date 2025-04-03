import os
from typing import List, Dict

from llm.base import BaseLLM


class DeepSeek(BaseLLM):
    def __init__(self, model='deepseek-r1-distill-qwen-32b', **kwargs):
        """
        Initialize the large language model client and parameters
        :param model: Qwen model
        :param kwargs: other arguments
        """
        from openai import OpenAI as OpenAI_
        self.model = model

        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL', default='https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.client = OpenAI_(api_key=api_key, base_url=base_url, **kwargs)

    def chat(self, messages: List[Dict]):
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        return completion.choices[0].message.content, completion.usage.total_tokens
