"""
@Project ：LibRAG 
@File    ：decorator.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/5/13 上午11:04 
"""
import ast
import copy
import re
from math import ceil
from concurrent.futures import ThreadPoolExecutor, as_completed

PUNCT_CLASSES = {
    "(": r"[\(\（]",
    ")": r"[\)\）]",
    ",": r"[,，]",
    ":": r"[:：]",
    ";": r"[;；]",
    ".": r"[\.。]",
    "!": r"[!！]",
    "?": r"[\?？]",
    "-": r"[-－﹣_]",
    "/": r"[/／]",
}


def normalize_punctuation(text):
    for standard_char, pattern in PUNCT_CLASSES.items():
        text = re.sub(pattern, standard_char, text)
    return text

def concurrent_decorator(func):
    def wrapper(*args, **kwargs):
        llm = args[0]
        messages = args[1]
        count = kwargs.get('count', 0)
        if not count:
            return func(*args, **kwargs)
        contents = ast.literal_eval(messages[-1]['content'])
        if 'input_text' not in contents:
            return func(*args, **kwargs)

        input_text = contents['input_text']
        del contents['input_text']
        key = list(contents.keys())[0]
        values = list(contents.values())[0]

        if not isinstance(values, list):
            return func(*args, **kwargs)

        tasks = []
        all_messages_result = []
        max_workers = ceil(len(values) / count)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i in range(0, len(values), count):
                thread_messages = copy.deepcopy(messages)
                thread_messages[-1]['content'] = str({
                    'input_text': input_text,
                    key: values[i: i + count]
                })
                tasks.append(executor.submit(func, llm, messages=thread_messages, count=count))

            for task in as_completed(tasks):
                # 获取不同层级选择器选项key值保持1个
                print(task.result()[0])
                selected_key = list(task.result()[0].keys())[0]
                all_messages_result.extend(task.result()[0][selected_key])

        return all_messages_result

    return wrapper
