from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from utils.logger import logger
from pykrx import stock
import pandas as pd
import time
import asyncio
from pydantic import BaseModel
from typing import List

router = APIRouter(
    prefix="/api",       
    tags=["Market Data"] 
)

# --- 캐시 및 헬퍼 함수 ---
cached_data = {}
CACHE_DURATION_SECONDS = 60

def get_latest_trading_day_str():
    """가장 최근 거래일을 YYYYMMDD 문자열로 반환"""
    today = datetime.now()
    if today.weekday() >= 5:
        today -= timedelta(days=today.weekday() - 4)
    
    # 최대 10일 전까지 거래일 찾기
    for _ in range(10):
        try:
            date_str = today.strftime("%Y%m%d")
            df = stock.get_market_ohlcv(date_str, market="KOSPI")
            if not df.empty:
                return date_str
            today -= timedelta(days=1)
        except Exception:
            today -= timedelta(days=1)
    
    # Fallback: 오늘 날짜 반환
    return datetime.now().strftime("%Y%m%d")

def safe_get_ohlcv(date_str, ticker=None, market="ALL"):
    """
    pykrx OHLCV 안전 조회 (컬럼명 에러 처리)
    """
    try:
        if ticker:
            df = stock.get_market_ohlcv(date_str, date_str, ticker)
        else:
            df = stock.get_market_ohlcv(date_str, market=market)
        
        # ★ 컬럼명 정규화 (pykrx 버전별 차이 대응)
        if not df.empty:
            df.columns = df.columns.str.strip()  # 공백 제거
        
        return df
    except Exception as e:
        logger.error(f"OHLCV 조회 실패 (date={date_str}, ticker={ticker}): {e}")
        return pd.DataFrame()

def safe_get_market_cap(date_str, market="ALL"):
    """시가총액 안전 조회"""
    try:
        df = stock.get_market_cap(date_str, market=market)
        if not df.empty:
            df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        logger.error(f"시가총액 조회 실패: {e}")
        return pd.DataFrame()

