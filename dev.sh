#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID_FILE="$PROJECT_DIR/.backend.pid"
FRONTEND_PID_FILE="$PROJECT_DIR/.frontend.pid"
VENV_DIR="$PROJECT_DIR/backend/.venv"

BACKEND_PORT=8001
FRONTEND_PORT=3000

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[0;33m%s\033[0m\n' "$*"; }

usage() {
  cat <<EOF
Usage: $0 {start|stop|restart|status|install|reseed}

Commands:
  start    Start the backend and frontend dev servers
  stop     Stop running dev servers
  restart  Stop then start dev servers
  status   Show whether dev servers are running
  install  Create venv and install all dependencies
  reseed   Drop database and restart with fresh demo data
EOF
  exit 1
}

# Resolve which Python to use: venv > python3 > python
resolve_python() {
  if [[ -f "$VENV_DIR/bin/python" ]]; then
    echo "$VENV_DIR/bin/python"
  elif command -v python3 &>/dev/null; then
    echo "python3"
  elif command -v python &>/dev/null; then
    echo "python"
  else
    red "No python found. Install Python 3.11+ first."
    exit 1
  fi
}

is_running() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid=$(<"$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    rm -f "$pid_file"
  fi
  return 1
}

start_backend() {
  if is_running "$BACKEND_PID_FILE"; then
    yellow "Backend already running (PID $(<"$BACKEND_PID_FILE"))"
    return
  fi

  local py
  py=$(resolve_python)

  # Check that uvicorn is available
  if ! "$py" -c "import uvicorn" 2>/dev/null; then
    red "Backend dependencies not installed. Run: $0 install"
    exit 1
  fi

  green "Starting backend on port $BACKEND_PORT..."
  cd "$PROJECT_DIR/backend"
  "$py" -m uvicorn server:app --reload --port "$BACKEND_PORT" &
  local pid=$!
  echo "$pid" > "$BACKEND_PID_FILE"
  green "Backend started (PID $pid)"
}

start_frontend() {
  if is_running "$FRONTEND_PID_FILE"; then
    yellow "Frontend already running (PID $(<"$FRONTEND_PID_FILE"))"
    return
  fi

  if [[ ! -d "$PROJECT_DIR/frontend/node_modules" ]]; then
    red "Frontend dependencies not installed. Run: $0 install"
    exit 1
  fi

  green "Starting frontend on port $FRONTEND_PORT..."
  cd "$PROJECT_DIR/frontend"
  PORT=$FRONTEND_PORT yarn start &
  local pid=$!
  echo "$pid" > "$FRONTEND_PID_FILE"
  green "Frontend started (PID $pid)"
}

kill_tree() {
  local parent="$1"
  local sig="${2:-TERM}"
  local children
  children=$(pgrep -P "$parent" 2>/dev/null || true)
  for child in $children; do
    kill_tree "$child" "$sig"
  done
  kill -"$sig" "$parent" 2>/dev/null || true
}

stop_service() {
  local name="$1"
  local pid_file="$2"

  if is_running "$pid_file"; then
    local pid
    pid=$(<"$pid_file")
    green "Stopping $name (PID $pid)..."
    kill_tree "$pid" TERM
    local i=0
    while kill -0 "$pid" 2>/dev/null && (( i < 10 )); do
      sleep 0.5
      i=$((i + 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
      yellow "Force-killing $name (PID $pid)..."
      kill_tree "$pid" 9
    fi
    rm -f "$pid_file"
    green "$name stopped"
  else
    yellow "$name is not running"
  fi
}

do_start() {
  start_backend
  start_frontend
  echo ""
  green "Dev environment is running:"
  echo "  Frontend: http://localhost:$FRONTEND_PORT"
  echo "  Backend:  http://localhost:$BACKEND_PORT/api"
  echo "  Login:    admin / admin123"
  echo ""
  echo "Logs are streaming to this terminal. Press Ctrl+C to stop all."
  trap do_stop INT TERM
  wait
}

do_stop() {
  stop_service "frontend" "$FRONTEND_PID_FILE"
  stop_service "backend" "$BACKEND_PID_FILE"
}

do_restart() {
  do_stop
  sleep 1
  do_start
}

do_reseed() {
  local db_name="${DB_NAME:-barbershop_autopilot}"
  yellow "Dropping database '$db_name'..."
  if command -v mongosh &>/dev/null; then
    mongosh --quiet --eval "db.getMongo().getDB(\"$db_name\").dropDatabase()"
  else
    red "mongosh not found. Install MongoDB Shell first."
    exit 1
  fi
  green "Database dropped. Restarting with fresh seed data..."
  do_stop
  sleep 1
  do_start
}

do_install() {
  # Backend: create venv and install deps
  local sys_python
  sys_python="$(command -v python3 || command -v python)"
  if [[ -z "$sys_python" ]]; then
    red "No python found. Install Python 3.11+ first."
    exit 1
  fi

  if [[ ! -d "$VENV_DIR" ]]; then
    green "Creating virtual environment in backend/.venv..."
    "$sys_python" -m venv "$VENV_DIR"
  fi

  green "Installing backend dependencies..."
  # Filter out emergentintegrations (not on PyPI) and install the rest
  grep -v emergentintegrations "$PROJECT_DIR/backend/requirements.txt" \
    | "$VENV_DIR/bin/pip" install -r /dev/stdin

  # Pin bcrypt to avoid passlib 1.7.4 incompatibility on Python 3.13+
  "$VENV_DIR/bin/pip" install 'bcrypt==4.1.3'

  # Frontend: create .env from example if missing, then install
  if [[ ! -f "$PROJECT_DIR/frontend/.env" && -f "$PROJECT_DIR/frontend/.env.example" ]]; then
    cp "$PROJECT_DIR/frontend/.env.example" "$PROJECT_DIR/frontend/.env"
    green "Created frontend/.env from .env.example"
  fi

  green "Installing frontend dependencies..."
  cd "$PROJECT_DIR/frontend"
  yarn install

  echo ""
  green "All dependencies installed. Run: $0 start"
}

do_status() {
  if is_running "$BACKEND_PID_FILE"; then
    green "Backend:  running (PID $(<"$BACKEND_PID_FILE")) on port $BACKEND_PORT"
  else
    red "Backend:  stopped"
  fi

  if is_running "$FRONTEND_PID_FILE"; then
    green "Frontend: running (PID $(<"$FRONTEND_PID_FILE")) on port $FRONTEND_PORT"
  else
    red "Frontend: stopped"
  fi
}

[[ $# -lt 1 ]] && usage

case "$1" in
  start)   do_start   ;;
  stop)    do_stop     ;;
  restart) do_restart  ;;
  status)  do_status   ;;
  install) do_install  ;;
  reseed)  do_reseed   ;;
  *)       usage       ;;
esac
