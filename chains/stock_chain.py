"""
주가 분석 체인 - pykrx API 데이터 조회 및 LLM 감성 분석
"""
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.config import settings
from utils.logger import logger
from pykrx import stock
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import yfinance as yf # Fallback data source

def get_latest_trading_day() -> datetime:
    """
    가장 최근 거래일을 반환 (주말/공휴일 제외)
    
    Returns:
        datetime 객체
    """
    today = datetime.now()
    
    # 주말이면 금요일로
    if today.weekday() >= 5:
        days_to_subtract = today.weekday() - 4
        today = today - timedelta(days=days_to_subtract)
    
    # 최대 7일 전까지 거래일 찾기
    for i in range(7):
        try:
            test_date = today - timedelta(days=i)
            date_str = test_date.strftime("%Y%m%d")
            
            df = stock.get_market_ohlcv(date_str, date_str, "005930")
            
            if not df.empty:
                logger.info(f"최근 거래일 발견: {date_str}")
                return test_date
        except Exception as e:
            logger.debug(f"날짜 {test_date.strftime('%Y%m%d')} 거래일 아님: {e}")
            continue
    
    logger.warning("최근 거래일을 찾지 못했습니다. 오늘 날짜 사용")
    return today

def get_stock_data_from_pykrx(stock_code: str) -> Dict[str, Any]:
    """
    pykrx에서 주가 데이터 조회 (타입 안정성 강화)
    
    Args:
        stock_code: 종목 코드 (예: "005930")
    
    Returns:
        주가 데이터 딕셔너리
        {
            "ticker": str,
            "name": str,
            "price": int,
            "change_pct": float,
            "volume": int,
            "open": int,
            "high": int,
            "low": int,
            "date": str
        }
    """
    try:
        logger.info(f"pykrx 주가 조회 시작: {stock_code}")
        
        latest_day = get_latest_trading_day()
        today_str = latest_day.strftime("%Y%m%d")
        
        logger.info(f"조회 날짜: {today_str}")
        
        df = stock.get_market_ohlcv(today_str, today_str, stock_code)
        
        if df.empty:
            logger.warning(f"주가 데이터 없음 (종목: {stock_code}, 날짜: {today_str})")
            
            week_ago = (latest_day - timedelta(days=7)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv(week_ago, today_str, stock_code)
            
            if df.empty:
                logger.error(f"1주일 데이터도 없음: {stock_code}")
                return {}
        
        latest = df.iloc[-1]
        
        try:
            stock_name = stock.get_market_ticker_name(stock_code)
        except Exception:
            stock_name = "Unknown"
        
        result: Dict[str, Any] = {
            "ticker": stock_code,
            "name": stock_name,
            "price": int(latest["종가"]),
            "change_pct": round(float(latest["등락률"]), 2),
            "volume": int(latest["거래량"]),
            "open": int(latest["시가"]),
            "high": int(latest["고가"]),
            "low": int(latest["저가"]),
            "date": today_str
        }
        
        logger.info(f"pykrx 주가 조회 성공: {stock_name} ({stock_code}) - {result['price']:,}원")
        return result
        
    except Exception as e:
        logger.error(f"pykrx 주가 조회 실패 ({stock_code}): {e}")
        logger.info(f"⚠️ Fallback: {stock_code}에 대해 yfinance 시도")
        return get_stock_data_from_yfinance(stock_code)

def get_stock_data_from_yfinance(stock_code: str) -> Dict[str, Any]:
    """yfinance를 통한 주가 조회 Fallback"""
    suffixes = [".KS", ".KQ"]
    
    for suffix in suffixes:
        try:
            yf_ticker = stock_code + suffix
            stock_obj = yf.Ticker(yf_ticker)
            # 2일치 데이터로 등락률 계산
            hist = stock_obj.history(period="5d")
            
            if len(hist) < 1:
                continue
                
            latest = hist.iloc[-1]
            price = int(latest["Close"])
            
            # 전일 대비 등락률 계산
            if len(hist) >= 2:
                prev = hist.iloc[-2]["Close"]
                change_pct = round(((price / prev) - 1) * 100, 2)
            else:
                change_pct = 0.0
                
            # 기본 정보
            info = stock_obj.fast_info
            
            return {
                "ticker": stock_code,
                "name": f"{stock_code} (Yahoo)", # 종목명 조회 어려움
                "price": price,
                "change_pct": change_pct,
                "volume": int(latest["Volume"]),
                "open": int(latest["Open"]),
                "high": int(latest["High"]),
                "low": int(latest["Low"]),
                "date": datetime.now().strftime("%Y%m%d") # 최신 데이터 가정
            }
        except Exception:
            continue
            
    return {}

def analyze_sentiment(stock_data: Dict[str, Any]) -> str:
    """
    주가 데이터 기반 감성 분석 (긍정/중립/부정)
    
    Args:
        stock_data: 주가 데이터
    
    Returns:
        "긍정", "중립", "부정" 중 하나
    """
    if not stock_data:
        return "중립"
    
    change_pct = stock_data.get("change_pct", 0)
    
    # 간단한 규칙 기반 감성 분석
    if change_pct >= 3.0:
        return "긍정"
    elif change_pct <= -3.0:
        return "부정"
    else:
        return "중립"

def query_stock_analysis(question: str, stock_code: str) -> str:
    """
    주가 데이터를 기반으로 질문에 답변 (감성 분석 포함)
    
    Args:
        question: 사용자 질문
        stock_code: 종목 코드
    
    Returns:
        답변 문자열
    """
    logger.info(f"주가 분석 질의: {question}, 종목: {stock_code}")
    
    # ★ 1. pykrx에서 주가 데이터 조회
    stock_data = get_stock_data_from_pykrx(stock_code)
    
    if not stock_data:
        return f"죄송합니다. 종목 코드 '{stock_code}'의 주가 데이터를 조회할 수 없습니다. 종목 코드를 확인해 주세요."
    
    # ★ 2. 감성 분석
    sentiment = analyze_sentiment(stock_data)
    
    # LLM 초기화
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.3,
        openai_api_key=settings.openai_api_key
    )
    
    # ★ 3. 감성 분석을 포함한 프롬프트
    prompt = PromptTemplate(
        input_variables=["question", "stock_data", "sentiment"],
        template="""
당신은 주식 애널리스트입니다.
아래 주가 데이터와 시장 감성 분석을 기반으로 질문에 답변하세요.

주가 데이터:
{stock_data}

시장 감성: {sentiment}

질문: {question}

답변 지침:
1. 현재 주가와 변동률을 명확히 설명하세요
2. 시장 감성({sentiment})을 반영하여 분석하세요
   - 긍정: 상승 모멘텀, 투자 심리 호전 강조
   - 부정: 하락 압력, 리스크 요인 강조
   - 중립: 균형잡힌 시각 제시
3. 거래량과 가격 범위를 고려한 시장 동향을 분석하세요
4. 투자 시 주의사항을 언급하세요
5. 구체적인 매수/매도 추천은 하지 마세요
6. 한국어로 자연스럽게 답변하세요

답변:
"""
    )
    
    # 체인 구성
    chain = prompt | llm | StrOutputParser()
    
    # ★ 4. 주가 데이터를 문자열로 변환
    stock_str = f"""
종목명: {stock_data['name']}
종목코드: {stock_data['ticker']}
현재가: {stock_data['price']:,}원
등락률: {stock_data['change_pct']}%
시가: {stock_data['open']:,}원
고가: {stock_data['high']:,}원
저가: {stock_data['low']:,}원
거래량: {stock_data['volume']:,}주
기준일: {stock_data['date']}
"""
    
    # 실행
    try:
        answer = chain.invoke({
            "question": question,
            "stock_data": stock_str,
            "sentiment": sentiment
        })
        
        # ★ 5. 답변에 감성 분석 결과 추가
        final_answer = f"[시장 감성: {sentiment}]\n\n{answer}"
        
        logger.info(f"주가 분석 답변 생성 완료 (감성: {sentiment})")
        return final_answer
        
    except Exception as e:
        logger.error(f"주가 분석 LLM 호출 실패: {e}", exc_info=True)
        return f"주가 데이터는 조회했으나 분석 중 오류가 발생했습니다: {str(e)}"