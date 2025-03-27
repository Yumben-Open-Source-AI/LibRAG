import os

from fastapi import APIRouter

from llm.qwen import Qwen
from selector.document_selector import DocumentSelector
from selector.paragraph_selector import ParagraphSelector

router = APIRouter(tags=['ai'], prefix='/ai')


@router.get('/query')
async def query_with_llm(question: str):
    os.environ['OPENAI_API_KEY'] = 'sk-3fb76d31383b4552b9c3ebf82f44157d'
    os.environ['OPENAI_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

    qwen = Qwen()
    document_selector = DocumentSelector(qwen)
    selected_documents = document_selector.collate_select_params().start_select(question)
    paragraph_selector = ParagraphSelector(qwen)
    target_paragraphs = paragraph_selector.collate_select_params(selected_documents).start_select(question).collate_select_result()
    return target_paragraphs
