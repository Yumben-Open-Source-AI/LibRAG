import copy
import datetime
import math
import os
from string import Template
from typing import Dict, Optional

from llm.llmchat import LlmChat
from parser.base import BaseParser
from tools.log_tools import parser_logger as logger
from tools.prompt_load import TextFileReader
from web_server.ai.models import Document, Category

# parse() 会先根据可选的 compression_config 调整阈值，然后调用 tidy_up_data() 将原始段落简化为仅含 summary 的列表，并交给 _compress_paragraphs() 判断总长度是否超过限制。
#
# _compress_paragraphs() 会检测序列化后的长度，若超限则进入循环，持续用 _summarise_groups() 进行分组压缩，直到总长度回到阈值以内或只剩一个摘要。
#
# _summarise_groups() 使用 _determine_group_size() 计算分组大小，逐组调用 _summarise_chunk()，后者基于成对的系统/用户提示词请求 LLM 输出合并摘要，必要时回退到简单拼接。
#
# 完成分组汇总后，压缩得到的摘要列表会被重新注入到主提示词模板中，作为最终文档解析的输入，符合您描述的“先分组迭代压缩，再把汇总摘要喂给文档解析器”的流程。
# 文档解析主提示词配置
DOCUMENT_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/parse/DOCUMENT_SYSTEM.txt")
    },
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/parse/DOCUMENT_USER.txt")
    }
]

# 段落分组压缩提示词配置
GROUP_SUMMARY_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/parse/DOCUMENT_GROUP_SUMMARY_SYSTEM.txt")
    },
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/parse/DOCUMENT_GROUP_SUMMARY_USER.txt")
    }
]


