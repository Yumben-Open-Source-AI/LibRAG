"""
@Project ：LibRAG
@File    ：views.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/4/24 上午11:48 
"""
import datetime
import os.path
from typing import List, Dict

from sqlmodel import Session

from llm.llmchat import LlmChat
from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from parser.paragraph_parser import ParagraphParser
from tools.log_tools import parser_logger as logger


def loading_data(
        files_info: List[Dict],
        engine
):
    with Session(engine) as session:
        try:
            for info in files_info:
                kb_id = info['kb_id']
                file_path = info['file_path']
                policy_type = info['policy_type']
                file_name = os.path.basename(file_path)
                start_time = datetime.datetime.now()
                logger.info(f'开始处理文件:{file_name}')
                llm = LlmChat()

                # 解析文档内部段落
                par_parser = ParagraphParser(llm, kb_id, session)
                paragraph_params = {
                    'path': file_path,
                    'parse_strategy': policy_type
                }
                all_paragraphs = par_parser.parse(**paragraph_params)
                logger.info(f'文件:{file_name} 段落解析:{all_paragraphs}')

                # 解析文档信息
                doc_parser = DocumentParser(llm, kb_id, session)
                document_params = {
                    'path': file_path,
                    'parse_strategy': policy_type,
                    'paragraphs': all_paragraphs
                }
                document = doc_parser.parse(**document_params)
                logger.info(f'文件:{file_name} 文档解析:{document}')

                # 解析文档所属分类
                category_parser = CategoryParser(llm, kb_id, session)
                category_params = {'document': document}
                category = category_parser.parse(**category_params)
                logger.info(f'文件:{file_name} 类别解析:{category}')

                # 解析文档所属领域
                domain_parser = DomainParser(llm, kb_id, session)
                domain_params = {'category': category}
                domain = domain_parser.parse(**domain_params)
                logger.info(f'文件:{file_name} 领域解析:{domain}')

                # 回填及存储数据
                par_parser.storage_parser_data(document)
                doc_parser.storage_parser_data(category)
                category_parser.storage_parser_data(domain)
                domain_parser.storage_parser_data(None)
                session.commit()
                logger.info(f'文件:{file_name} 处理完毕 耗时:{datetime.datetime.now() - start_time}')
        except Exception as e:
            session.rollback()
            logger.info(e)
