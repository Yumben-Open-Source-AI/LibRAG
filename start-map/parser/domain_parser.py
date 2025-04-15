import copy
import json
import os
import uuid
import datetime
from string import Template
from llm.base import BaseLLM
from parser.base import BaseParser

DOMAIN_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': """
            # Role: 领域分类专家
            ## Profile
            - author: LangGPT 
            - version: 1.1
            - language: 中文
            - description: 能根据文档类别名称与描述判断其所属的标准领域，先从用户提供的已知领域中进行匹配，进行匹配时优先关注`description`而不是`domain_name`，若无法匹配或已知领域不适合该分类则生成新的标准领域结构。
            
            ## Skills
            1. 从类别语义中抽象提炼其归属领域，支持技术、财务、法律等知识领域。
            2. 优先匹配“已知领域列表”中的领域，避免重复创建相似领域。
            3. 若无法匹配，或已知领域不适合该分类则生成新的标准领域结构。
            4. 输出标准领域结构，包括子类、关键词、是否为新建领域等元信息。
            5. 适用于构建文档知识图谱、自动归档系统、领域标签树等场景。
            
            ## Rules
            1. 类别归属应尽量与已有领域匹配，避免无意义的新建。
            2. 优先匹配用户提供的 `known_domains` 分类列表。
            3. 匹配时需严格判断语义场景，对于具有明显对内或对外属性的类别，应避免将其归入语义方向不符的领域，例如对外交流、合同、投标等业务行为不应归类到强调内部结构或管理的信息类领域。
            4. 若无明确匹配领域或已知领域语义不符，返回新建领域标记 `new_domain: true`。
            5. 进行匹配时优先关注`description`而不是`domain_name`，但应结合实际业务场景进行语义逻辑判断。
            
            ## Workflows
            1. 接收输入：
                - category_name（分类名称）
                - description（分类描述）
                - known_domains（已知领域列表，含 domain_name, domain_id, description 等）
            2. 解析分类的语义特征，优先匹配已有领域（按语义相关度）。
            3. 若描述明显涉及对外活动、文件交付或客户互动，应优先排除“内部管理”类领域匹配。
            4. 若匹配成功，返回匹配领域及 `new_domain: false`，否则构建新领域结构。
            5. 输出 JSON 格式的领域信息结构。
            
            ## Example Output
            ```json
            {
                "domain_name": "",#填写领域名称
                "domain_id": "",
                "description": "领域描述:<>", #对应领域的描述信息,
                "new_domain": 'true'/'false' #是否为新领域
            }
            ```
            Warning:
            -输出不要增加额外字段，严格按照Example Output结构输出。
            -不要解释行为。
        """
    },
    {
        'role': 'user',
        'content': """读取文档，使用中文生成或选择此分类所属的领域以及领域描述，最终按照Example Output样例生成完整json格式数据```<分类信息:<$cla>>```"""
    }
]


class DomainParser(BaseParser):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.domain = {}
        self.known_domains = []
        self.domain_cla_dic = {}
        self.new_domain = 'true'
        self.save_path = os.path.join(self.base_path, 'domain_info.json')

    def parse(self, **kwargs):
        cla = kwargs.get('cla')
        category_name = cla['category_name']
        class_id = cla['category_id']
        description = cla['description']
        parse_params = {
            'category_name': category_name,
            'description': description,
            'known_domains': self.__get_known_domains()
        }
        parse_messages = copy.deepcopy(DOMAIN_PARSE_MESSAGES)
        content = Template(parse_messages[1]['content'])
        parse_messages[1]['content'] = content.substitute(cla=str(parse_params))
        self.domain = self.llm.chat(parse_messages)[0]
        # llm judgments this document is not an added domain
        if self.domain['new_domain'] == 'false':
            sub_categories = self.domain_cla_dic[self.domain['domain_name']]
            if not any(class_id == category for category in sub_categories):
                sub_categories.append(class_id)
            self.domain['sub_categories'] = sub_categories
        else:
            self.domain['domain_id'] = str(uuid.uuid4())
            self.domain.setdefault('sub_categories', []).append(class_id)
        self.domain.setdefault('metadata', {})['最后更新时间'] = datetime.datetime.now().strftime(
            '%Y-%m-%d %H:%M:%S')
        self.new_domain = self.domain['new_domain']
        return self.domain

    def storage_parser_data(self):
        if self.new_domain == 'true':
            del self.domain['new_domain']

            with open(self.save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.append(self.domain)

            with open(self.save_path, 'w+', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False))
        else:
            del self.domain['new_domain']

            with open(self.save_path, 'r', encoding='utf-8') as f:
                domains = json.load(f)

            for domain in domains:
                if domain['domain_id'] == self.domain['domain_id']:
                    domain['sub_categories'] = self.domain['sub_categories']
                    domain['metadata'] = self.domain['metadata']

            with open(self.save_path, 'w+', encoding='utf-8') as f:
                f.write(json.dumps(domains, ensure_ascii=False))

    def back_fill_parent(self, parent):
        if parent is None:
            self.domain['parent'] = None
            self.domain['parent_description'] = None

    def rebuild_domain(self):
        ...

    def __get_known_domains(self):
        """
        Getting Known Categories to Aid in Classification Selection for Large Language Models
        """
        with open(self.save_path, 'r', encoding='utf-8') as f:
            domains = json.load(f)

        for domain in domains:
            self.domain_cla_dic[domain['domain_name']] = domain['sub_categories']
            del domain['sub_categories']
            del domain['metadata']
            del domain['parent']
            del domain['parent_description']

        return domains