class DocumentParser(BaseParser):
    """负责解析文档并在必要时进行段落压缩的解析器。"""

    # 默认可接受的段落序列序列化长度上限
    DEFAULT_MAX_PARAGRAPH_PAYLOAD = 12000
    # 默认手动配置的分组大小
    DEFAULT_GROUP_SIZE = 8
    # 自动模式下允许的最小分组大小
    MIN_AUTOMATIC_GROUP_SIZE = 2

    def __init__(
        self,
        llm: LlmChat,
        kb_id,
        session,
        *,
        max_paragraph_payload: Optional[int] = None,
        group_size: Optional[int] = None,
    ):
        super().__init__(llm, kb_id, session)
        self.document = None
        # 解析最大段落负载配置，优先使用传入参数，其次环境变量，最后默认值
        self.max_paragraph_payload = self._resolve_int_config(
            provided=max_paragraph_payload,
            env_key='DOCUMENT_PARSER_MAX_PAYLOAD',
            default=self.DEFAULT_MAX_PARAGRAPH_PAYLOAD,
        )
        # 解析分组大小配置，支持同样的多层优先级
        self.group_size = self._resolve_int_config(
            provided=group_size,
            env_key='DOCUMENT_PARSER_GROUP_SIZE',
            default=self.DEFAULT_GROUP_SIZE,
        )

    def tidy_up_data(self, paragraphs):
        """整理段落数据并在必要时触发压缩流程。"""
        paragraphs = paragraphs or []
        tidy_paragraphs = [{
            'summary': paragraph['summary'],
        } for paragraph in paragraphs]
        # 判断总长度是否超过限制
        return self._compress_paragraphs(tidy_paragraphs)

    @classmethod
    def _serialize_paragraphs(cls, paragraphs):
        """统一的段落序列化方法，方便计算长度并传给模型。"""
        return repr(paragraphs)

    @staticmethod
    def _resolve_int_config(*, provided: Optional[int], env_key: str, default: int) -> int:
        """从参数或环境变量解析数值配置，并在异常时回退默认值。"""
        if provided is not None:
            try:
                return max(0, int(provided))
            except (TypeError, ValueError):
                logger.warning('Invalid provided value for %s: %s', env_key, provided)
        env_value = os.getenv(env_key)
        if env_value is not None:
            try:
                return max(0, int(env_value))
            except ValueError:
                logger.warning('Invalid environment value for %s: %s', env_key, env_value)
        return default

    def _configure_compression(self, config: Dict):
        """根据运行时传入的配置动态调整压缩策略。"""
        if not isinstance(config, dict):
            logger.warning('Compression configuration must be a dictionary, received: %s', type(config))
            return

        if 'max_paragraph_payload' in config:
            self.max_paragraph_payload = self._resolve_int_config(
                provided=config.get('max_paragraph_payload'),
                env_key='DOCUMENT_PARSER_MAX_PAYLOAD',
                default=self.max_paragraph_payload,
            )

        if 'group_size' in config:
            self.group_size = self._resolve_int_config(
                provided=config.get('group_size'),
                env_key='DOCUMENT_PARSER_GROUP_SIZE',
                default=self.group_size,
            )

    def _compress_paragraphs(self, paragraphs):
        """根据配置判断是否需要压缩段落列表并执行多层汇总。"""
        serialized_length = len(self._serialize_paragraphs(paragraphs))
        if self.max_paragraph_payload <= 0:
            return paragraphs

        if serialized_length <= self.max_paragraph_payload:
            return paragraphs

        logger.info(
            'DocumentParser detected oversized paragraph payload (%s chars), applying hierarchical summarisation.',
            serialized_length
        )

        grouped = paragraphs
        # 若超限则进入循环，持续用 _summarise_groups() 进行分组压缩，直到总长度回到阈值以内或只剩一个摘要
        while len(self._serialize_paragraphs(grouped)) > self.max_paragraph_payload and len(grouped) > 1:
            grouped = self._summarise_groups(grouped)

        return grouped

    def _summarise_groups(self, paragraphs):
        """将段落按分组进行压缩，输出更短的摘要列表。"""
        compressed = []
        # 计算出分组的大小（每组包含多少段落）
        step = self._determine_group_size(len(paragraphs))
        # 表示从0开始，每次增加step值，直到覆盖所有段落,例如如果有10个段落，step=3，那么会分成4组：0-2, 3-5, 6-8, 9
        for start in range(0, len(paragraphs), step):
            chunk = paragraphs[start:start + step]
            # 逐组调用 _summarise_chunk()，后者基于成对的系统/用户提示词请求 LLM 输出合并摘要
            summary_text = self._summarise_chunk(chunk)
            compressed.append({'summary': summary_text})
        return compressed

    def _determine_group_size(self, paragraph_count: int) -> int:
        """计算当前批次段落应使用的分组大小。"""
        # 使用配置的分组大小：
        # 如果configured_size存在并且大于1，则直接返回这个配置值。
        configured_size = self.group_size
        if configured_size and configured_size > 1:
            return configured_size

        # 自动模式：
        # 如果段落数量paragraph_count小于或等于0，则返回1。
        if paragraph_count <= 0:
            return 1
        # 为小段落集计算分组大小：
        # 如果段落数量小于或等于self.MIN_AUTOMATIC_GROUP_SIZE（默认为2），则返回1或段落数量中的较大值。
        if paragraph_count <= self.MIN_AUTOMATIC_GROUP_SIZE:
            return max(1, paragraph_count)
        # 为大段落集动态计算分组大小：
        # 使用数学平方根来计算动态的分组大小，确保结果不小于self.MIN_AUTOMATIC_GROUP_SIZE。
        dynamic_size = max(
            self.MIN_AUTOMATIC_GROUP_SIZE,
            int(math.ceil(math.sqrt(paragraph_count)))
        )
        logger.info(
            'DocumentParser automatically calculated group size %s for %s paragraphs.',
            dynamic_size,
            paragraph_count
        )
        return dynamic_size

    def _summarise_chunk(self, chunk):
        """调用模型或回退策略对单个分组进行摘要。"""
        parse_messages = copy.deepcopy(GROUP_SUMMARY_MESSAGES)
        user_template = Template(parse_messages[1]['content'])
        parse_messages[1]['content'] = user_template.substitute(paragraphs=self._serialize_paragraphs(chunk))

        try:
            response = self.llm.chat(parse_messages)
            if isinstance(response, dict) and 'summary' in response:
                summary_text = response['summary']
            elif isinstance(response, str):
                summary_text = response
            else:
                raise ValueError('Unexpected response format when summarising chunk')
            return summary_text
        except Exception as exc:
            logger.warning('Chunk summarisation failed, falling back to concatenation: %s', exc)
            return ' '.join(item.get('summary', '') for item in chunk)

    def parse(self, **kwargs):
        """执行文档解析主流程并填充最终文档对象。"""
        path = kwargs.get('path')
        compression_config = kwargs.get('compression_config')
        if compression_config:
            self._configure_compression(compression_config)

        paragraphs = self.tidy_up_data(kwargs.get('paragraphs'))
        parse_messages = copy.deepcopy(DOCUMENT_PARSE_MESSAGES)
        content = Template(parse_messages[1]['content'])
        parse_messages[1]['content'] = content.substitute(paragraphs=paragraphs, path=path)
        self.document = self.llm.chat(parse_messages)
        self.document['kb_id'] = self.kb_id
        self.document['parse_strategy'] = kwargs.get('parse_strategy')
        self.document['meta_data']['最后更新时间'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.document = Document(**self.document)
        return self.document

    def storage_parser_data(self, parent: Category):
        self.document.categories.append(parent)
        self.session.add(self.document)

    def rebuild_parser_data(self, parent: Category):
        import uuid
        if not isinstance(parent.category_id, uuid.UUID):
            try:
                parent.category_id = uuid.UUID(str(parent.category_id))
            except ValueError:
                raise ValueError(f"异常category_id: {parent.category_id}")
        # 解绑旧类别
        self.document.categories = []
        self.document.categories.append(parent)
        self.session.add(self.document)
