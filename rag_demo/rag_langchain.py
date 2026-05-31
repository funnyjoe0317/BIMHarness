"""
================================================================
 RAG (LangChain · 온프레미스 버전) — 건축법규 검색 + 로컬 LLM 답변
================================================================
 rag_demo.py(밑바닥 손코딩 + 클라우드 Voyage/Claude)의 짝.
 이 파일은 같은 RAG를 **LangChain 프레임워크 + 완전 온프레미스**로 구현한다.

   임베딩: OllamaEmbeddings(nomic-embed-text)   ← 로컬, 무료
   LLM    : ChatOllama(qwen2.5)                  ← 로컬, 무료
   벡터스토어: InMemoryVectorStore               ← 추가 DB 설치 없음
   체인   : LCEL (retriever | prompt | llm | parser)

 → IFC/법규 문서가 사내망 밖으로 안 나감 (BIMHarness 온프레미스 서사와 일치).

 실행 (윈도우, Ollama 켜진 상태):
   ollama pull nomic-embed-text
   ollama pull qwen2.5:7b
   python rag_demo/rag_langchain.py
================================================================
"""

import os
import re

CORPUS = os.path.join(os.path.dirname(__file__), "corpus", "rules_korean_law.md")
EMBED_MODEL = "nomic-embed-text"      # 로컬 임베딩 모델 (Ollama)
CHAT_MODEL = "qwen2.5:7b"             # 로컬 답변 모델 (Ollama)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


# ────────────────────────────────────────────────────────────
# [준비 1] 문서를 룰 단위 청크로 분할 (LLM 불필요 — 테스트 가능)
# ────────────────────────────────────────────────────────────
def load_and_chunk(path: str = CORPUS) -> list[dict]:
    """'## R1. 방화구획' 같은 룰 헤더 기준으로 문서를 청크 분할."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parts = re.split(r"\n(?=## [A-Z])", text)
    chunks = []
    for p in parts:
        p = p.strip()
        m = re.match(r"## (.+)", p)
        if m and re.search(r"\d", m.group(1)):     # 제목에 숫자 있는 룰 섹션만
            chunks.append({"title": m.group(1).strip(), "text": p})
    return chunks


# ────────────────────────────────────────────────────────────
# [준비 2~3] LangChain 벡터스토어 구성 (임베딩 → 인메모리 저장)
# ────────────────────────────────────────────────────────────
def build_vectorstore(chunks: list[dict]):
    from langchain_core.documents import Document
    from langchain_core.vectorstores import InMemoryVectorStore
    from langchain_ollama import OllamaEmbeddings

    embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_HOST)
    docs = [
        Document(page_content=c["text"], metadata={"title": c["title"]})
        for c in chunks
    ]
    return InMemoryVectorStore.from_documents(docs, embedding=embeddings)


# ────────────────────────────────────────────────────────────
# [체인] LCEL RAG: 검색 → 프롬프트 증강 → 로컬 LLM 생성
# ────────────────────────────────────────────────────────────
def build_rag_chain(vectorstore):
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough
    from langchain_ollama import ChatOllama

    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
    llm = ChatOllama(model=CHAT_MODEL, base_url=OLLAMA_HOST, temperature=0)

    prompt = ChatPromptTemplate.from_template(
        "아래는 건축법규 문서에서 검색된 관련 조항입니다.\n"
        "반드시 이 내용에만 근거해 한국어로 답하세요.\n"
        "문서에 없으면 지어내지 말고 '문서에 없음'이라고 답하세요.\n\n"
        "[검색된 법규]\n{context}\n\n[질문]\n{question}\n\n[답변]"
    )

    def format_docs(docs):
        return "\n\n---\n\n".join(d.page_content for d in docs)

    return (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )


# ════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print(" RAG (LangChain · 온프레미스) — 건축법규 + 로컬 qwen2.5")
    print("=" * 60)

    chunks = load_and_chunk()
    print(f"\n[준비] 룰 {len(chunks)}개를 청크로 분할:")
    for c in chunks:
        print(f"   · {c['title']}")

    print(f"\n[준비] {EMBED_MODEL}로 임베딩 → 인메모리 벡터스토어...")
    vs = build_vectorstore(chunks)
    chain = build_rag_chain(vs)

    for q in ["비상계단 너비는 얼마 이상이어야 해?", "방화구획 기준이 뭐야?"]:
        print("\n" + "─" * 60)
        print(f"❓ 질문: {q}")
        hits = vs.similarity_search(q, k=2)
        print("🔍 검색된 관련 룰:")
        for d in hits:
            print(f"   · {d.metadata.get('title')}")
        print("💬 로컬 LLM 답변 (검색된 법규 근거):")
        ans = chain.invoke(q)
        print("   " + ans.replace("\n", "\n   "))

    print("\n" + "=" * 60)
    print(" 끝. 핵심: 클라우드 없이 로컬 모델이 '검색된 실제 법규'로 답했다.")
    print("=" * 60)


if __name__ == "__main__":
    main()
