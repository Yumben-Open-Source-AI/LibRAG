from msilib.schema import File

from fastapi import UploadFile, Form
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class KbBase(SQLModel):
    kb_name: str = Field(default='')
    kb_description: str | None = Field(default='')
    keywords: str | None = Field(default='')


class KnowledgeBase(KbBase, table=True):
    __tablename__ = "knowledge_base"

    kb_id: int | None = Field(default=None, primary_key=True)


class FilePolicy(BaseModel):
    kb_id: int = Form()
    file: UploadFile = File
    policy_type: str = Form()

