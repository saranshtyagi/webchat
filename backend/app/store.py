from typing import Dict
from langchain_community.vectorstores import FAISS


session_store: Dict[str, FAISS] = {}