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
        while len(self._serialize_paragraphs(grouped)) > self.max_paragraph_payload and len(grouped) > 1:
            grouped = self._summarise_groups(grouped)

        return grouped

    def _summarise_groups(self, paragraphs):
        """将段落按分组进行压缩，输出更短的摘要列表。"""
        compressed = []
        step = self._determine_group_size(len(paragraphs))
        for start in range(0, len(paragraphs), step):
            chunk = paragraphs[start:start + step]
            summary_text = self._summarise_chunk(chunk)
            compressed.append({'summary': summary_text})
        return compressed

    def _determine_group_size(self, paragraph_count: int) -> int:
        """计算当前批次段落应使用的分组大小。"""
        configured_size = self.group_size
        if configured_size and configured_size > 1:
            return configured_size

        # Automatic mode: compress more aggressively for large paragraph sets.
        if paragraph_count <= 0:
            return 1

        if paragraph_count <= self.MIN_AUTOMATIC_GROUP_SIZE:
            return max(1, paragraph_count)

        dynamic_size = max(
            self.MIN_AUTOMATIC_GROUP_SIZE,
            int(math.ceil(math.sqrt(paragraph_count)))
        )
        logger.debug(
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
