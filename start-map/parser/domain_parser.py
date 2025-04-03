import json
import uuid
import datetime
from string import Template
from llm.base import BaseLLM
from parser.base import BaseParser

DOMAIN_PARSE_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': """
            # Role: 领域分类专家
            
            ## Profile
            - author: LangGPT 
            - version: 1.1
            - language: 中文
            - description: 能根据文档类别名称与描述判断其所属的标准领域，优先从用户提供的已知领域中进行匹配，若无法匹配则生成新的标准领域结构。
            
            ## Skills
            1. 从类别语义中抽象提炼其归属领域，支持技术、财务、法律等知识领域。
            2. 优先匹配'known_domains'中的语义最相近者，避免重复创建领域。
            3. 输出标准领域结构，包括子类、关键词、是否为新建领域等元信息。
            4. 适用于构建文档知识图谱、自动归档系统、领域标签树等场景。
            
            ## Rules
            1. 类别归属应尽量与已有领域匹配，避免无意义的新建。
            2. 优先匹配用户提供的 known_domains 分类列表。
            3. 若无明确匹配领域或者领域数组为空，返回新建领域标记 new_domain: 'true'。
            
            ## Workflows
            1. 接收输入：
                - class_name（分类名称）
                - description（分类描述）
                - known_domains（已知领域数组，含 domain_name, domain_id, description 等字段，空数组代表没有已知领域）
            2. 解析分类的语义特征，优先匹配已有领域（按语义相关度）。
            3. 若匹配成功，返回匹配领域及 new_domain: 'false'，否则构建新领域结构。
            4. 输出 JSON 格式的领域信息结构。
            
            ## Example Output
            ```json
            {
                "domain_name": "",#填写领域名称
                "domain_id": "",
                "description": "领域描述:<>", #对应领域的描述信息
                "new_domain": 'true'/'false' #是否为新领域
            }
            ```
        """
    }
]

DOMAIN_PARSE_USER_MESSAGES = [
    {
        'role': 'user',
        'content': """读取分类信息，使用中文生成此分类所属的领域以及领域描述，最终按照Example Output样例生成完整json格式数据```<分类信息:<$cla>>```"""
    }
]


class DomainParser(BaseParser):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.domain = {}
        self.known_domains = []
        self.domain_cla_dic = {}
        self.new_domain = 'true'

    def parse(self, **kwargs):
        cla = kwargs.get('cla')
        class_name = cla['category_name']
        class_id = cla['category_id']
        description = cla['description']
        self.known_domains = self.__get_known_domains()
        print(self.known_domains)
        parse_params = {
            'class_name': class_name,
            'description': description,
            'known_domains': self.known_domains
        }
        content = Template(DOMAIN_PARSE_USER_MESSAGES[0]['content'])
        DOMAIN_PARSE_USER_MESSAGES[0]['content'] = content.substitute(cla=str(parse_params))
        print(DOMAIN_PARSE_USER_MESSAGES[0]['content'])
        self.domain = self.llm.chat(DOMAIN_PARSE_SYSTEM_MESSAGES + DOMAIN_PARSE_USER_MESSAGES)[0]
        print(self.domain)
        # llm judgments this document is not an added domain
        if self.domain['new_domain'] == 'false':
            sub_categories = self.domain_cla_dic[self.domain['domain_name']]
            # TODO 唯一性校验
            sub_categories.append(class_id)
            self.domain['sub_categories'] = sub_categories
        else:
            self.domain['domain_id'] = str(uuid.uuid4())
            self.domain.setdefault('sub_categories', []).append(class_id)
        self.domain.setdefault('metadata', {})['最后更新时间'] = datetime.datetime.now().strftime(
            '%Y-%m-%d %H:%M:%S')
        self.new_domain = self.domain['new_domain']
        return self.domain

    def __get_known_domains(self):
        """
        Getting Known Categories to Aid in Classification Selection for Large Language Models
        """
        with open(r'D:\xqm\python\project\llm\start-map\data\domain_info.json', 'r', encoding='utf-8') as f:
            domains = json.load(f)

        for domain in domains:
            self.domain_cla_dic[domain['domain_name']] = domain['sub_categories']
            del domain['sub_categories']
            del domain['metadata']
            del domain['parent']
            del domain['parent_description']

        return domains

    def storage_parser_data(self):
        if self.new_domain == 'true':
            del self.domain['new_domain']

            with open(r'D:\xqm\python\project\llm\start-map\data\domain_info.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.append(self.domain)

            with open(r'D:\xqm\python\project\llm\start-map\data\domain_info.json', 'w+', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False))
        else:
            del self.domain['new_domain']

            with open(r'D:\xqm\python\project\llm\start-map\data\domain_info.json', 'r', encoding='utf-8') as f:
                domains = json.load(f)

            for domain in domains:
                if domain['domain_id'] == self.domain['domain_id']:
                    domain['sub_categories'] = self.domain['sub_categories']
                    domain['metadata'] = self.domain['metadata']

            with open(r'D:\xqm\python\project\llm\start-map\data\domain_info.json', 'w+', encoding='utf-8') as f:
                f.write(json.dumps(domains, ensure_ascii=False))

    def back_fill_parent(self, parent):
        if parent is None:
            self.domain['parent'] = None
            self.domain['parent_description'] = None
