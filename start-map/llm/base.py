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
        import ast

        response_content = response_content.strip()
        # handler think
        if '<think>' in response_content and '</think>' in response_content:
            think_id = response_content.find('</think>') + len('</think>')
            response_content = response_content[think_id:]

        try:
            if '```' in response_content:
                # handler json
                if '```json' in response_content:
                    response_content = response_content[7:-3]
                # handler markdown
                if '```markdown' in response_content:
                    response_content = response_content[11:-3]

            result = ast.literal_eval(response_content)
        except Exception as e:
            import re

            json_match = re.findall(r"\{.*\}", response_content, re.DOTALL)
            if len(json_match) < 0:
                raise Exception('the response is invalid JSON content, please try again')

            result = ast.literal_eval(json_match[0])

        return result
