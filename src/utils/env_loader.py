"""
환경변수 자동 로드
.env 파일이 있으면 환경변수에 로드

사용:
  from src.utils.env_loader import load_env
  load_env()
"""

import os
from pathlib import Path


def load_env(env_path: str = None) -> bool:
    """프로젝트 루트의 .env 파일 로드"""
    if env_path is None:
        # src/utils/env_loader.py에서 프로젝트 루트 찾기
        env_path = Path(__file__).parent.parent.parent / ".env"
    else:
        env_path = Path(env_path)

    if not env_path.exists():
        return False

    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        return True
    except ImportError:
        # python-dotenv 없어도 동작하게
        _load_manual(env_path)
        return True


def _load_manual(env_path: Path):
    """python-dotenv 없을 때 수동 파싱"""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # 이미 환경변수에 있으면 덮어쓰지 않음
        os.environ.setdefault(key, value)


def check_api_key() -> tuple[bool, str]:
    """ANTHROPIC_API_KEY 확인"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return False, "ANTHROPIC_API_KEY가 설정되지 않음"
    if "여기에" in key or "YOUR" in key.upper():
        return False, ".env 파일에 실제 키를 채우세요"
    if not key.startswith("sk-ant-"):
        return False, f"키 형식이 이상함 (sk-ant-로 시작해야 함)"
    return True, f"OK ({key[:15]}...)"


if __name__ == "__main__":
    loaded = load_env()
    print(f"✅ .env 로드: {loaded}")
    ok, msg = check_api_key()
    print(f"{'✅' if ok else '❌'} API Key: {msg}")
