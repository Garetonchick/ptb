#!/bin/bash
set -a;source <(echo -n "$ENV_VARS");set +a
python3 bot.py "$@"
