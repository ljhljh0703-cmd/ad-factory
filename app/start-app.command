#!/bin/bash
# 광고 공장 앱 켜기 (맥에서 두 번 클릭)
set -e
cd "$(dirname "$0")"
command -v node >/dev/null || { echo "Node 가 없습니다. https://nodejs.org 에서 LTS 를 설치한 뒤 다시 여세요."; read -r; exit 1; }
command -v python3 >/dev/null || { echo "python3 가 없습니다. 터미널에서 xcode-select --install 을 먼저 하세요."; read -r; exit 1; }
if [ ! -d node_modules/electron ]; then echo "처음 한 번 앱 부품을 받습니다(1~2분)…"; npm install --no-audit --no-fund; fi
# AI: 기본은 클라우드 세션(ADF_AI=cloud). 앱이 요청을 저장소에 올리고, Code 탭 세션이 답한다.
#     맥의 Claude Code 로그인으로 바로 돌리려면 ADF_AI=local 로 켠다.
export PATH="$HOME/.local/bin:$HOME/.claude/local:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ "${ADF_AI:-cloud}" = "local" ] && command -v claude >/dev/null; then export ADF_PROVIDER=claude-code; echo "AI: 맥 Claude Code 로그인으로 돕니다."
else export ADF_PROVIDER=session; echo "AI: 클라우드 세션이 답합니다(앱의 「클라우드에 맡기기」→ Code 탭 → 「클라우드 결과 받기」)."
  git -C .. rev-parse --git-dir >/dev/null 2>&1 || echo "주의: 이 폴더가 깃 저장소가 아닙니다. git clone https://github.com/ljhljh0703-cmd/ad-factory 로 받은 폴더에서 여세요."; fi
# 수집기 기록 내려받기 열쇠: Vercel jelly-panic-collector → Settings → Environment Variables → EXPORT_KEY 값을 ~/.adf-export-key 파일에 한 줄로
if [ -z "$ADF_EXPORT_KEY" ] && [ -f "$HOME/.adf-export-key" ]; then export ADF_EXPORT_KEY="$(tr -d '[:space:]' < "$HOME/.adf-export-key")"; fi
[ -n "$ADF_EXPORT_KEY" ] || echo "알림: 수집기 열쇠가 없어 성과 받기만 안 됩니다(다른 화면은 그대로)."
npm start
