import os
from typing import List, Dict

from llm.base import BaseLLM


class Qwen(BaseLLM):
    def __init__(self, model='qwen2.5-72b-instruct', **kwargs):
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
        retries = 0
        while retries < 3:
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7
                )
                content = completion.choices[0].message.content
                usage_token = completion.usage.total_tokens
                content = self.literal_eval(content)
                return content, usage_token
            except Exception as e:
                retries += 1
