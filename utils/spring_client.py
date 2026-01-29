"""
Spring Boot 백엔드와 통신하는 클라이언트 모듈
경제지표 데이터를 Spring Boot의 MariaDB에서 가져옴
"""
import httpx
from typing import Dict, Optional
from utils.logger import logger
from utils.config import settings

class SpringBootClient:
    """Spring Boot API 클라이언트"""
    
    def __init__(self, base_url: str = "http://backend-svc:8080"):

        """
        초기화
        
        Args:
            base_url: Spring Boot 서버 주소
                     - 로컬: http://localhost:8080
                     - Kubernetes: http://backend-svc:8080
        """
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)  # 30초 타임아웃
    
    async def get_economic_indicators(self) -> Optional[Dict]:
        """
        경제지표 데이터 조회 (MariaDB)
        
        Returns:
            경제지표 딕셔너리 {"기준금리": "3.5%", "M2 통화량": "3500조원", ...}
            실패 시 None
        """
        try:
            logger.info("Spring Boot에서 경제지표 조회 시작")
            
            # ★ Spring Boot의 /api/indicators/latest 엔드포인트 호출
            response = await self.client.get(
                f"{self.base_url}/api/indicators/latest"
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"경제지표 조회 성공: {data}")
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"경제지표 조회 HTTP 오류: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"경제지표 조회 실패: {str(e)}")
            return None
    
    async def get_stock_code_from_name(self, stock_name: str) -> Optional[str]:
        """
        종목명으로 종목 코드 조회 (Spring Boot DB 활용)
        
        Args:
            stock_name: 종목명 (예: "삼성전자")
        
        Returns:
            종목 코드 (예: "005930") 또는 None
        """
        try:
            logger.info(f"종목 코드 조회: {stock_name}")
            
            # Spring Boot의 /api/stocks/search?query={종목명} 엔드포인트 호출
            response = await self.client.get(
                f"{self.base_url}/api/stocks/search",
                params={"query": stock_name}
            )
            response.raise_for_status()
            
            stocks = response.json()
            if stocks and len(stocks) > 0:
                stock_code = stocks[0].get("stockId")
                logger.info(f"종목 코드 조회 성공: {stock_name} → {stock_code}")
                return stock_code
            else:
                logger.warning(f"종목을 찾을 수 없음: {stock_name}")
                return None
                
        except Exception as e:
            logger.error(f"종목 코드 조회 실패: {str(e)}")
            return None
    
    async def close(self):
        """클라이언트 종료"""
        await self.client.aclose()

# 전역 클라이언트 인스턴스
# ★ Kubernetes 환경에서는 "http://backend-svc:8080" 사용
# ★ 로컬 개발 환경에서는 "http://localhost:8080" 사용
# ★ Render 환경에서는 Env Var BACKEND_URL 사용
spring_client = SpringBootClient(base_url=settings.backend_url)

