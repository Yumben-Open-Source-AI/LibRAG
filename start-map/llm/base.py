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

            result = ast.literal_eval(response_content)
        except Exception as e:
            import re

            json_match = re.findall(r"\{.*\}", response_content, re.DOTALL)
            if len(json_match) < 0:
                raise Exception('the response is invalid JSON content, please try again')

            result = ast.literal_eval(json_match[0])

        print(result)
        return result

# 籌 {'matrix': (11.9, 0.0, 0, 14, 76.7855, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 76.7855, 'y0': 441.9562, 'x1': 88.6855, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '籌', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
# 籌 {'matrix': (11.9, 0.0, 0, 14, 76.78609999999998, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 76.78609999999998, 'y0': 441.9582, 'x1': 88.68609999999998, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '籌', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
#
#
# 資 {'matrix': (11.9, 0.0, 0, 14, 88.98359999999998, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 88.98359999999998, 'y0': 441.9582, 'x1': 100.88359999999999, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '資', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
# 活 {'matrix': (11.9, 0.0, 0, 14, 101.18109999999997, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 101.18109999999997, 'y0': 441.9582, 'x1': 113.08109999999998, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '活', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
# 動 {'matrix': (11.9, 0.0, 0, 14, 113.37859999999998, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 113.37859999999998, 'y0': 441.9582, 'x1': 125.27859999999998, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '動', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
# 現 {'matrix': (11.9, 0.0, 0, 14, 125.57609999999997, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 125.57609999999997, 'y0': 441.9582, 'x1': 137.47609999999997, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '現', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
# 金 {'matrix': (11.9, 0.0, 0, 14, 137.7736, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 137.7736, 'y0': 441.9582, 'x1': 149.6736, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '金', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
# 流 {'matrix': (11.9, 0.0, 0, 14, 149.97109999999998, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 149.97109999999998, 'y0': 441.9582, 'x1': 161.87109999999998, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '流', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
# 入 {'matrix': (11.9, 0.0, 0, 14, 162.16859999999997, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 162.16859999999997, 'y0': 441.9582, 'x1': 174.06859999999998, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '入', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
# 小 {'matrix': (11.9, 0.0, 0, 14, 174.3661, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 174.3661, 'y0': 441.9582, 'x1': 186.2661, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '小', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
# 計 {'matrix': (11.9, 0.0, 0, 14, 186.5636, 444.7442), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 186.5636, 'y0': 441.9582, 'x1': 198.4636, 'y1': 455.9582, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '計', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.74280000000005, 'bottom': 351.74280000000005, 'doctop': 18592.86580000001}
# 資 {'matrix': (11.9, 0.0, 0, 14, 88.983, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 88.983, 'y0': 441.9562, 'x1': 100.88300000000001, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '資', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
# 活 {'matrix': (11.9, 0.0, 0, 14, 101.1805, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 101.1805, 'y0': 441.9562, 'x1': 113.0805, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '活', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
# 動 {'matrix': (11.9, 0.0, 0, 14, 113.378, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 113.378, 'y0': 441.9562, 'x1': 125.278, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '動', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
# 現 {'matrix': (11.9, 0.0, 0, 14, 125.5755, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 125.5755, 'y0': 441.9562, 'x1': 137.4755, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '現', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
# 金 {'matrix': (11.9, 0.0, 0, 14, 137.773, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 137.773, 'y0': 441.9562, 'x1': 149.673, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '金', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
# 流 {'matrix': (11.9, 0.0, 0, 14, 149.97050000000002, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 149.97050000000002, 'y0': 441.9562, 'x1': 161.87050000000002, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '流', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
# 入 {'matrix': (11.9, 0.0, 0, 14, 162.168, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 162.168, 'y0': 441.9562, 'x1': 174.068, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '入', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
# 小 {'matrix': (11.9, 0.0, 0, 14, 174.3655, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 174.3655, 'y0': 441.9562, 'x1': 186.2655, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '小', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
# 計 {'matrix': (11.9, 0.0, 0, 14, 186.56300000000002, 444.7422), 'fontname': 'PNKDCP+PMingLiU', 'adv': 1.0, 'upright': True, 'x0': 186.56300000000002, 'y0': 441.9562, 'x1': 198.46300000000002, 'y1': 455.9562, 'width': 11.900000000000006, 'height': 14.0, 'size': 14.0, 'mcid': None, 'tag': None, 'object_type': 'char', 'page_number': 24, 'ncs': 'DeviceCMYK', 'text': '計', 'stroking_color': (0, 0, 0, 1), 'stroking_pattern': None, 'non_stroking_color': (0, 0, 0, 1), 'non_stroking_pattern': None, 'top': 337.7448, 'bottom': 351.7448, 'doctop': 18592.86780000001}
