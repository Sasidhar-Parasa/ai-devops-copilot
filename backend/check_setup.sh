#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Run this from inside your backend/ folder:
#   cd ~/ai-devops-copilot/backend
#   bash check_setup.sh
# ─────────────────────────────────────────────────────────────────
echo ""
echo "=== AI DevOps Copilot — Setup Checker ==="
echo ""

# 1. Check .env file
if [ -f ".env" ]; then
  echo "✅ .env file exists"
  if grep -q "GROQ_API_KEY=gsk_" .env 2>/dev/null; then
    KEY=$(grep "GROQ_API_KEY" .env | cut -d= -f2 | head -c 12)
    echo "✅ GROQ_API_KEY found: ${KEY}..."
  elif grep -q "GROQ_API_KEY=" .env 2>/dev/null; then
    echo "❌ GROQ_API_KEY is in .env but looks empty or invalid"
    echo "   It should start with gsk_"
    echo "   Current value: $(grep 'GROQ_API_KEY' .env)"
  else
    echo "❌ GROQ_API_KEY not found in .env"
    echo "   Add:  GROQ_API_KEY=gsk_your_key_here"
  fi
else
  echo "❌ .env file NOT found in $(pwd)"
  echo "   Run: cp .env.example .env"
  echo "   Then add: GROQ_API_KEY=gsk_your_key_here"
fi

# 2. Test Groq API directly
echo ""
echo "--- Testing Groq API connection ---"
GROQ_KEY=$(grep "GROQ_API_KEY" .env 2>/dev/null | cut -d= -f2 | tr -d ' "'"'" || echo "")

if [ -z "$GROQ_KEY" ]; then
  echo "⏭️  Skipping API test — no key found"
else
  echo "Testing model: llama-3.3-70b-versatile"
  HTTP=$(curl -s -o /tmp/groq_test.json -w "%{http_code}" \
    -X POST "https://api.groq.com/openai/v1/chat/completions" \
    -H "Authorization: Bearer $GROQ_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"reply with just: ok"}],"max_tokens":5}')

  if [ "$HTTP" = "200" ]; then
    echo "✅ Groq API works! HTTP $HTTP"
    echo "   Response: $(cat /tmp/groq_test.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])')"
  else
    echo "❌ Groq API returned HTTP $HTTP"
    echo "   Response: $(cat /tmp/groq_test.json)"
    echo ""
    echo "   Common fixes:"
    echo "   - Invalid key: regenerate at https://console.groq.com"
    echo "   - Rate limit: wait a minute and retry"
  fi
fi

echo ""
echo "--- Done ---"
echo ""