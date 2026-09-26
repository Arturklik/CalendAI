#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)
cd "$ROOT_DIR"

if [ ! -f .env ]; then
    cp .env.example .env
    printf '%s\n' "Created .env from .env.example. Add your AI and Telegram API keys as needed."
    if [ -t 0 ]; then
        printf '%s' "Press Enter to start Docker Compose, or Ctrl+C to edit .env first: "
        IFS= read -r _
    fi
fi

exec docker compose up --build "$@"
