#!/usr/bin/env bash
export ANTHROPIC_BASE_URL="https://api.discretestack.com"
export ANTHROPIC_AUTH_TOKEN="${DS_API_KEY}"
export ANTHROPIC_DEFAULT_OPUS_MODEL="discretestack-stable-max"
export ANTHROPIC_DEFAULT_SONNET_MODEL="discretestack-stable"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="discretestack-stable-fast"
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192
export MAX_THINKING_TOKENS=8191
export API_TIMEOUT_MS="3000000"

claude "$@"