# --- 통합 대시보드 API ---
@router.get("/dashboard")
async def get_dashboard_data():
    """대시보드에 필요한 모든 데이터를 한 번에 조회하여 반환"""
    global cached_data
    current_time = time.time()

    if 'dashboard' in cached_data and current_time - cached_data['dashboard']['timestamp'] < CACHE_DURATION_SECONDS:
        logger.info("✅ 캐시된 대시보드 데이터 반환")
        return cached_data['dashboard']['data']

    try:
        logger.info("🔄 새로운 대시보드 데이터 요청")
        latest_day = get_latest_trading_day_str()
        df_ohlcv = stock.get_market_ohlcv(latest_day, market="ALL")
        
        logger.info(f"✅ OHLCV 데이터 {len(df_ohlcv)}개 로드")

        # ★ 지수 데이터 (KOSPI, KOSDAQ)
        indices_data = {}
        today_str = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=21)).strftime('%Y%m%d')
        
        for index_name, index_code in [("kospi", "1001"), ("kosdaq", "2001")]:
            try:
                logger.info(f"{index_name} 지수 조회 시작: {start_date} ~ {today_str}")
                
                df_daily = stock.get_index_ohlcv(start_date, today_str, index_code, "d")
                
                if df_daily.empty or len(df_daily) < 2:
                    raise ValueError(f"{index_name} 일봉 데이터가 부족: {len(df_daily)}개")
                
                chart_data = [{'value': float(row['종가'])} for idx, row in df_daily.tail(7).iterrows()]
                
                latest_row = df_daily.iloc[-1]
                previous_row = df_daily.iloc[-2]
                latest_close = float(latest_row['종가'])
                previous_close = float(previous_row['종가'])
                
                latest_info = {
                    "value": round(latest_close, 2),
                    "changeValue": round(latest_close - previous_close, 2),
                    "changeRate": round((latest_close / previous_close - 1) * 100, 2)
                }
                
                logger.info(f"{index_name} 최종 데이터: 차트 개수 {len(chart_data)}")
                
            except Exception as e:
                logger.error(f"{index_name} 지수 데이터 처리 중 오류: {e}")
                try:
                    old_start = "20241001"
                    logger.info(f"{index_name} Fallback 시도: {old_start} ~ {today_str}")
                    df_fallback = stock.get_index_ohlcv(old_start, today_str, index_code, "d")
                    
                    if df_fallback.empty or len(df_fallback) < 2:
                        raise ValueError("Fallback 데이터도 부족")
                    
                    chart_data = [{'value': float(row['종가'])} for idx, row in df_fallback.tail(7).iterrows()]
                    
                    latest_row = df_fallback.iloc[-1]
                    previous_row = df_fallback.iloc[-2]
                    
                    latest_info = {
                        "value": round(float(latest_row['종가']), 2),
                        "changeValue": round(float(latest_row['종가'] - previous_row['종가']), 2),
                        "changeRate": round(float((latest_row['종가'] / previous_row['종가'] - 1) * 100), 2)
                    }
                    
                    logger.info(f"{index_name} Fallback 성공: 차트 개수 {len(chart_data)}")
                    
                except Exception as fallback_error:
                    logger.error(f"{index_name} Fallback 실패: {fallback_error}")
                    chart_data = []
                    latest_info = {"value": 0, "changeValue": 0, "changeRate": 0}
            
            indices_data[index_name] = {**latest_info, "chartData": chart_data}

        # 상승률 상위 5개
        top_gainers = df_ohlcv.sort_values(by='등락률', ascending=False).head(5)
        top_gainers_data = [{"code": ticker, "name": stock.get_market_ticker_name(ticker), "price": row['종가'], "change_rate": round(row['등락률'], 2)} for ticker, row in top_gainers.iterrows()]

        # 하락률 상위 5개
        top_losers = df_ohlcv.sort_values(by='등락률', ascending=True).head(5)
        top_losers_data = [{"code": ticker, "name": stock.get_market_ticker_name(ticker), "price": row['종가'], "change_rate": round(row['등락률'], 2)} for ticker, row in top_losers.iterrows()]

        # 거래량 상위 5개
        top_volume = df_ohlcv.sort_values(by='거래량', ascending=False).head(5)
        top_volume_data = [{"code": ticker, "name": stock.get_market_ticker_name(ticker), "volume": row['거래량']} for ticker, row in top_volume.iterrows()]

        # 시가총액 상위 10개
        df_cap = stock.get_market_cap(latest_day, market="ALL")
        top_10_tickers = df_cap.sort_values(by='시가총액', ascending=False).head(10).index.tolist()
        
        top_market_cap_data = [
            {
                "code": ticker,
                "name": stock.get_market_ticker_name(ticker),
                "price": df_ohlcv.loc[ticker]['종가'],
                "change_rate": round(df_ohlcv.loc[ticker]['등락률'], 2)
            }
            for ticker in top_10_tickers if ticker in df_ohlcv.index
        ]

        dashboard_data = {
            "indices": indices_data,
            "topGainers": top_gainers_data,
            "topLosers": top_losers_data,
            "topVolume": top_volume_data,
            "topMarketCap": top_market_cap_data,
        }

        cached_data['dashboard'] = {"data": dashboard_data, "timestamp": current_time}
        return dashboard_data
        
    except Exception as e:
        logger.error(f"대시보드 데이터 조회 중 오류 (Real Data 실패): {e}")
        logger.info("⚠️ Fallback: 목업(Mock) 데이터 반환. (Render IP 차단 가능성)")
        
        # 목업 데이터 반환
        return {
            "indices": {
                "kospi": {"value": 2650.12, "changeValue": 12.34, "changeRate": 0.47, "chartData": [{"value": 2600}, {"value": 2610}, {"value": 2620}, {"value": 2630}, {"value": 2640}, {"value": 2645}, {"value": 2650.12}]},
                "kosdaq": {"value": 850.55, "changeValue": -5.12, "changeRate": -0.60, "chartData": [{"value": 860}, {"value": 858}, {"value": 855}, {"value": 852}, {"value": 850}, {"value": 848}, {"value": 850.55}]}
            },
            "topGainers": [
                {"code": "005930", "name": "삼성전자(예시)", "price": 75000, "change_rate": 2.5},
                {"code": "000660", "name": "SK하이닉스(예시)", "price": 142000, "change_rate": 1.8},
                {"code": "035420", "name": "NAVER(예시)", "price": 210000, "change_rate": 1.2},
                {"code": "035720", "name": "카카오(예시)", "price": 54000, "change_rate": 0.9},
                {"code": "005380", "name": "현대차(예시)", "price": 240000, "change_rate": 0.5}
            ],
            "topLosers": [
                {"code": "051910", "name": "LG화학(예시)", "price": 450000, "change_rate": -1.5},
                {"code": "006400", "name": "삼성SDI(예시)", "price": 380000, "change_rate": -1.2},
                {"code": "066570", "name": "LG전자(예시)", "price": 98000, "change_rate": -0.8},
                {"code": "000270", "name": "기아(예시)", "price": 82000, "change_rate": -0.5},
                {"code": "010130", "name": "고려아연(예시)", "price": 480000, "change_rate": -0.3}
            ],
            "topVolume": [
                {"code": "005930", "name": "삼성전자(예시)", "volume": 12000000},
                {"code": "000660", "name": "SK하이닉스(예시)", "volume": 5000000},
                {"code": "042700", "name": "한미반도체(예시)", "volume": 3000000},
                {"code": "001570", "name": "금양(예시)", "volume": 2500000},
                {"code": "005935", "name": "삼성전자우(예시)", "volume": 2000000}
            ],
            "topMarketCap": [
                 {"code": "005930", "name": "삼성전자(예시)", "price": 75000, "change_rate": 2.5},
                 {"code": "000660", "name": "SK하이닉스(예시)", "price": 142000, "change_rate": 1.8},
                 {"code": "373220", "name": "LG에너지솔루션(예시)", "price": 390000, "change_rate": -0.5},
                 {"code": "207940", "name": "삼성바이오로직스(예시)", "price": 810000, "change_rate": 0.2},
                 {"code": "005380", "name": "현대차(예시)", "price": 240000, "change_rate": 0.5},
                 {"code": "000270", "name": "기아(예시)", "price": 82000, "change_rate": -0.5},
                 {"code": "068270", "name": "셀트리온(예시)", "price": 180000, "change_rate": 1.1},
                 {"code": "005490", "name": "POSCO홀딩스(예시)", "price": 440000, "change_rate": 0.8},
                 {"code": "035420", "name": "NAVER(예시)", "price": 210000, "change_rate": 1.2},
                 {"code": "003550", "name": "LG(예시)", "price": 95000, "change_rate": -0.1}
            ]
        }

