"""
Pinecone 벡터 DB 클라이언트 모듈
벡터 DB 생성, 저장, 검색 기능 제공 (Permanent Free Tier)
"""
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from typing import List
from utils.embedder import get_embeddings
from utils.config import settings
from utils.logger import logger

# Pinecone 클라이언트 초기화
pc = Pinecone(api_key=settings.pinecone_api_key)

def get_vectorstore():
    """
    기존 Pinecone 벡터스토어 로드
    
    Returns:
        PineconeVectorStore 객체
    """
    embeddings = get_embeddings()
    
    # Pinecone Index 연결
    vectorstore = PineconeVectorStore(
        index_name=settings.pinecone_index_name,
        embedding=embeddings,
        pinecone_api_key=settings.pinecone_api_key
    )
    
    logger.info(f"Pinecone 벡터스토어 로드 완료: {settings.pinecone_index_name}")
    return vectorstore

def create_vectorstore(documents: List[Document]):
    """
    새로운 Pinecone 벡터스토어 생성 및 문서 업로드
    
    Args:
        documents: Document 리스트
    
    Returns:
        PineconeVectorStore 객체
    """
    logger.info(f"Pinecone 벡터스토어 생성 시작: {len(documents)}개 문서")
    
    # Index 존재 여부 확인
    index_name = settings.pinecone_index_name
    
    if index_name not in pc.list_indexes().names():
        logger.info(f"Index '{index_name}' 생성 중...")
        pc.create_index(
            name=index_name,
            dimension=1536,  # OpenAI text-embedding-ada-002/3-small
            metric="cosine",
            spec=ServerlessSpec(
                cloud='aws',
                region=settings.pinecone_environment
            )
        )
        logger.info(f"Index '{index_name}' 생성 완료")
    
    embeddings = get_embeddings()
    
    # 문서를 Pinecone에 업로드
    vectorstore = PineconeVectorStore.from_documents(
        documents=documents,
        embedding=embeddings,
        index_name=index_name,
        pinecone_api_key=settings.pinecone_api_key
    )
    
    logger.info(f"Pinecone 벡터스토어 생성 완료: {index_name}")
    return vectorstore

def get_index_stats():
    """
    Pinecone Index 통계 정보 조회
    
    Returns:
        dict: Index 통계 (벡터 개수, namespace 등)
    """
    index = pc.Index(settings.pinecone_index_name)
    stats = index.describe_index_stats()
    logger.info(f"Pinecone Index 통계: {stats}")
    return stats
