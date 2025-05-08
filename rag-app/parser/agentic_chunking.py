import uuid
import json
from typing import List, Dict
from pydantic import BaseModel
from dotenv import load_dotenv
from llm.qwen import Qwen

# ---------- 数据模型 ----------
class ChunkMeta(BaseModel):
    chunk_id: str
    title: str
    summary: str
    propositions: List[str]


# ---------- 业务类 ----------
class ChunkOrganizer:
    """
    封装命题提取、块摘要与归类逻辑的核心类。
    用法:
        organizer = ChunkOrganizer()
        chunks = organizer.process(text)
    """

    # ======== 初始化 ========
    def __init__(self):
        load_dotenv()
        self.llm = Qwen()

        # 保存所有块
        self.chunks: Dict[str, ChunkMeta] = {}

        # ---- 三大角色的 system prompt ----
        self._proposition_system = """
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
        输出一个JSON数组，每个元素是一个完整、可独立理解的简单命题字符串。
        
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
        你好！我是内容命题拆解专家✍️。请发送你想拆解的内容，我会帮你规范化处理成清晰的命题列表，方便你后续使用。"""

        self._summary_system = """
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
        你好！我是 summary_llm 文本摘要与标题生成专家✍️。请发送你需要处理的文本块，我会帮你提炼出精华摘要并拟定标题。"""

        self._allocation_system = """
        # Role: 命题归块判断与分配专家（allocation_llm）
        ## Profile
        - author: LangGPT
        - version: 1.0
        - language: 中文
        - description: 根据命题的主题大意，判断应将其归入哪个现有块，或是否需要新建一个块。判断时优先考虑语义相近的主题进行泛化归类。
        
        ## Skills
        - 理解命题的核心主题与含义。
        - 将主题相近、方向一致的命题合并到同一类。
        - 在无明确相似块时，合理建议新建块。
        
        ## Background
        在知识整理过程中，过度细化会导致冗余。需要以主题为基础，对命题进行泛化归类，提高结构紧凑性与整体可读性。
        
        ## Goals
        帮助用户将主题相近的命题归入同一块，降低碎片化程度，增强信息组织的聚合度。
        
        ## OutputFormat
        输出一个JSON对象，格式如下：
        {
          "action": "assign" 或 "create_new",
          "target_block_id": "（如果是 assign，填匹配的块id）"
        }
        
        ## Rules
        - 优先将主题相关的命题聚合到已有块中，即使细节不同。
        - 仅在新命题的主题明显与所有块不相关时，才建议创建新块。
        - 聚焦于“语义相似性”，而非完全内容重复。
        - 不要解释你的行为。
        
        ## Workflows
        1. 阅读当前命题，理解其核心主题。
        2. 浏览所有已有块摘要，寻找主题相近者。
        3. 判断是否可以归类到某一块，或是否有必要新建块。
        4. 输出操作建议（assign 或 create_new）。
        
        ## Init
        你好！我是 allocation_llm 命题归块判断专家✍️。请提供新命题和现有块摘要信息，我将帮你进行泛化归类判断。"""

    # ======== 公共接口 ========
    def process(self, text: str) -> List[ChunkMeta]:
        """
        主入口：接收原始长文本，返回整理后的块列表。
        """
        propositions = self._extract_propositions(text)

        for prop in propositions:
            self._dispatch_proposition(prop)

        # 返回 Pydantic 模型列表，供外部使用
        return list(self.chunks.values())

    # ======== 私有工具 ========
    # ---- proposition 提取 ----
    def _extract_propositions(self, text: str) -> List[str]:
        messages = [
            {"role": "system", "content": self._proposition_system},
            {"role": "user", "content": text}
        ]
        result = self.llm.chat(messages)[0]  # 预计返回 JSON 数组
        return result

    # ---- 创建新块 ----
    def _create_new_chunk(self, proposition: str) -> str:
        chunk_id = str(uuid.uuid4())
        messages = [
            {"role": "system", "content": self._summary_system},
            {"role": "user", "content": f"txt_chunk:{proposition};"}
        ]
        summary_res = self.llm.chat(messages)[0]

        self.chunks[chunk_id] = ChunkMeta(
            chunk_id=chunk_id,
            title=summary_res.get("title", ""),
            summary=summary_res.get("summary", ""),
            propositions=[proposition]
        )
        return chunk_id

    # ---- 将命题追加到已有块并更新摘要 ----
    def _add_to_chunk(self, chunk_id: str, proposition: str):
        chunk = self.chunks[chunk_id]
        chunk.propositions.append(proposition)

        # 重新生成块标题与摘要
        all_text = " ".join(chunk.propositions)
        messages = [
            {"role": "system", "content": self._summary_system},
            {"role": "user", "content": f"txt_chunk:{all_text};"}
        ]
        summary_res = self.llm.chat(messages)[0]
        chunk.title = summary_res.get("title", chunk.title)
        chunk.summary = summary_res.get("summary", chunk.summary)

    # ---- 判定归属 ----
    def _dispatch_proposition(self, proposition: str):
        if not self.chunks:
            self._create_new_chunk(proposition)
            return

        chunks_summaries = {cid: c.summary for cid, c in self.chunks.items()}
        messages = [
            {"role": "system", "content": self._allocation_system},
            {"role": "user",
             "content": f"已有块信息:{json.dumps(chunks_summaries, ensure_ascii=False)};proposition:{proposition};"}
        ]
        alloc_res = self.llm.chat(messages)[0]

        if alloc_res.get("action") == "create_new":
            self._create_new_chunk(proposition)
        else:  # assign
            target_id = alloc_res.get("target_block_id")
            if target_id in self.chunks:
                self._add_to_chunk(target_id, proposition)
            else:
                # 保险起见，目标不存在时新建块
                self._create_new_chunk(proposition)


if __name__ == "__main__":
    print("请输入文本，结束后回车空行：")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    text = "\n".join(lines)
    import time
    start_time = time.time()
    organizer = ChunkOrganizer()
    blocks = organizer.process(text)
    for blk in blocks:
        print(blk.model_dump())
    end_time = time.time()
    print("程序运行时间：%s 秒" % (end_time - start_time))