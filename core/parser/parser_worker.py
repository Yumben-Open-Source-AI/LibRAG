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
from concurrent.futures import ThreadPoolExecutor

from sqlmodel import select

from db.database import get_session
from llm.llmchat import LlmChat
from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from parser.paragraph_parser import ParagraphParser
from tools.log_tools import parser_logger as logger
from web_server.ai.models import KnowledgeBase, ProcessingTask


def worker_loop(pending_task_id):
    """ 预处理主进程 """
    session = next(get_session())

    pending_task = session.get(ProcessingTask, pending_task_id)
    if not pending_task:
        logger.error(f"任务ID {pending_task_id} 不存在")
        raise Exception(f'任务ID {pending_task_id} 不存在')

    try:
        kb_id = pending_task.kb_id
        file_path = pending_task.file_path
        policy_type = pending_task.parse_strategy
        file_name = os.path.basename(file_path)
        start_time = datetime.datetime.now()

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f'{file_path} 文件路径不存在，请检查')
        pending_task.status = 'processing'
        pending_task.progress = 0
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
        pending_task.progress = 1
        session.add(pending_task)
        session.commit()

        # 解析文档信息
        doc_parser = DocumentParser(llm, kb_id, session)
        document_params = {
            'path': file_path,
            'parse_strategy': policy_type,
            'paragraphs': all_paragraphs
        }
        document = doc_parser.parse(**document_params)
        logger.info(f'文件:{file_name} 文档解析:{document}')
        pending_task.progress = 2
        session.add(pending_task)
        session.commit()

        # 解析文档所属分类
        category_parser = CategoryParser(llm, kb_id, session)
        category_params = {'document': document}
        category = category_parser.parse(**category_params)
        logger.info(f'文件:{file_name} 类别解析:{category}')
        pending_task.progress = 3
        session.add(pending_task)
        session.commit()

        # 解析文档所属领域
        domain_parser = DomainParser(llm, kb_id, session)
        domain_params = {'category': category}
        domain = domain_parser.parse(**domain_params)
        logger.info(f'文件:{file_name} 领域解析:{domain}')
        pending_task.progress = 4
        session.add(pending_task)
        session.commit()

        # 回填及存储数据
        par_parser.storage_parser_data(document)
        doc_parser.storage_parser_data(category)
        category_parser.storage_parser_data(domain)
        domain_parser.storage_parser_data(None)
        pending_task.status = 'succeed'
        pending_task.completed_at = datetime.datetime.now()
        session.add(pending_task)
        session.commit()
        logger.info(f'文件:{file_name} 处理完毕 耗时:{datetime.datetime.now() - start_time}')
    except Exception as e:
        session.rollback()
        if pending_task:
            pending_task.status = 'failed'
            session.add(pending_task)
            session.commit()
        logger.error(f'task {pending_task_id} error: {e} sleep 10s', exc_info=True)
    finally:
        session.close()


def thread_call_back(task):
    exception = task.exception(120)
    if exception:
        logger.error(exception)


def init_process():
    while True:
        # 主线程单独创建管理会话
        session = next(get_session())
        try:
            knowledge_bases = session.exec(select(KnowledgeBase)).all()
            pending_tasks = []

            for knowledge_base in knowledge_bases:
                kb_id = knowledge_base.kb_id
                pending_task = session.query(ProcessingTask).filter(
                    ProcessingTask.kb_id == kb_id,
                    ProcessingTask.status == 'pending'
                ).first()
                if pending_task:
                    pending_tasks.append(pending_task.task_id)

            with ThreadPoolExecutor(8) as executor:
                for task_id in pending_tasks:
                    # 调整传递任务id, 不再共享会话
                    future = executor.submit(worker_loop, task_id)
                    future.add_done_callback(thread_call_back)
        except Exception as e:
            logger.error(f"查询任务时出错: {e}")
        finally:
            session.close()

        # 完成所有数据库检查休眠
        time.sleep(60)


def process_exit():
    """ 预处理退出前检查 """
    session = next(get_session())
    try:
        all_processing = session.query(ProcessingTask).filter_by(status='processing').all()
        for task in all_processing:
            task.status = 'pending'
            task.progress = 0
        session.add_all(all_processing)
        session.commit()
    except Exception as e:
        logger.error(f"退出处理时出错: {e}")
        session.rollback()
    finally:
        session.close()
