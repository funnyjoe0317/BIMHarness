# RAG 데모 — 건축법규를 AI가 근거 기반으로 답하게

> BIMHarness 확장. "AI가 룰을 지어내지 않고 **실제 건축법 문서를 검색해서** 답한다."
> 같은 RAG를 **2가지 방식 × 2가지 인프라**로 구현 → 원리도, 프레임워크도, 보안 환경도 다 커버.

|  | 손코딩 (원리 이해) | LangChain (프레임워크) |
|---|---|---|
| **클라우드** | `rag_demo.py` (Voyage + Claude) | — |
| **온프레미스** | — | `rag_langchain.py` (Ollama, 로컬·무료) |

핵심 4단계(둘 다 동일): 문서 청크 분할 → 임베딩(의미를 벡터로) → 유사도 검색 → 검색결과+질문을 LLM에 증강 → 답변.

---

## A. 온프레미스 버전 (LangChain + Ollama) — 추천

완전 로컬. 인터넷·API키 불필요. 사내 보안망에서 동작.

```powershell
# 1) 모델 2개 받기 (임베딩 + 답변)  ※ Ollama 설치/실행 상태에서
ollama pull nomic-embed-text
ollama pull qwen2.5:7b

# 2) 의존성 (윈도우 venv)
.venv-win\Scripts\pip install -r requirements-rag.txt

# 3) 실행
$env:PYTHONIOENCODING = "utf-8"     # 한글 윈도우 콘솔 (LESSONS L12)
.venv-win\Scripts\python.exe rag_demo\rag_langchain.py
```

기대 출력: 질문 → 관련 룰 검색 → **로컬 qwen2.5가 검색된 법규에만 근거해** 한국어 답변.

---

## B. 클라우드 버전 (손코딩 + Voyage/Claude)

RAG 내부(코사인 유사도 등)를 프레임워크 없이 직접 구현해 원리를 보여주는 버전.

```powershell
# .env 에 VOYAGE_API_KEY, ANTHROPIC_API_KEY 필요
.venv-win\Scripts\python.exe rag_demo\rag_demo.py
```

---

## 연계: 룰 컴파일도 LangChain·온프레미스로

RAG와 별개로, 자연어 룰 → JSON 컴파일 백엔드도 LangChain으로 추가됨
(`src/agents/agent_2_interpreter.py`):

```powershell
# 로컬 모델 + 구조화 출력 — 소형 모델 JSON 깨짐(R5) 방지
$env:PYTHONIOENCODING = "utf-8"
.venv-win\Scripts\python.exe -m src.agents.agent_2_interpreter `
  --backend langchain-ollama --model qwen2.5:7b
```

백엔드: `claude` | `ollama` | `langchain` | `langchain-ollama` | `mock`

---

## 다음 단계 (아이디어)

- 코퍼스를 **실제 건축법 시행령/소방법 조문**으로 교체 → "지어낸 룰"이 아니라 법령 인용.
- RAG로 **검색된 조문을 근거로 룰 자동 생성** → 검증 파이프라인에 투입.
- 임베딩 한국어 성능: `nomic-embed-text` vs `bge-m3` 비교.
