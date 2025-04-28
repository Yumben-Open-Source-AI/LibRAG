import uuid
import json
from typing import List, Dict
from pydantic import BaseModel
from dotenv import load_dotenv
from llm.qwen import Qwen

# 加载配置文件密钥
load_dotenv()
qwen = Qwen()

# === Pydantic 模型定义 ===
class Sentences(BaseModel):
    sentences: List[str]

class ChunkMeta(BaseModel):
    chunk_id: str
    title: str
    summary: str
    propositions: List[str]

class ChunkID(BaseModel):
    chunk_id: str

# === LLM 角色设定 ===
PROPOSITION_MESSAGES = [{ 'role': 'system', 'content': """
            # Role: 内容命题拆解专家
            ## Profile              
            - author: LangGPT
            - version: 1.0
            - language: 中文
            - description: 将长文本拆解为清晰、简单、脱离上下文可独立理解的命题，以JSON字符串列表的形式输出。
            
            ## Skills
            - 拆分并列句为简单句，尽量保持原始措辞。
            - 将带有描述性信息的命名实体与主体信息分开成独立命题。
            - 替换代词为完整实体名词，并适度补充修饰信息确保句子独立可理解。
            - 精确遵循JSON数组输出格式，确保每条是独立命题。
            
            ## Background
            在处理中文复杂叙述时，为方便知识抽取、AI学习或信息重组，需要将原文信息结构化为独立、完整的小命题单元。
            
            ## Goals
            帮助用户将长文内容拆分为规范、清晰的小命题列表，便于后续处理。
            
            ## OutputFormat
            输出一个JSON数组，每个元素是一个完整、可独立理解的简单中文命题字符串。
            
            ## Rules
            - 保持输入原文措辞，只在必要时补充修饰或改写以保证独立性。
            - 代词（如“他”、“她”、“它”、“他们”等）需替换为所指实体全名。
            - 一个简单句只描述一个核心事实或描述。
            - 忠实于原文，不添加主观推断。
            - 代词回指处理，补全引用实体。
            
            ## Workflows
            1. 阅读并理解输入文本内容和逻辑结构。
            2. 逐句分析并列关系，拆分成独立简单句。
            3. 分离命名实体及其描述，补充必要信息。
            4. 代词回指处理，补全引用实体。
            5. 生成JSON数组形式的输出，每条为独立命题。
            
            ## Init
            你好！我是内容命题拆解专家✍️。请发送你想拆解的内容，我会帮你规范化处理成清晰的命题列表，方便你后续使用。""" }, {'role': 'user'}]

SUMMARY_MESSAGES = [{ 'role': 'system', 'content': """
            # Role: 文本摘要与标题生成专家（summary_llm）
            ## Profile
            - author: LangGPT
            - version: 1.0
            - language: 中文
            - description: 针对给定的一段文本块，生成一个简明扼要的摘要，以及一个精准概括内容的标题。
            
            ## Skills
            - 从复杂文本中提取关键信息。
            - 用简洁、准确的语言总结文本内容。
            - 根据文本主旨创作具有概括性的标题。
            
            ## Background
            在处理大量文本信息时，需要快速提取要点和生成清晰的标题，以便于信息检索、归类和阅读。
            
            ## Goals
            帮助用户从任意文本中提炼出高质量的摘要和符合内容主题的标题。
            
            ## OutputFormat
            输出一个JSON对象，格式如下：
            { 
            "title": "简洁概括的标题",
            "summary": "简明扼要的摘要"
            }
            
            ## Rules
            - 摘要应覆盖文本中的主要观点，控制在50-150字以内。
            - 标题应高度凝练，不超过15字。
            - 保持客观、中立，不添加主观评价。
            - 必须用标准中文输出。
            
            ## Workflows
            1. 阅读输入文本，理解核心内容和主旨。
            2. 提取文本中的关键信息和重要细节。
            3. 生成内容清晰、易于理解的摘要。
            4. 创作符合内容主题且吸引人的标题。
            
            ## Init
            你好！我是 summary_llm 文本摘要与标题生成专家✍️。请发送你需要处理的文本块，我会帮你提炼出精华摘要并拟定标题。""" }, {'role': 'user'}]

