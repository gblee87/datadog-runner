"""
🔐 Auth Service (Python FastAPI) - Datadog Runner 프로젝트

인증 및 사용자 관리 마이크로서비스
- 하이브리드 인증: 기존 demo 사용자(평문) + 신규 사용자(SHA-256 해싱)
- 세션 기반 인증: Redis 세션 스토어 (24시간 TTL)
- 점수 제출: 게임 점수를 Redis ZSET에 저장
- Datadog APM: ddtrace-run으로 자동 계측
- CORS: 분산 트레이싱 헤더 지원 (RUM-APM 연결)

엔드포인트:
- POST /api/auth/login     : 로그인 (쿠키 기반 세션)
- POST /api/auth/signup    : 회원가입 (자동 로그인)
- GET  /api/auth/logout    : 로그아웃 (세션 삭제)
- GET  /api/session/me     : 현재 사용자 정보
- POST /api/score          : 게임 점수 제출
"""
import os, secrets, time, hashlib
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from pydantic import BaseModel
import asyncpg
import redis.asyncio as aioredis
#from ddtrace import patch_all; patch_all()  # Datadog APM 트레이싱
import logging
from starlette.middleware.cors import CORSMiddleware

app = FastAPI(title="auth-python")
# CORS 설정 - 프론트엔드에서 쿠키 기반 인증 및 RUM-APM 연결 허용
app.add_middleware(CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=[
        "*",
        "x-datadog-trace-id",
        "x-datadog-parent-id", 
        "x-datadog-origin",
        "x-datadog-sampling-priority",
        "traceparent",
        "tracestate",
        "b3"
    ],
    expose_headers=[
        "x-datadog-trace-id",
        "x-datadog-parent-id",
        "traceparent",
        "tracestate"
    ]
)

# 데이터베이스 및 세션 설정
PG_DSN   = os.getenv("PG_DSN", "postgresql://app:app@postgres:5432/app")
REDIS_DSN= os.getenv("REDIS_DSN", "redis://redis:6379/0")
COOKIE_NAME = "sid"
SESSION_TTL = 60*60*24  # 24시간 세션 유지

async def get_pg():
    return await asyncpg.connect(PG_DSN)

async def get_redis():
    return await aioredis.from_url(REDIS_DSN, decode_responses=True)

# 헬스체크 엔드포인트 - ALB 헬스체크용
@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "auth-python"}

# 요청 데이터 모델
class LoginIn(BaseModel):
    id: str
    pw: str

# 회원가입 기능 추가를 위한 새로운 모델 - 기존 demo 전용에서 확장
class SignupIn(BaseModel):
    id: str    # 최소 3글자 (프론트엔드 및 서버에서 검증)
    pw: str    # 최소 4글자 (프론트엔드 및 서버에서 검증)

def hash_password(password: str) -> str:
    """
    SHA-256 기반 비밀번호 해싱 - 회원가입 시 보안 강화
    기존 demo 사용자(평문 저장)와 호환성 유지하면서 새 사용자는 해시 적용
    데모 목적으로 간단한 SHA-256 사용 (프로덕션에서는 bcrypt, scrypt 등 권장)
    """
    return hashlib.sha256(password.encode()).hexdigest()

# 로그인 엔드포인트 - 기존 demo 사용자와 새 사용자 모두 지원
@app.post("/auth/login")
@app.post("/api/auth/login")
async def login(inp: LoginIn, resp: Response):
    pg = await get_pg()
    row = await pg.fetchrow("SELECT id, pw_hash FROM users WHERE id=$1", inp.id)
    await pg.close()
    if not row:
        raise HTTPException(401, "no user")
    
    # 비밀번호 검증 - 기존 demo 사용자와 해시된 비밀번호 모두 지원
    # init.sql의 기존 demo 사용자: pw_hash = "demo" (평문)
    # 새로 가입한 사용자: pw_hash = SHA-256 해시값
    if row["pw_hash"] == "demo" and inp.pw == "demo":
        # 레거시 demo 사용자 처리 (하위 호환성)
        pass
    elif hash_password(inp.pw) != row["pw_hash"]:
        raise HTTPException(401, "bad pw")
    
    # 세션 생성 및 쿠키 설정
    sid = secrets.token_urlsafe(24)
    r = await get_redis()
    await r.setex(f"session:{sid}", SESSION_TTL, row["id"])
    await r.close()
    resp.set_cookie(COOKIE_NAME, sid, httponly=True, secure=False, samesite="lax", max_age=SESSION_TTL)
    return {"ok": True}

