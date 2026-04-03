# GPU PC 환경 설정 가이드

> **프로젝트**: FarmOS Shopping Mall + Backoffice
> **Date**: 2026-04-02
> **Prerequisites**: NVIDIA GPU (VRAM 6GB+), Windows 또는 Linux

---

## 1단계: 기본 도구 설치

| 도구 | 설치 방법 | 확인 명령 |
|------|----------|----------|
| **Git** | https://git-scm.com | `git --version` |
| **Python 3.12+** | https://python.org 또는 MS Store | `python --version` |
| **uv** | `pip install uv` 또는 `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `uv --version` |
| **Node.js 20+** | https://nodejs.org (LTS) | `node --version` |
| **NVIDIA 드라이버** | https://nvidia.com/drivers | `nvidia-smi` |

---

## 2단계: AI 도구 설치 (GPU)

### Ollama (LLM 추론 서버)

```bash
# Windows: https://ollama.com/download 에서 설치파일 다운로드
# 설치 후 확인:
ollama --version

# LLM 모델 다운로드 (약 4.7GB)
ollama pull llama3.1:8b

# 임베딩 모델 (RAG용, 약 274MB)
ollama pull nomic-embed-text
```

| 모델 | 크기 | VRAM | 용도 |
|------|------|------|------|
| `llama3.1:8b` | ~4.7GB | 6GB+ | 챗봇, 리포트, 분류 |
| `nomic-embed-text` | ~274MB | 1GB | RAG 벡터 임베딩 |

> GPU VRAM이 8GB 미만이면 `llama3.1:8b` 대신 `phi3:mini` (2.3GB) 사용 가능

### GPU VRAM 요구사항

| GPU | VRAM | 가능 여부 |
|-----|------|----------|
| RTX 3060 | 12GB | llama3.1:8b 정상 구동 |
| RTX 4060 | 8GB | llama3.1:8b 가능 (여유 적음) |
| RTX 3050 | 4GB | `phi3:mini` 또는 `gemma2:2b` 사용 |
| GTX 1660 | 6GB | llama3.1:8b 4bit 양자화 가능 |

---

## 3단계: 프로젝트 클론 & 설정

```bash
git clone <your-repo-url> FarmOS
cd FarmOS
```

---

## 4단계: Backend 실행 (port 4000)

```bash
cd shopping_mall/backend

# Python 가상환경 + 의존성 설치
uv venv
uv sync

# 기본 쇼핑몰 더미 데이터 시드
uv run python db/seed.py

# 백오피스 더미 데이터 시드
uv run python db/seed_backoffice.py

# 서버 실행
uv run python main.py
```

실행 확인:
- API: http://localhost:4000
- Swagger UI: http://localhost:4000/docs

---

## 5단계: Ollama 서버 실행 (port 11434)

```bash
# 별도 터미널에서
ollama serve
```

실행 확인:
```bash
curl http://localhost:11434/api/tags
```

> Ollama가 꺼져 있어도 백엔드는 fallback 응답으로 정상 동작합니다.

---

## 6단계: 쇼핑몰 Frontend 실행 (port 5174)

```bash
cd shopping_mall/frontend
npm install
npm run dev
```

확인: http://localhost:5174

---

## 7단계: 백오피스 Frontend 실행 (port 5175)

```bash
cd shopping_mall/backoffice
npm install
npm run dev
```

확인: http://localhost:5175

---

## 전체 실행 구성도

```
터미널 1: Backend API
  cd shopping_mall/backend && uv run python main.py
  → http://localhost:4000 (Swagger: /docs)

터미널 2: Ollama LLM Server (GPU)
  ollama serve
  → http://localhost:11434

터미널 3: 쇼핑몰 Frontend (고객용)
  cd shopping_mall/frontend && npm run dev
  → http://localhost:5174

터미널 4: 백오피스 Frontend (관리자용)
  cd shopping_mall/backoffice && npm run dev
  → http://localhost:5175
```

---

## 포트 요약

| 서비스 | 포트 | GPU | 필수 |
|--------|:----:|:---:|:----:|
| Shopping Mall Backend (FastAPI) | 4000 | No | Yes |
| Ollama LLM | 11434 | **Yes** | No (fallback 있음) |
| Shopping Mall Frontend | 5174 | No | 선택 |
| Backoffice Frontend | 5175 | No | 선택 |
| FarmOS Backend (기존) | 8000 | No | 별도 |
| FarmOS Frontend (기존) | 5173 | No | 별도 |

---

## 빠른 테스트

```bash
# 1. 챗봇 테스트 (Ollama 실행 상태에서)
curl -X POST http://localhost:4000/api/chatbot/ask \
  -H "Content-Type: application/json" \
  -H "X-User-Id: 1" \
  -d '{"question": "사과는 어떻게 보관하나요?"}'

# 2. 대시보드 데이터 확인
curl http://localhost:4000/api/analytics/dashboard \
  -H "X-User-Id: 1"

# 3. 고객 세그먼트 확인
curl http://localhost:4000/api/analytics/segments \
  -H "X-User-Id: 1"
```

---

## 문제 해결

| 문제 | 원인 | 해결 |
|------|------|------|
| `uv sync` 실패 | Python 3.12 미설치 | `python --version` 확인 후 설치 |
| `npm install` 실패 | Node.js 미설치 | `node --version` 확인 후 설치 |
| 챗봇 응답이 rule-based만 나옴 | Ollama 미실행 | `ollama serve` 실행 후 재시도 |
| `nvidia-smi` 안 됨 | NVIDIA 드라이버 미설치 | 드라이버 설치 후 재부팅 |
| Ollama 모델 다운로드 느림 | 네트워크 | `llama3.1:8b`는 약 4.7GB, 시간 소요 정상 |
| port 4000 사용 중 | 다른 프로세스 | `netstat -ano \| findstr :4000` 으로 확인 |
