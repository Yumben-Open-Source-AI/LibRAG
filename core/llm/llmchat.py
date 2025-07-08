import os
from typing import Any, List, Union

from tools.log_tools import parser_logger as logger
from llama_index.core.base.llms.types import ChatResponse, ChatMessage
from llama_index.llms.openai_like import OpenAILike
from tools.decorator import concurrent_decorator


class LlmChat(OpenAILike):

    def __init__(self, **kwargs):
        kwargs['model'] = os.getenv('MODEL_NAME', default='qwen2.5-72b-instruct')
        kwargs['api_base'] = os.getenv('OPENAI_BASE_URL', default='https://dashscope.aliyuncs.com/compatible-mode/v1')
        kwargs['api_key'] = os.getenv('OPENAI_API_KEY')
        kwargs['context_window'] = 128000
        kwargs['max_tokens'] = 8192
        kwargs['temperature'] = 0.7
        kwargs['is_chat_model'] = True
        kwargs['is_function_calling_model'] = False
        kwargs['max_retries'] = 3
        kwargs['timeout'] = 1800
        kwargs['reuse_client'] = True
        super().__init__(**kwargs)

    @staticmethod
    def literal_eval(response_content: str):
        """
        convert the response content to a literal string
        """
        import ast

        response_content = response_content.strip()
        # handler think
        if '<think>' in response_content and '</think>' in response_content:
            think_id = response_content.find('</think>') + len('</think>')
            response_content = response_content[think_id:]

        try:
            if response_content.startswith("```") and response_content.endswith("```"):
                # handler python
                if response_content.startswith("```python"):
                    response_content = response_content[9:-3]
                # handler json
                elif response_content.startswith("```json"):
                    response_content = response_content[7:-3]
                # handler str
                elif response_content.startswith("```str"):
                    response_content = response_content[6:-3]
                elif response_content.startswith("```\n"):
                    response_content = response_content[4:-3]
                else:
                    raise ValueError("Invalid code block format")
            result = ast.literal_eval(response_content.strip())
        except Exception as e:
            import re
            json_match = re.findall(r'(\[.*?\]|\{.*?\})', response_content, re.DOTALL)
            if len(json_match) != 1:
                raise Exception('the response is invalid JSON content, please try again')
            result = ast.literal_eval(json_match[0])

        return result

    @concurrent_decorator
    def chat(self, messages: List[Union[str, dict]], count: int = 0, **kwargs: Any) -> ChatResponse:
        processed_messages = []

        retries = 0
        while retries < 3:
            try:
                for i, msg in enumerate(messages):
                    if isinstance(msg, dict):
                        # 如果消息是字典，直接使用其role/content
                        processed_messages.append(ChatMessage(**msg))
                    else:
                        # 自动分配角色：偶数索引为system，奇数索引为user
                        role = "system" if i % 2 == 0 else "user"
                        processed_messages.append(ChatMessage(role=role, content=msg))
                chat = super().chat(processed_messages, **kwargs)
                response = chat.message.content
                return self.literal_eval(response)
            except Exception as e:
                logger.error(e, exc_info=True)
                retries += 1
