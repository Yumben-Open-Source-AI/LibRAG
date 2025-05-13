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

    def chat(self, messages: List[Dict], count: int = 0):
        """
        Send a message to the big language model and get a response.
        :param messages: list of messages
        :param count: Number of concurrent messages per group
        """
        pass

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
            print(response_content)
            import re

            json_match = re.findall(r'(\[.*?\]|\{.*?\})', response_content, re.DOTALL)
            if len(json_match) != 1:
                raise Exception('the response is invalid JSON content, please try again')

            result = ast.literal_eval(json_match[0])

        return result
