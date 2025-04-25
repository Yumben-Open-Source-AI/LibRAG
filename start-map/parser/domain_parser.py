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
            - version: 1.2
            - language: 中文
            - description: 能根据文档类别名称与描述判断其所属的标准领域，先从用户提供的已知领域中进行匹配，匹配时优先关注 `domain_description` 而不是 `domain_name`，若匹配成功但描述不清晰可优化，或已知领域不适合该分类则生成新的标准领域结构，并支持对已有领域描述进行增强与补充。
            
            ## Skills
            1. 从类别语义中抽象提炼其归属领域，支持技术、财务、法律等知识领域。
            2. 优先匹配“已知领域列表”中的领域，避免重复创建相似领域。
            3. 若匹配成功但领域描述不清晰、范围不够全面，能根据分类描述对领域描述进行合理优化补充。
            4. 若无法匹配，或已知领域不适合该分类则生成新的标准领域结构。
            5. 输出标准领域结构，包括子类、关键词、是否为新建领域等元信息。
            
            ## Rules
            1. 类别归属应尽量与已有领域匹配，避免无意义的新建。
            2. 优先匹配用户提供的 `known_domains` 分类列表。
            3. 匹配时需严格判断语义场景，对于具有明显对内或对外属性的类别，应避免将其归入语义方向不符的领域，例如对外交流、合同、投标等业务行为不应归类到强调内部结构或管理的信息类领域。
            4. 匹配逻辑优先使用 `domain_description` 进行判断，其次考虑 `domain_name`。
            5. 若无明确匹配领域或者已知领域语义不符或领域数组为空，返回新建领域标记 `new_domain: 'true'`
            6. 若匹配成功但原有领域描述不够清晰全面，应在保留原始语义的基础上进行补充优化。
            7. 新建或优化领域时的 `domain_description` 应具备抽象性、可覆盖多个场景，不得冗长或含糊。
            
            ## Workflows
            1. 接收输入：
                - category_name（分类名称）
                - category_description（分类描述）
                - known_domains（已知领域列表，含 domain_name, domain_id, domain_description 等）
            2. 解析分类的语义特征，优先匹配已有领域（按语义相关度）。
            3. 若描述明显涉及对外活动、文件交付或客户互动，应优先排除“内部管理”类领域匹配。
            4. 匹配成功后，判断当前领域描述是否适配当前分类，若不清晰可进行优化后输出。
            5. 若匹配失败，则构建新领域结构并标记 `new_domain: 'true'`
            6. 输出 JSON 格式的领域信息结构，包含是否为新领域与最终描述。
            
            ## Example Output
            ```json
            {
                "domain_name": "",#填写领域名称；
                "domain_id": "",
                "domain_description": "<>", # 对应领域的描述信息，若有优化应包含原始信息的扩展；
                "new_domain": 'true'/'false' #是否为新领域；
            } 
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
    def __init__(self, llm: BaseLLM, kb_id, session):
        super().__init__(llm, kb_id, session)
        self.domain = {}
        self.known_domains = []
        self.domain_cla_dic = {}
        self.new_domain = 'true'
        self.save_path = os.path.join(self.base_path, 'domain_info.json')

    def parse(self, **kwargs):
        cla = kwargs.get('cla')
        category_name = cla['category_name']
        category_id = cla['category_id']
        category_description = cla['category_description']
        parse_params = {
            'category_name': category_name,
            'category_description': category_description,
            'known_domains': self.__get_known_domains()
        }
        parse_messages = copy.deepcopy(DOMAIN_PARSE_MESSAGES)
        content = Template(parse_messages[1]['content'])
        parse_messages[1]['content'] = content.substitute(cla=str(parse_params))
        self.domain = self.llm.chat(parse_messages)[0]
        # llm judgments this document is not an added domain
        if self.domain['new_domain'] == 'false':
            sub_categories = self.domain_cla_dic[self.domain['domain_name']]
            if not any(category_id == category for category in sub_categories):
                sub_categories.append(category_id)
            self.domain['sub_categories'] = sub_categories
        else:
            self.domain['kb_id'] = self.kb_id
            self.domain['domain_id'] = str(uuid.uuid4())
            self.domain.setdefault('sub_categories', []).append(category_id)
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
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            del self.domain['new_domain']

            with open(self.save_path, 'r', encoding='utf-8') as f:
                domains = json.load(f)

            for domain in domains:
                if domain['domain_id'] == self.domain['domain_id']:
                    domain['metadata'] = self.domain['metadata']
                    domain['sub_categories'] = self.domain['sub_categories']
                    domain['domain_description'] = self.domain['domain_description']

            with open(self.save_path, 'w+', encoding='utf-8') as f:
                json.dump(domains, f, ensure_ascii=False, indent=2)

    def back_fill_parent(self, parent):
        # 若生成新领域数据则回填上级数据
        if self.new_domain == 'true':
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