async def fetch_top_gainers_data():
    """상승률 상위 5개 종목 조회 내부 함수"""
    latest_day = get_latest_trading_day_str()
    df = stock.get_market_ohlcv(latest_day, market="ALL")
    top_5 = df.sort_values(by='등락률', ascending=False).head(5)
    return [{"code": ticker, "name": stock.get_market_ticker_name(ticker), "price": row['종가'], "change_rate": round(row['등락률'], 2)} for ticker, row in top_5.iterrows()]

async def fetch_top_losers_data():
    """하락률 상위 5개 종목 조회 내부 함수"""
    latest_day = get_latest_trading_day_str()
    df = stock.get_market_ohlcv(latest_day, market="ALL")
    top_5 = df.sort_values(by='등락률', ascending=True).head(5)
    return [{"code": ticker, "name": stock.get_market_ticker_name(ticker), "price": row['종가'], "change_rate": round(row['등락률'], 2)} for ticker, row in top_5.iterrows()]

async def fetch_top_volume_data():
    """거래량 상위 5개 종목 조회 내부 함수"""
    latest_day = get_latest_trading_day_str()
    df = stock.get_market_ohlcv(latest_day, market="ALL")
    top_5 = df.sort_values(by='거래량', ascending=False).head(5)
    return [{"code": ticker, "name": stock.get_market_ticker_name(ticker), "volume": row['거래량']} for ticker, row in top_5.iterrows()]

