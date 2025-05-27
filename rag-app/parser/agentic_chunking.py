import uuid
import json
from typing import List, Dict
from pydantic import BaseModel
from dotenv import load_dotenv
from llm.llmchat import LlmChat
from tools.prompt_load import TextFileReader


# ---------- 数据模型 ----------
class ChunkMeta(BaseModel):
    chunk_id: str
    paragraph_name: str
    summary: str
    keywords: List[str]
    position: str
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
        self.llm = LlmChat()

        # 保存所有块
        self.chunks: Dict[str, ChunkMeta] = {}

        # ---- 三大角色的 system prompt ----
        self._proposition_system = TextFileReader().read_file("prompts/agent/AGENTIC_CHUNKING_PROPOSITION_STSTEM.TXT")

        self._summary_system = TextFileReader().read_file("prompts/agent/AGENTIC_CHUNKING_SUMMARY_STSTEM.TXT")

        self._allocation_system = TextFileReader().read_file("prompts/agent/AGENTIC_CHUNKING_ALLOCATION_STSTEM.TXT")

    # ======== 公共接口 ========
    def process(self, text: str) -> List[ChunkMeta]:
        """
        主入口：接收原始长文本，返回整理后的块列表。
        """
        print("##process text:" + text)
        propositions = self._extract_propositions(text)

        for prop in propositions:
            self._dispatch_proposition(prop)

        # 返回 Pydantic 模型列表，供外部使用
        return list(self.chunks.values())

    # ======== 私有工具 ========
    # ---- proposition 提取 ----
    def _extract_propositions(self, text: str) -> List[str]:
        messages = [
            self._proposition_system,
            text
        ]
        result = self.llm.chat(messages)  # 预计返回 JSON 数组
        print("##_extract_propositions result:" + str(result))
        return result

    # ---- 创建新块 ----
    def _create_new_chunk(self, proposition: str) -> str:
        chunk_id = str(uuid.uuid4())
        messages = [
            self._summary_system,
            f"txt_chunk:{proposition};"
        ]
        summary_res = self.llm.chat(messages)
        print("##_create_new_chunk summary_res:" + str(summary_res))
        self.chunks[chunk_id] = ChunkMeta(
            chunk_id=chunk_id,
            paragraph_name=summary_res.get("paragraph_name", ""),
            summary=summary_res.get("summary", ""),
            keywords=summary_res.get("keywords", []),
            position=summary_res.get("position", ""),
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
            self._summary_system,
            f"txt_chunk:{all_text};"
        ]
        summary_res = self.llm.chat(messages)
        print("##_add_to_chunk summary_res:" + str(summary_res))
        chunk.paragraph_name = summary_res.get("paragraph_name", chunk.paragraph_name)
        chunk.keywords = summary_res.get("keywords", chunk.keywords)
        chunk.position = summary_res.get("position", chunk.position)
        chunk.summary = summary_res.get("summary", chunk.summary)

    # ---- 判定归属 ----
    def _dispatch_proposition(self, proposition: str):
        if not self.chunks:
            self._create_new_chunk(proposition)
            return

        chunks_summaries = {cid: c.summary for cid, c in self.chunks.items()}
        messages = [
            self._allocation_system,
            f"已有块信息:{json.dumps(chunks_summaries, ensure_ascii=False)};proposition:{proposition};"
        ]
        alloc_res = self.llm.chat(messages)
        print("##_dispatch_proposition alloc_res:" + str(alloc_res))
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
