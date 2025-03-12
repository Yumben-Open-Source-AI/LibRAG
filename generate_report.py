# import json
#
# import openai
#
# local_llm = openai.OpenAI(
#     api_key='sk-3fb76d31383b4552b9c3ebf82f44157d',
#     base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
# )
#
# # system_prompt = """
# #     # Role：数据解析师
# #
# #     # Profile：
# #     - version：1.0
# #     - language：zh-cn
# #     - description：你将获得一个JSON数组作为现有数据，内容包含多个文件每页内容总结。你需要理解用户给出的操作提示，分析并通过对应操作如实准确无误的返回用户所需数据
# #     JSON数据结构解析：[{"filename": "文件名", "content": [{"description": "每一页文档的指标描述总结，下标表示第几页的描述"}]
# #
# #     # Skills
# #     - 擅长分析理解用户提供的
# #     - 擅长
# #
# #     # Rules
# #
# #     # Workflow
# # """
#
# with open('byd_info.json', 'r', encoding='utf-8') as f:
#     data = json.load(f)
# data = data[0]
#
# user_question = str(data) + """
# JSON结构解析：[{"filename": "文件名", "content": [{"description": "每一页文档的指标描述总结，下标即第几页的描述"}]，代表多个文件每页内容总结
# 理解JSON结构，从数据中获取第二页的歸屬於上市公司股東的淨利潤具体金额给我
# """
#
# completion = local_llm.chat.completions.create(
#     temperature=0.6,
#     model='deepseek-r1-distill-qwen-14b',
#     messages=[
#         {'role': 'user', 'content': user_question}
#     ],
#     max_tokens=16384,
#     timeout=12000
# )
# print(completion.choices[0].message.content)


with open('比亚迪汽车金融优先公司年度信息披露报告.md', 'r', encoding='utf-8') as f:
    data = f.read()
import re
print(re.findall(pattern=r'\{{.*?}\}', string=data))

