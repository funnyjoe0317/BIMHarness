"""
================================================================
 RAG 미니 데모 — 건축법규를 AI가 정확히 답하게 하기
================================================================
 목적: RAG(검색증강생성)가 어떻게 동작하는지 직접 만들어 이해한다.
 시나리오: 사용자가 건축법규를 물으면, 관련 조항을 검색해서
          그 근거를 바탕으로 Claude가 정확히 답한다 (환각 방지).

 RAG 4단계 구조:
   [준비] 1.문서를 청크로 분할 → 2.임베딩(의미를 벡터로) → 3.벡터 저장
   [질문] 4.질문 임베딩 → 5.유사 청크 검색 → 6.검색결과+질문을 LLM에 → 7.답변

 실행: python rag_demo.py
 필요: VOYAGE_API_KEY, ANTHROPIC_API_KEY (.env)
================================================================
"""

import os
import re
import numpy as np
import voyageai
import anthropic
from dotenv import load_dotenv

# .env에서 API 키 로드 (IFC-LLM 루트의 .env 사용)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# 클라이언트 준비
# - Voyage AI: 임베딩(글 → 의미 벡터) 전용. Anthropic 공식 추천 임베딩.
# - Anthropic: 최종 답변 생성(LLM).
voyage = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

EMBED_MODEL = "voyage-3.5"          # 임베딩 모델 (한국어 지원)
CHAT_MODEL = "claude-opus-4-8"      # 답변 생성 모델
DOC_PATH = os.path.join(os.path.dirname(__file__), "corpus", "rules_korean_law.md")


# ────────────────────────────────────────────────────────────
# [준비 1단계] 문서를 '청크(chunk)'로 분할
#   왜? 문서 전체를 통째로 검색하면 너무 크고 부정확.
#   '## R'(룰 하나) 단위로 잘라서, 룰 하나하나를 검색 단위로 만든다.
# ────────────────────────────────────────────────────────────
def load_and_chunk(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        text = f.read()

    # "## R1. 방화구획" 같은 룰 헤더 기준으로 분할
    parts = re.split(r"\n(?=## R\d)", text)
    chunks = []
    for p in parts:
        p = p.strip()
        if p.startswith("## R"):                       # 룰 섹션만 청크로
            title = p.split("\n")[0].replace("## ", "")  # "R1. 방화구획"
            chunks.append({"title": title, "text": p})
    return chunks


# ────────────────────────────────────────────────────────────
# [준비 2단계] 임베딩 — 글을 '의미를 담은 숫자(벡터)'로 변환
#   "벽 두께"와 "외벽 규격"이 단어는 달라도 의미가 가까우면
#   벡터도 가까워진다. 그래서 '의미 기반 검색'이 가능해진다.
# ────────────────────────────────────────────────────────────
def embed(texts: list[str], input_type: str) -> np.ndarray:
    # input_type="document" (저장용 문서) / "query" (검색용 질문)
    #   → Voyage가 둘을 구분해 더 정확히 매칭
    result = voyage.embed(texts, model=EMBED_MODEL, input_type=input_type)
    return np.array(result.embeddings)


# ────────────────────────────────────────────────────────────
# [검색 핵심] 코사인 유사도 — 두 벡터가 얼마나 '의미상 가까운가'
#   1에 가까울수록 비슷, 0에 가까울수록 무관.
#   질문 벡터와 모든 문서 벡터를 비교해 가장 가까운 걸 찾는다.
# ────────────────────────────────────────────────────────────
def cosine_search(query_vec: np.ndarray, doc_vecs: np.ndarray, top_k: int = 2):
    # 정규화 후 내적 = 코사인 유사도
    q = query_vec / np.linalg.norm(query_vec)
    d = doc_vecs / np.linalg.norm(doc_vecs, axis=1, keepdims=True)
    scores = d @ q                       # 각 문서와의 유사도 점수
    top_idx = np.argsort(scores)[::-1][:top_k]   # 점수 높은 top_k개
    return [(int(i), float(scores[i])) for i in top_idx]


# ────────────────────────────────────────────────────────────
# [질문 6~7단계] 증강 + 생성
#   검색으로 찾은 법규 조항을 질문과 함께 Claude에게 주고,
#   "이 근거만 보고 답하라"고 지시 → 환각 없이 근거 기반 답변.
# ────────────────────────────────────────────────────────────
def answer_with_rag(question: str, retrieved: list[str]) -> str:
    context = "\n\n---\n\n".join(retrieved)
    prompt = f"""아래는 건축법규 문서에서 검색된 관련 조항입니다.
반드시 이 내용에만 근거해서 한국어로 답하세요.
문서에 없는 내용은 지어내지 말고 "문서에 없음"이라고 답하세요.

[검색된 법규]
{context}

[질문]
{question}

[답변]"""
    msg = claude.messages.create(
        model=CHAT_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ════════════════════════════════════════════════════════════
#  메인 — RAG 전체 파이프라인 실행
# ════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print(" RAG 미니 데모 — 건축법규 검색 + Claude 답변")
    print("=" * 60)

    # [준비] 문서 적재 → 청크 → 임베딩 (프로그램 시작 시 1번)
    print("\n[준비] 건축법규 문서를 청크로 나누고 임베딩 중...")
    chunks = load_and_chunk(DOC_PATH)
    doc_vecs = embed([c["text"] for c in chunks], input_type="document")
    print(f"  → 룰 {len(chunks)}개를 벡터로 저장 완료")
    for c in chunks:
        print(f"     · {c['title']}")

    # [질문] 테스트 질문들로 검색→답변 시연
    questions = [
        "비상계단 너비는 얼마 이상이어야 해?",
        "방화구획 기준이 뭐야?",
    ]

    for q in questions:
        print("\n" + "─" * 60)
        print(f"❓ 질문: {q}")

        # 4단계: 질문도 임베딩
        q_vec = embed([q], input_type="query")[0]

        # 5단계: 벡터 유사도로 가장 가까운 룰 검색
        hits = cosine_search(q_vec, doc_vecs, top_k=2)
        print("🔍 검색된 관련 룰 (유사도 순):")
        retrieved = []
        for idx, score in hits:
            print(f"   · {chunks[idx]['title']}  (유사도 {score:.3f})")
            retrieved.append(chunks[idx]["text"])

        # 6~7단계: 검색 결과를 근거로 Claude가 답변
        print("💬 Claude 답변 (검색된 법규 근거):")
        ans = answer_with_rag(q, retrieved)
        print("   " + ans.replace("\n", "\n   "))

    print("\n" + "=" * 60)
    print(" 끝. 핵심: LLM이 '기억'이 아니라 '검색된 실제 법규'로 답했다.")
    print("=" * 60)


if __name__ == "__main__":
    main()
