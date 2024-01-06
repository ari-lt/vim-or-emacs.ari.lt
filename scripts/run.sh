#!/usr/bin/env sh

set -u

main() {
    cd src
    kill -9 $(pgrep python3) || true
    python3 -m pip install gunicorn
    python3 -m gunicorn -b 127.0.0.1:8001 -w "$(nproc --all)" main:app &
    disown
}

main "$@"