ALLOCATION_MESSAGES = [{ 'role': 'system', 'content': """
            # Role: 命题归块判断与分配专家（allocation_llm）
            ## Profile
            - author: LangGPT
            - version: 1.0
            - language: 中文
            - description: 根据输入的命题内容，判断其应归入已有的文本块，或者建议新建一个新块。
            
            ## Skills
            - 精确理解命题内容与现有文本块的主题。
            - 判断命题与块之间的相关性。
            - 在缺乏匹配的情况下，合理建议创建新块。
            
            ## Background
            在结构化知识管理或文档自动整理过程中，需要根据内容语义快速归类或分组，提高信息的组织性和检索效率。
            
            ## Goals
            帮助用户智能地将新命题归入最合适的已有块，或在必要时建议新建块。
            
            ## OutputFormat
            输出一个JSON对象，格式如下：
            {
            "action": "assign" 或 "create_new",
            "target_block_title": "（如果是assign，填匹配的块标题）",
            "reason": "详细说明为什么选择该块或建议新建块"
            }
            
            ## Rules
            - 归类时优先寻找语义最接近的已有块。
            - 如无合适匹配，建议新建块，并说明原因。
            - 保持判断的客观性，不随意归类。
            - 必须用标准中文输出。
            
            ## Workflows
            1. 阅读新命题和已有的块标题/摘要。
            2. 对比命题与块之间的主题相关度。
            3. 判断是归入已有块还是新建块。
            4. 输出操作指令和理由说明。
            
            ## Init
            你好！我是 allocation_llm 命题归块判断专家✍️。请发送新的命题和已有的块信息，我将帮你判断归属或建议新建块。""" }, {'role': 'user'}]

# === LLM实例 ===
summary_llm = qwen
allocation_llm = qwen

# === 核心模块 ===
chunks: Dict[str, ChunkMeta] = {}

# 新建块
def create_new_chunk(proposition: str) -> str:
    chunk_id = str(uuid.uuid4())
    SUMMARY_MESSAGES[1]['content'] = f'txt_chunk:{proposition};'
    result = summary_llm.chat(SUMMARY_MESSAGES)[0]

    new_chunk = ChunkMeta(
        chunk_id=chunk_id,
        title=result.get('title', ''),
        summary=result.get('summary', ''),
        propositions=[proposition]
    )
    chunks[chunk_id] = new_chunk
    return chunk_id

# 添加命题到已有块
def add_proposition(chunk_id: str, proposition: str):
    chunk = chunks[chunk_id]
    chunk.propositions.append(proposition)
    # 更新块的标题和摘要
    SUMMARY_MESSAGES[1]['content'] = f'txt_chunk:{" ".join(chunk.propositions)};'
    result = summary_llm.chat(SUMMARY_MESSAGES)[0]
    chunk.title = result.get('title', chunk.title)
    chunk.summary = result.get('summary', chunk.summary)
    chunks[chunk_id] = chunk

# 决定放到哪个块
def find_chunk_and_push_proposition(proposition: str):
    if not chunks:
        create_new_chunk(proposition)
        return

    chunks_summaries = {chunk_id: chunk.summary for chunk_id, chunk in chunks.items()}
    ALLOCATION_MESSAGES[1]['content'] = f'已有块信息:{json.dumps(chunks_summaries, ensure_ascii=False)};proposition:{proposition};'
    result = allocation_llm.chat(ALLOCATION_MESSAGES)[0]

    action = result.get('action')
    if action == 'create_new':
        create_new_chunk(proposition)
    elif action == 'assign':
        target_chunk_id = result.get('target_block_title')
        if target_chunk_id in chunks:
            add_proposition(target_chunk_id, proposition)
        else:
            create_new_chunk(proposition)

# === 主流程 ===
def extraction_chain(text:str):
    print("请输入文本，结束后回车空行：")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    text = "\n".join(lines)

    PROPOSITION_MESSAGES[1]['content'] = text
    print(PROPOSITION_MESSAGES[1])
    result = qwen.chat(PROPOSITION_MESSAGES)[0]
    print("proposition_list:"+ str(result))
    proposition_list = result

    for proposition in proposition_list:
        print("proposition:"+proposition)
        find_chunk_and_push_proposition(proposition)

    # 输出整理结果
    print(json.dumps([chunk.dict() for chunk in chunks.values()], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    extraction_chain()