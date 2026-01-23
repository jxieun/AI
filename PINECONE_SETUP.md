# 🎯 Pinecone Vector DB 설정 가이드

Pinecone은 **영구 무료**로 벡터 데이터베이스를 제공합니다 (1M 벡터).

---

## 1️⃣ Pinecone 계정 생성

1. https://www.pinecone.io 접속
2. **"Start Free"** 클릭
3. 이메일로 가입 또는 Google 계정으로 로그인
4. 이메일 인증 완료

---

## 2️⃣ API 키 생성

### 2-1. API Key 가져오기
1. Pinecone Console 로그인
2. 왼쪽 메뉴 → **"API Keys"** 클릭
3. 기본 API Key가 자동 생성되어 있음
4. **"Copy"** 클릭하여 API Key 복사 (저장 필수!)

**형식**:
```
pcsk_xxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 3️⃣ Index 생성

### 3-1. 새 Index 만들기
1. Pinecone Console → **"Indexes"** (왼쪽 메뉴)
2. **"Create Index"** 클릭
3. Index 정보 입력:
   - **Name**: `robo-advisor-reports` (영문 소문자, 숫자, 하이픈만 가능)
   - **Dimensions**: `1536` (OpenAI text-embedding-ada-002 벡터 크기)
   - **Metric**: `cosine` (유사도 측정 방식)
   - **Region**: `us-east-1` (무료 플랜은 특정 지역만 가능)
   - **Plan**: **Starter** (무료) 선택
4. **"Create Index"** 클릭

### 3-2. Index 준비 대기
- Index 생성까지 약 1~2분 소요
- Status가 **"Ready"**가 될 때까지 대기

---

## 4️⃣ Render 환경 변수 설정

Render 대시보드 → **jeonbongjun-ai** → **Environment**:

### 추가할 환경 변수

| Key | Value | 예시 |
|-----|-------|------|
| `PINECONE_API_KEY` | Pinecone API Key | `pcsk_xxxxx_xxxx` |
| `PINECONE_INDEX_NAME` | Index 이름 | `robo-advisor-reports` |
| `PINECONE_ENVIRONMENT` | 환경 (지역) | `us-east-1` |

---

## 5️⃣ 로컬 개발 환경 설정

### 5-1. `.env` 파일 생성/수정 (AI 폴더)

```bash
cd /Users/rose/Downloads/mini3/AI
cat > .env << EOF
OPENAI_API_KEY=sk-proj-your-api-key
PINECONE_API_KEY=pcsk_xxxxx_xxxx
PINECONE_INDEX_NAME=robo-advisor-reports
PINECONE_ENVIRONMENT=us-east-1
BACKEND_URL=http://localhost:8080
EOF
```

---

## 6️⃣ 증권사 리포트 임베딩

### 6-1. PDF 리포트 준비
```bash
cd /Users/rose/Downloads/mini3/AI

# data/reports/ 폴더에 PDF 파일 추가
# 파일명 형식: {증권사}_{종목}_{날짜}.pdf
# 예: NH투자증권_삼성전자_20251015.pdf
```

### 6-2. 임베딩 스크립트 실행

```bash
# 가상환경 활성화
source venv/bin/activate

# 의존성 설치 (Pinecone 버전)
pip install -r requirements.txt

# 임베딩 스크립트 실행
python scripts/embed_reports_pinecone.py
```

**스크립트가 자동으로**:
1. PDF 파일 로드
2. 텍스트 추출 및 청킹
3. OpenAI로 임베딩 생성
4. Pinecone에 벡터 저장

---

## 7️⃣ Pinecone Dashboard에서 확인

1. Pinecone Console → **Indexes** → `robo-advisor-reports` 클릭
2. **Overview** 탭:
   - **Total Vector Count**: 임베딩된 벡터 개수 확인
   - **Index Fullness**: 사용량 확인 (무료 플랜: 1M 벡터)
3. **Browse** 탭:
   - 저장된 벡터 ID 및 메타데이터 확인

---

## ✅ 검증

### AI Service 로그 확인
```bash
# 로컬 또는 Render 로그에서 확인
python main.py

# 예상 출력:
# INFO: Pinecone initialized successfully
# INFO: Connected to index: robo-advisor-reports
```

### 벡터 검색 테스트
```bash
curl -X POST http://localhost:8000/ai/query \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-123",
    "question": "삼성전자 AI 반도체 전망은?"
  }'
```

**예상 응답**:
```json
{
  "answer": "NH투자증권 리포트에 따르면...",
  "category": "analyst_report",
  "sources": [...]
}
```

---

## 🎁 Pinecone 무료 플랜 제한

- ✅ **1M 벡터** 저장 (충분함)
- ✅ **무제한** 쿼리
- ✅ **1536 차원** (OpenAI embedding 호환)
- ✅ **1개** Index
- ✅ **영구 무료** (시간 제한 없음)

**예상 사용량**: PDF 리포트 100개 = 약 10,000~50,000 벡터

---

## 🔧 문제 해결

### API Key 오류
```
Error: Invalid API key
```

**해결**:
1. Pinecone Console에서 API Key 재확인
2. `.env` 파일에 정확히 복사되었는지 확인
3. 앞뒤 공백 제거

### Index Not Found
```
Error: Index 'robo-advisor-reports' not found
```

**해결**:
1. Pinecone Console → **Indexes**에서 Index 이름 확인
2. Status가 **"Ready"**인지 확인
3. 환경 변수 `PINECONE_INDEX_NAME` 값 재확인

### Dimension Mismatch
``
Error: Vector dimension 3072 does not match index dimension 1536
```

**해결**:
- OpenAI embedding 모델 확인
- `text-embedding-ada-002` 사용 시 1536 차원
- `text-embedding-3-small` 사용 시 1536 차원
- `text-embedding-3-large` 사용 시 3072 차원

**Index 차원 수정 필요 시**:
- 새 Index 생성 (기존 Index는 삭제 불가, 차원 변경 불가)

---

## 💡 성능 최적화

### Batch Upsert
벡터를 한 번에 여러 개 업로드:
```python
# 100개씩 배치 처리
batch_size = 100
for i in range(0, len(vectors), batch_size):
    batch = vectors[i:i+batch_size]
    index.upsert(vectors=batch)
```

### 메타데이터 필터링
검색 시 메타데이터로 필터링:
```python
results = index.query(
    vector=query_vector,
    filter={"securities_firm": "NH투자증권"},
    top_k=3
)
```

### Namespace 사용
여러 카테고리 분리:
```python
# 증권사별 namespace
index.upsert(vectors=vectors, namespace="NH투자증권")
index.query(vector=query_vector, namespace="NH투자증권")
```
