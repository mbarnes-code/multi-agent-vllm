#
#
from pydantic import BaseModel
from typing import Optional, List

class ChatConfig(BaseModel):
    sources: List[str]
    models :  List[str]
    selected_model: Optional[str] = None
    selected_sources: Optional[List[str]] = None
    current_chat_id: Optional[str] = None

class ChatIdRequest(BaseModel):
    chat_id: str

class ChatRenameRequest(BaseModel):
    chat_id: str
    new_name: str

class SelectedModelRequest(BaseModel):
    model: str      
