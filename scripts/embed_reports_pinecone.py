"""
증권사 리포트 PDF를 Pinecone에 임베딩하는 스크립트
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from utils.data_loader import load_pdfs_from_directory
from utils.text_splitter import get_text_splitter
from utils.db_client import create_vectorstore
from utils.logger import logger

def main():
    """메인 실행 함수"""
    # PDF 리포트 디렉토리
    reports_dir = "./data/reports"
    
    if not os.path.exists(reports_dir):
        logger.error(f"리포트 디렉토리를 찾을 수 없습니다: {reports_dir}")
        logger.info("디렉토리를 생성합니다...")
        os.makedirs(reports_dir, exist_ok=True)
        logger.info(f"{reports_dir}에 PDF 파일을 추가한 후 다시 실행하세요.")
        return
    
    # PDF 파일 로드
    logger.info(f"📂 PDF 파일 로드 중: {reports_dir}")
    documents = load_pdfs_from_directory(reports_dir)
    
    if not documents:
        logger.warning("로드된 PDF 파일이 없습니다.")
        logger.info(f"{reports_dir}에 PDF 파일을 추가한 후 다시 실행하세요.")
        return
    
    logger.info(f"✅ {len(documents

)}개 PDF 문서 로드 완료")
    
    # 텍스트 청킹
    logger.info("📝 텍스트 청킹 중...")
    text_splitter = get_text_splitter()
    chunks = text_splitter.split_documents(documents)
    logger.info(f"✅ {len(chunks)}개의 청크 생성 완료")
    
    # Pinecone에 임베딩 및 저장
    logger.info("🚀 Pinecone에 임베딩 및 업로드 중...")
    logger.info("⏳ OpenAI API를 사용하여 벡터 생성 중... (시간이 소요될 수 있습니다)")
    
    vectorstore = create_vectorstore(chunks)
    
    logger.info("✅ Pinecone 임베딩 완료!")
    logger.info(f"📊 총 {len(chunks)}개의 벡터가 Pinecone에 저장되었습니다.")
    
    # Index 통계 확인
    from utils.db_client import get_index_stats
    stats = get_index_stats()
    logger.info(f"📈 Pinecone Index 통계:")
    logger.info(f"   - Total vectors: {stats.get('total_vector_count', 0)}")
    logger.info(f"   - Dimensions: {stats.get('dimension', 0)}")
    
    logger.info("🎉 모든 작업이 완료되었습니다!")

if __name__ == "__main__":
    main()
