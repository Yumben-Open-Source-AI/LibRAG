"""
@Project ：start-map 
@File    ：models.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/4/25 上午10:21 
"""
import uuid
from sqlmodel import Field, SQLModel, JSON, Relationship
from sqlalchemy import Column, TEXT


class KbBase(SQLModel):
    """ knowledge_base base model """
    kb_name: str = Field(default='')
    kb_description: str | None = Field(default='')
    keywords: str | None = Field(default='')


class KnowledgeBase(KbBase, table=True):
    """ knowledge_base model """
    __tablename__ = "knowledge_base"

    kb_id: int | None = Field(default=None, primary_key=True)

    paragraphs: list['Paragraph'] = Relationship(back_populates='know_base')
    documents: list['Document'] = Relationship(back_populates='know_base')


class Category(SQLModel, table=True):
    __tablename__ = 'category'

    category_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    category_name: str = Field(default='', sa_column_kwargs={'comment': '分类名称'})
    category_description: str = Field(default='', sa_column_kwargs={'comment': '分类描述'})
    meta_data: dict = Field(sa_type=JSON, default={}, sa_column_kwargs={'comment': '元数据'})
    parent_description: str
    documents: list['Document'] = Relationship(back_populates='document')
    kb_id: int | None = Field(default=None, foreign_key='knowledge_base.kb_id',
                              sa_column_kwargs={'comment': '知识库id'})
    know_base: KnowledgeBase = Relationship(back_populates='documents')


class Document(SQLModel, table=True):
    __tablename__ = 'document'

    document_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_name: str = Field(default='', sa_column_kwargs={'comment': '文档名称'})
    document_description: str = Field(default='', sa_column_kwargs={'comment': '文档描述'})
    file_path: str = Field(default='', sa_column_kwargs={'comment': '文档路径'})
    meta_data: dict = Field(sa_type=JSON, default={}, sa_column_kwargs={'comment': '元数据'})
    parent_description: str
    parent_id: uuid.UUID | None = Field(foreign_key='document.document_id')
    paragraphs: list['Paragraph'] = Relationship(back_populates='document')
    kb_id: int | None = Field(default=None, foreign_key='knowledge_base.kb_id',
                              sa_column_kwargs={'comment': '知识库id'})
    know_base: KnowledgeBase = Relationship(back_populates='documents')


class Paragraph(SQLModel, table=True):
    __tablename__ = 'paragraph'

    paragraph_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    paragraph_name: str = Field(default='', sa_column_kwargs={'comment': '段落名称'})
    summary: str = Field(default='', sa_column_kwargs={'comment': '段落摘要'})
    content: str = Field(sa_column=Column(TEXT))
    position: str = Field(default='', sa_column_kwargs={'comment': '段落页数位置'})
    parse_strategy: str = Field(default='', sa_column_kwargs={'comment': '提取原文相关信息'})
    meta_data: dict = Field(sa_type=JSON, default={}, sa_column_kwargs={'comment': '元数据'})
    keywords: list[str] = Field(sa_type=JSON, default=[], sa_column_kwargs={'comment': '提取关键词'})
    parent_description: str
    parent_id: uuid.UUID | None = Field(foreign_key='document.document_id')
    document: Document = Relationship(back_populates='paragraphs')
    kb_id: int | None = Field(default=None, foreign_key='knowledge_base.kb_id',
                              sa_column_kwargs={'comment': '知识库id'})
    know_base: KnowledgeBase = Relationship(back_populates='paragraphs')
