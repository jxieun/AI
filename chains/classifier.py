"""
질문 분류 체인
사용자 질문을 4가지 카테고리로 자동 분류 + 종목 코드 추출
"""
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.config import settings
from utils.logger import logger
from utils.spring_client import spring_client
import re
import asyncio
import openai # 직접 예외 처리를 위해 추가

async def classify_question(question: str) -> dict:
    """
    사용자 질문을 카테고리로 분류하고 필요 시 종목 코드 추출
    
    Args:
        question: 사용자 질문
    
    Returns:
        {"category": str, "stock_code": str (optional)}
    """
    logger.info(f"질문 분류 시작: {question}")
    
    # LLM 초기화 (temperature=0으로 일관된 분류)
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.0,
        openai_api_key=settings.openai_api_key
    )
    
    # ★ 분류 프롬프트: 카테고리 + 종목명 추출
    prompt = PromptTemplate(
        input_variables=["question"],
        template="""
당신은 투자 질문을 분류하는 전문가입니다.
사용자 질문을 아래 4가지 카테고리 중 **정확히 하나**로 분류하세요.

카테고리:
1. economic_indicator - 기준금리, M2, 환율, GDP, 시장 상황, 경제 전망 등 **거시경제** 관련
2. stock_price - **특정 기업명이 명시된** 주가, 시가총액, 거래량, 재무제표 질문
3. analyst_report - **특정 기업명이 명시된** 증권사 리포트, 애널리스트 의견, 목표주가 질문
4. general - 투자 전략, 포트폴리오 조언, 투자 용어 설명 등 **일반적인 투자 상담**

**중요한 판단 기준:**
- "시장 상황", "시장 전망", "경제 상황" 같은 거시적 질문 → economic_indicator
- 구체적인 기업명(삼성전자, 네이버 등)이 있는 질문 → stock_price 또는 analyst_report
- 기업명 없이 "투자 방법", "전략" 등을 묻는 질문 → general

질문: {question}

답변 형식: 
category: 카테고리명
stock: 종목명 (stock_price 또는 analyst_report인 경우만, 없으면 none)

예시:
질문: "삼성전자 주가가 얼마야?"
답변: 
category: stock_price
stock: 삼성전자

질문: "기준금리가 주식에 미치는 영향은?"
답변:
category: economic_indicator
stock: none

질문: "현재 시장 상황은 어때?"
답변:
category: economic_indicator
stock: none

질문: "초보자 투자 전략 알려줘"
답변:
category: general
stock: none

답변:
"""
    )
    
    # 체인 구성
    chain = prompt | llm | StrOutputParser()
    
    # 실행
    try:
        result = chain.invoke({"question": question}).strip()
    except Exception as e:
        logger.error(f"분류 LLM 호출 실패 (RateLimit 등): {e}")
        logger.info("⚠️ Fallback: 규칙 기반(Rule-based) 분류기 작동")
        return await rule_based_classification(question)
    
    # ★ 결과 파싱
    category_match = re.search(r'category:\s*(\w+)', result)
    stock_match = re.search(r'stock:\s*(.+)', result)
    
    category = category_match.group(1) if category_match else "general"
    stock_name = stock_match.group(1).strip() if stock_match else "none"
    
    # ★ 종목명 → 종목 코드 변환 (Spring Boot DB 조회)
    stock_code = None
    if stock_name != "none":
        stock_code = await get_stock_code(stock_name)
    
    result_dict = {
        "category": category,
        "stock_code": stock_code
    }
    
    logger.info(f"분류 결과: {result_dict}")
    return result_dict

async def get_stock_code(stock_name: str) -> str:
    """
    종목명 → 종목 코드 변환 (Spring Boot DB 조회)
    
    Args:
        stock_name: 종목명
    
    Returns:
        종목 코드 (6자리) 또는 None
    """
    # ★ Spring Boot의 Stock 테이블 조회
    stock_code = await spring_client.get_stock_code_from_name(stock_name)
    
    if stock_code:
        return stock_code
    
    # ★ Fallback: 주요 종목 하드코딩 (DB 조회 실패 시)
    stock_map = {
        "삼성전자": "005930",
        "네이버": "035420",
        "현대차": "005380",
        "SK하이닉스": "000660",
        "카카오": "035720",
        "LG에너지솔루션": "373220",
        "삼성바이오로직스": "207940",
        "POSCO홀딩스": "005490"
    }
    
    return stock_map.get(stock_name, None)

async def rule_based_classification(question: str) -> dict:
    """
    LLM 사용 불가 시(429 에러 등) 규칙 기반 분류
    """
    q = question.replace(" ", "")
    
    # 1. 종목명 추출 (간단한 매핑)
    stock_map = {
        "삼성전자": "005930", "삼전": "005930",
        "네이버": "035420", "NAVER": "035420",
        "카카오": "035720",
        "현대차": "005380",
        "하이닉스": "000660", "SK하이닉스": "000660",
        "LG엔솔": "373220", "LG에너지솔루션": "373220",
        "포스코": "005490", "POSCO홀딩스": "005490", 
        "삼성바이오": "207940", "로직스": "207940"
    }
    
    stock_code = None
    extracted_name = "none"
    for name, code in stock_map.items():
        if name in q:
            stock_code = code
            extracted_name = name
            break
            
    # 2. 카테고리 분류
    if stock_code:
        if "리포트" in q or "목표가" in q or "의견" in q:
            category = "analyst_report"
        else:
            category = "stock_price"
    elif "환율" in q or "금리" in q or "경제" in q or "시장" in q:
        category = "economic_indicator"
    else:
        # 종목은 없지만 '추천'이나 '전망' 단어가 있으면 general, 아니면 general
        category = "general"
        
    logger.info(f"규칙 기반 분류 결과: category={category}, stock={extracted_name}")
    
    return {
        "category": category,
        "stock_code": stock_code
    }