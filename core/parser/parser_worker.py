"""
@Project ：core 
@File    ：parser_worker.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/6/4 下午6:25 
"""
import datetime
import os.path
import time
from multiprocessing import Process

from sqlmodel import select

from db.database import get_session
from llm.llmchat import LlmChat
from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from parser.paragraph_parser import ParagraphParser
from tools.log_tools import parser_logger as logger
from web_server.ai.models import KnowledgeBase, ProcessingTask


def worker_loop(kb_id):
    """ 预处理主进程 """
    while True:
        session = next(get_session())
        pending_task = session.query(ProcessingTask).filter(ProcessingTask.kb_id == kb_id,
                                                            ProcessingTask.status == 'pending').first()

        if pending_task:
            try:
                kb_id = pending_task.kb_id
                file_path = pending_task.file_path
                policy_type = pending_task.parse_strategy
                file_name = os.path.basename(file_path)
                start_time = datetime.datetime.now()
                pending_task.status = 'processing'
                pending_task.started_at = datetime.datetime.now()
                session.add(pending_task)
                session.commit()
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
                pending_task.status = 'succeed'
                pending_task.started_at = datetime.datetime.now()
                session.add(pending_task)
                session.commit()
                logger.info(f'文件:{file_name} 处理完毕 耗时:{datetime.datetime.now() - start_time}')
            except Exception as e:
                pending_task.status = 'failed'
                session.add(pending_task)
                session.rollback()
                logger.error(f'task {pending_task} error: {e} sleep 10s', exc_info=True)
                time.sleep(10)
        else:
            logger.debug(f'知识库{kb_id} 暂无排队任务sleep 10s')
            # 当前知识库没有排队任务
            time.sleep(10)


def init_process():
    session = next(get_session())

    knowledge_bases = session.exec(select(KnowledgeBase)).all()
    # 每个知识库单开进程进行预处理
    for knowledge_base in knowledge_bases:
        create_new_process(knowledge_base.kb_id)


def create_new_process(kb_id):
    worker = Process(target=worker_loop, args=(kb_id,))
    worker.daemon = True
    worker.start()
