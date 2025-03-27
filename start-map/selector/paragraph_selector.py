import json
import datetime
from typing import List, Dict

from llm.base import BaseLLM
from selector.base import BaseSelector

# system action
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
PARAGRAPH_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': f"""
            ### 当前时间
            {now}
            ### 工作描述
            您是一个智能文档匹配引擎，能够理解用户输入的查询，并在预定义的文档列表中匹配最相关的文档。您的任务是分析用户输入，从中提取关键词，并基于文档描述选择最符合的文档。
            ### 任务
            1. **关键词提取**：从用户输入中提取有助于匹配的关键词。
            2. **文档匹配**：根据提取的关键词，匹配与之最相关的文档。
            3. **格式化输出**：仅返回 JSON 格式的数据，包括提取的关键词和匹配的文档。
            ### 输入格式
            - `input_text`：用户输入的一段自由文本，表示用户的查询需求。
            - `documents`：可选的文档列表，每个文档包含：
              - `document_id`（文档唯一标识）
              - `document_description`（文档描述信息）
            - `classification_instructions`（可选）：额外的匹配指令（如有）。
            ### 约束
            - **仅返回 JSON 格式的响应**，不得包含额外的文本解释。
            - **不得生成虚假信息**，仅基于已有的 `documents` 进行匹配。
        """
    }
]

# few shot example input output
PARAGRAPH_FEW_SHOT_MESSAGES = [
    {
        'role': 'user',
        'content': """{
            "input_text": "2023年新能源汽车补贴政策调整有哪些？",
            "documents": [
                {
                    "document_id": "6a9f1a62-d4a5-4c93-872f-2d74b9e2b681",
                    "document_description": "2023年新能源汽车补贴政策全文，涵盖补贴标准调整、补贴申领流程变更及适用车型范围。"
                },
                {
                    "document_id": "e3d4a8b9-72cf-46e5-b4f8-f98c612d9e36",
                    "document_description": "2023年新能源汽车购置税减免政策，适用于特定新能源车型，规定购置税免除标准。"
                },
                {
                    "document_id": "政策汇编-2022.pdf",
                    "document_description": "2022年新能源行业相关政策汇编，包括财政补贴、市场监管、税收优惠等。"
                }
            ],
            "classification_instructions": []
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "keywords": ["新能源汽车", "补贴政策", "2023年", "调整"],
            "selected_documents": [
                {
                    "document_id": "6a9f1a62-d4a5-4c93-872f-2d74b9e2b681",
                    "document_description": "2023年新能源汽车补贴政策全文，涵盖补贴标准调整、补贴申领流程变更及适用车型范围。"
                },
                {
                    "document_id": "e3d4a8b9-72cf-46e5-b4f8-f98c612d9e36",
                    "document_description": "2023年新能源汽车购置税减免政策，适用于特定新能源车型，规定购置税免除标准。"
                }
            ]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "比亚迪最近的高管变动情况？",
            "documents": [
                {
                    "document_id": "cfa82b11-5f6c-4a9a-8f21-3d2d9e7b1b45",
                    "document_description": "2022年比亚迪公司管理层调整公告，涉及新任CFO及多名高管调整。"
                },
                {
                    "document_id": "比亚迪股份有限公司 2024年人事变更公告（2024-06-15）.pdf",
                    "document_description": "比亚迪2024年最新人事调整，涉及董事会成员变更、新任CEO上任。"
                },
                {
                      "document_id": "9d6c319b-d86e-4c23-8a1f-5d56729a9c13",
                      "document_description": "2023年比亚迪人事调整文件，包含多个部门高管轮岗及管理层架构优化。"
                }
            ],
            "classification_instructions": []
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "keywords": ["比亚迪", "高管变动", "最近", "人事调整"],
            "selected_documents": [
                {
                    "document_id": "比亚迪股份有限公司 2024年人事变更公告（2024-06-15）.pdf",
                    "document_description": "比亚迪2024年最新人事调整，涉及董事会成员变更、新任CEO上任。"
                }
            ]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "比亚迪今年在欧洲的销量如何？",
            "documents": [
                {
                    "document_id": "f3c27e94-1d72-4e86-b9e8-97b542ef1e63",
                    "document_description": "比亚迪2023年全球市场销量报告，包含欧洲、北美和亚洲市场的增长趋势。"
                },
                {
                    "document_id": "2022年比亚迪全球销量数据.pdf",
                    "document_description": "比亚迪2022年全球销量分析，涵盖主要市场份额及竞争态势。"
                }
            ],
            "classification_instructions": []
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "keywords": ["比亚迪", "欧洲", "销量", "今年"],
            "selected_documents": [
                {
                    "document_id": "f3c27e94-1d72-4e86-b9e8-97b542ef1e63",
                    "document_description": "比亚迪2023年全球市场销量报告，包含欧洲、北美和亚洲市场的增长趋势。"
                }
            ]
        }"""
    },
]

PARAGRAPH_USER_PROMPT = """
    "input_text": "{question}",
    "documents": "{paragraph_params}",
    "classification_instructions": []
"""


class ParagraphSelector(BaseSelector):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.selected_paragraphs = None
        self.params = []
        self.paragraphs = self.get_layer_data()

    def get_layer_data(self):
        with open('data/byd_info.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data

    def collate_select_params(self, params: List[Dict] = None):
        parsed_data = self.paragraphs
        selected_documents = params

        filename_to_data = {item['filename']: item.get('content', []) for item in parsed_data}
        next_layer_params = []
        for doc in selected_documents:
            doc_id = doc["document_id"]

            if doc_id in filename_to_data:
                content_list = filename_to_data[doc_id]

                for content in content_list:
                    next_layer_params.append({
                        "document_id": content["index"],
                        "document_description": content["summary"]
                    })

        self.params = next_layer_params
        return self

    def start_select(self, question: str, params: List[Dict] = None):
        user_messages = [
            {
                'role': 'user',
                'content': '{' + PARAGRAPH_USER_PROMPT.format(question=question, paragraph_params=self.params) + '}'
            }
        ]
        response_chat = self.llm.chat(PARAGRAPH_SYSTEM_MESSAGES + PARAGRAPH_FEW_SHOT_MESSAGES + user_messages)
        content, total_token = response_chat
        self.selected_paragraphs = self.llm.literal_eval(content)['selected_documents']
        return self

    def collate_select_result(self) -> List:
        # 建立辅助结构：
        #   - index_map: index -> (filename, { "index": ..., "description": ... })
        #   - file_desc_map: filename -> overall_description
        index_map = {}
        file_desc_map = {}

        for file_item in self.paragraphs:
            filename = file_item["filename"]
            overall_desc = file_item.get("overall_description", "")
            file_desc_map[filename] = overall_desc

            for content in file_item.get("content", []):
                index_map[content["index"]] = (filename, content)

        # 按 filename 分组收集匹配到的内容（index + description）
        filename_to_contents = {}
        for doc in self.selected_paragraphs:
            doc_id = doc["document_id"]  # 即 content[i]["index"]
            if doc_id in index_map:
                filename, content_item = index_map[doc_id]
                # 需要的内容包含 index 和 description
                needed_info = {
                    "index": content_item["index"],
                    "description": content_item["description"]
                }
                filename_to_contents.setdefault(filename, []).append(needed_info)

        # 组装最终输出结构
        result_list = []
        for filename, contents in filename_to_contents.items():
            result_list.append({
                "filename": filename,
                "content": contents,
                "overall_description": file_desc_map.get(filename, "")
            })

        return result_list
