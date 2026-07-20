import os

import pytest


@pytest.fixture
def conn():
    """pgvector 연결. 접속 불가 시 기본은 skip(로컬 개발은 DB 없이 가능).

    단, REQUIRE_DB가 설정되면(CI/회귀 게이트) skip 대신 fail —
    DB 테스트가 조용히 건너뛰어져 '초록불=검증됨'이 거짓이 되는 것을 막는다.
    """
    psycopg = pytest.importorskip("psycopg")
    from app.config import get_settings

    try:
        c = psycopg.connect(get_settings().database_url, connect_timeout=3)
    except psycopg.OperationalError as e:
        if os.getenv("REQUIRE_DB"):
            pytest.fail(f"REQUIRE_DB 설정됨 — pgvector DB 접속 필수인데 실패: {e}")
        pytest.skip(f"pgvector DB 접속 불가: {e}")
    yield c
    with c.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS chunks")
    c.commit()
    c.close()
