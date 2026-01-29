"""
일반 투자 상담 체인 - 직접 LLM 답변
"""
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.config import settings
from utils.logger import logger

def query_general_advice(question: str):
    """
    일반적인 투자 상담 질문에 답변
    
    Args:
        question: 사용자 질문
    
    Returns:
        답변 문자열
    """
    logger.info(f"일반 상담 질의: {question}")
    
    # LLM 초기화
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.5,  # 조금 더 창의적 답변
        openai_api_key=settings.openai_api_key
    )
    
    # 프롬프트 템플릿
    prompt = PromptTemplate(
        input_variables=["question"],
        template="""
당신은 친절한 투자 상담 전문가입니다.
초보 투자자가 이해할 수 있도록 쉽고 정확하게 답변하세요.

질문: {question}

답변 지침:
1. **질문의 핵심을 파악하세요:**
   - 투자 전략을 묻는다면 구체적인 방법론을 제시
   - 용어를 묻는다면 정의 + 실전 활용법을 함께 설명
   - 조언을 구한다면 실행 가능한 단계별 가이드 제공

2. 복잡한 용어는 쉽게 풀어서 설명하세요

3. 구체적인 예시를 들어주세요 (실제 투자 상황 기반)

4. 투자 위험에 대해서도 언급하세요

5. **단순히 개념만 설명하지 말고, "이렇게 활용하세요"라는 실용적 조언을 포함하세요**

6. 법적/재무적 조언이 아님을 명시하세요

답변:
"""
    )
    
    # 체인 구성
    chain = prompt | llm | StrOutputParser()
    
    # 실행
    try:
        answer = chain.invoke({"question": question})
        logger.info("일반 상담 답변 생성 완료")
        return answer
    except Exception as e:
        logger.error(f"일반 상담 LLM 호출 실패: {e}")
        return "죄송합니다. 현재 AI 서버 이용량이 많아(429 Error) 답변을 생성할 수 없습니다. 잠시 후 다시 시도해 주세요.\n\n(참고: 단순 주가 조회는 '삼성전자 주가'와 같이 종목명을 포함하여 질문하시면 조회 가능합니다.)"