async def fetch_top_market_cap_data():
    """시가총액 상위 10개 종목 조회 내부 함수 (가장 안정적인 방식)"""
    latest_day = get_latest_trading_day_str()
    
    # 1. 시가총액 보고서로 상위 10개 종목의 '코드'만 가져옵니다.
    df_cap = stock.get_market_cap(latest_day, market="ALL")
    top_10_tickers = df_cap.sort_values(by='시가총액', ascending=False).head(10).index.tolist()
    
    # 2. 전체 시장의 '가격 보고서'를 가져옵니다.
    df_ohlcv = stock.get_market_ohlcv(latest_day, market="ALL")
    
    result = []
    # 3. 상위 10개 코드에 해당하는 가격 정보만 '가격 보고서'에서 찾아와 조합합니다.
    for ticker in top_10_tickers:
        if ticker in df_ohlcv.index:
            row = df_ohlcv.loc[ticker]
            result.append({
                "code": ticker,
                "name": stock.get_market_ticker_name(ticker),
                "price": row['종가'],
                "change_rate": round(row['등락률'], 2)
            })
    return result

class TickersRequest(BaseModel):
    tickers: List[str]

@router.post("/stock-details")
async def get_stock_details(request: TickersRequest):
    """
    요청받은 종목 코드(티커) 리스트에 대한
    최신 시세 정보(종목명, 현재가, 등락률)를 반환합니다.
    """
    try:
        # 요청된 티커가 없으면 빈 리스트 반환
        if not request.tickers:
            return []
            
        latest_day = get_latest_trading_day_str()
        
        # 전체 시장의 최신 시세 정보를 한 번만 가져옵니다.
        df = stock.get_market_ohlcv(latest_day, market="ALL")
        
        # 요청받은 티커에 해당하는 데이터만 필터링합니다.
        filtered_df = df[df.index.isin(request.tickers)]
        
        result = []
        for ticker in request.tickers:
            if ticker in filtered_df.index:
                row = filtered_df.loc[ticker]
                result.append({
                    "id": ticker,
                    "name": stock.get_market_ticker_name(ticker),
                    "price": row['종가'],
                    "changePct": round(row['등락률'], 2)
                })
        return result

    except Exception as e:
        logger.error(f"개별 종목 상세 정보 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail="개별 종목 정보를 가져오는 중 오류가 발생했습니다.")

@router.get("/stock/{ticker}")
async def get_stock_detail(ticker: str):
    """특정 종목의 최신 시세 정보"""
    try:
        latest_day = get_latest_trading_day_str()
        df = safe_get_ohlcv(latest_day, ticker=ticker)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="해당 종목의 데이터를 찾을 수 없습니다.")
        
        latest_data = df.iloc[0]
        
        return {
            "name": stock.get_market_ticker_name(ticker),
            "ticker": ticker,
            "price": int(latest_data["종가"]),
            "changePct": round(latest_data["등락률"], 2),
            "ohlc": {
                "open": int(latest_data["시가"]),
                "high": int(latest_data["고가"]),
                "low": int(latest_data["저가"]),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"종목 상세 조회 실패 ({ticker}): {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stock/{ticker}/chart")
async def get_stock_chart(ticker: str):
    """특정 종목의 최근 1주일간의 종가 데이터를 차트용으로 반환합니다."""
    try:
        start_date = (datetime.now() - timedelta(days=14)).strftime('%Y%m%d')
        today = datetime.now().strftime('%Y%m%d')
        
        df = stock.get_market_ohlcv(start_date, today, ticker)
        
        chart_data = df['종가'].tolist()
        
        return {"chart": chart_data}
    except Exception as e:
        logger.error(f"종목 차트({ticker}) 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))