# 회원가입 엔드포인트 - 기존 demo 전용 시스템을 일반 사용자로 확장
# 입력 검증, 중복 체크, 비밀번호 해싱, 자동 로그인까지 처리
@app.post("/auth/signup")
@app.post("/api/auth/signup")
async def signup(inp: SignupIn, resp: Response):
    # 입력 검증 - 프론트엔드에서도 체크하지만 서버에서 재검증 (보안)
    if not inp.id or len(inp.id) < 3:
        raise HTTPException(400, "ID는 3글자 이상이어야 합니다")
    if not inp.pw or len(inp.pw) < 4:
        raise HTTPException(400, "비밀번호는 4글자 이상이어야 합니다")
    
    pg = await get_pg()
    
    # 중복 ID 체크 - 기존 demo 사용자 포함 모든 사용자와 중복 방지
    existing_user = await pg.fetchrow("SELECT id FROM users WHERE id=$1", inp.id)
    if existing_user:
        await pg.close()
        raise HTTPException(400, "이미 존재하는 아이디입니다")
    
    # 새 사용자 생성 - SHA-256으로 해싱된 비밀번호와 함께 저장
    hashed_pw = hash_password(inp.pw)
    await pg.execute("INSERT INTO users(id, pw_hash) VALUES ($1, $2)", inp.id, hashed_pw)
    await pg.close()
    
    # 회원가입 후 자동 로그인 - UX 개선을 위해 바로 세션 생성하고 쿠키 설정
    sid = secrets.token_urlsafe(24)
    r = await get_redis()
    await r.setex(f"session:{sid}", SESSION_TTL, inp.id)
    await r.close()
    resp.set_cookie(COOKIE_NAME, sid, httponly=True, secure=False, samesite="lax", max_age=SESSION_TTL)
    
    return {"ok": True, "message": "회원가입이 완료되었습니다"}

@app.get("/session/me")
@app.get("/api/session/me")
async def me(req: Request):
    sid = req.cookies.get(COOKIE_NAME)
    if not sid:
        raise HTTPException(401)
    r = await get_redis()
    uid = await r.get(f"session:{sid}")
    await r.close()
    if not uid:
        raise HTTPException(401)
    return {"user_id": uid}

@app.get("/auth/logout")
@app.get("/api/auth/logout")
async def logout(resp: Response, req: Request):
    sid = req.cookies.get(COOKIE_NAME)
    if sid:
        r = await get_redis()
        await r.delete(f"session:{sid}")
        await r.close()
    resp.delete_cookie(COOKIE_NAME)
    return {"ok": True}

class ScoreIn(BaseModel):
    score: int

@app.post("/score")
@app.post("/api/score")
async def submit_score(inp: ScoreIn, req: Request):
    sid = req.cookies.get(COOKIE_NAME)
    if not sid:
        raise HTTPException(401)
    r = await get_redis()
    uid = await r.get(f"session:{sid}")
    if not uid:
        await r.close()
        raise HTTPException(401)
    ts = int(time.time()*1000)
    # Update best score only when higher
    curr = await r.zscore("game:scores", uid)
    if (curr is None) or (inp.score > float(curr)):
        await r.zadd("game:scores", {uid: inp.score})
        await r.hset(f"game:scores:best:{uid}", mapping={"score": inp.score, "ts": ts})
    await r.close()
    return {"ok": True}
