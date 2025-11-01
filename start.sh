#!/bin/bash
# ============================================
# NutriAI Bot - Startup Script for Linux
# ============================================
# This script starts all necessary services for the bot:
# 1. Redis (if not running)
# 2. PostgreSQL (if not running)
# 3. Celery Worker (background tasks)
# 4. Celery Beat (task scheduler)
# 5. NutriAI Bot (main application)
# ============================================

echo ""
echo "============================================"
echo "  Starting NutriAI Bot..."
echo "============================================"
echo ""

# Check if we're in the correct directory
if [ ! -f "app/bot/main.py" ]; then
    echo "ERROR: Please run this script from the tricer directory!"
    echo "Current directory: $(pwd)"
    exit 1
fi

# ============================================
# Step 1: Check and start Redis
# ============================================
echo "[1/5] Checking Redis service..."

if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "[OK] Redis is already running"
    else
        echo "[STARTING] Starting Redis server..."
        if command -v systemctl &> /dev/null; then
            sudo systemctl start redis &> /dev/null
            if [ $? -eq 0 ]; then
                echo "[OK] Redis started successfully"
            else
                echo "[WARNING] Could not start Redis service"
                echo "Please start Redis manually: sudo systemctl start redis"
            fi
        else
            echo "[WARNING] systemctl not found"
            echo "Please start Redis manually: redis-server &"
        fi
    fi
else
    echo "[WARNING] Redis not found"
    echo "Please install Redis: sudo apt-get install redis-server"
fi

sleep 2

# ============================================
# Step 2: Check and start PostgreSQL
# ============================================
echo ""
echo "[2/5] Checking PostgreSQL service..."

if command -v psql &> /dev/null; then
    if sudo systemctl is-active --quiet postgresql; then
        echo "[OK] PostgreSQL is already running"
    else
        echo "[STARTING] Starting PostgreSQL service..."
        sudo systemctl start postgresql &> /dev/null
        if [ $? -eq 0 ]; then
            echo "[OK] PostgreSQL started successfully"
        else
            echo "[WARNING] Could not start PostgreSQL service"
            echo "Please start PostgreSQL manually: sudo systemctl start postgresql"
        fi
    fi
else
    echo "[WARNING] PostgreSQL not found"
    echo "Please install PostgreSQL: sudo apt-get install postgresql"
fi

sleep 2

# ============================================
# Step 3: Start Celery Worker in background
# ============================================
echo ""
echo "[3/5] Starting Celery Worker..."

# Check if Python is available
if ! command -v python &> /dev/null; then
    if ! command -v python3 &> /dev/null; then
        echo "[ERROR] Python is not installed or not in PATH"
        echo "Please install Python 3.11+"
        exit 1
    else
        PYTHON_CMD=python3
    fi
else
    PYTHON_CMD=python
fi

# Kill existing Celery Worker if running
pkill -f "celery.*worker" &> /dev/null

# Start Celery Worker in background
nohup celery -A app.celery_app worker --loglevel=info > logs/celery_worker.log 2>&1 &
CELERY_WORKER_PID=$!

echo "[OK] Celery Worker started (PID: $CELERY_WORKER_PID)"
echo "    Log: logs/celery_worker.log"

sleep 3

# ============================================
# Step 4: Start Celery Beat in background
# ============================================
echo ""
echo "[4/5] Starting Celery Beat (task scheduler)..."

# Kill existing Celery Beat if running
pkill -f "celery.*beat" &> /dev/null
rm -f celerybeat-schedule.db

# Start Celery Beat in background
nohup $PYTHON_CMD celery_beat.py > logs/celery_beat.log 2>&1 &
CELERY_BEAT_PID=$!

echo "[OK] Celery Beat started (PID: $CELERY_BEAT_PID)"
echo "    Log: logs/celery_beat.log"

sleep 3

# ============================================
# Step 5: Start Bot in background
# ============================================
echo ""
echo "[5/5] Starting NutriAI Bot..."

# Kill existing bot if running
pkill -f "app.bot.main" &> /dev/null

# Start Bot in background
nohup $PYTHON_CMD -m app.bot.main > logs/bot.log 2>&1 &
BOT_PID=$!

echo "[OK] Bot started (PID: $BOT_PID)"
echo "    Log: logs/bot.log"

sleep 2

# ============================================
# Done!
# ============================================
echo ""
echo "============================================"
echo "  NutriAI Bot started successfully!"
echo "============================================"
echo ""
echo "Three processes have been started:"
echo "  1. Celery Worker (PID: $CELERY_WORKER_PID) - background tasks"
echo "  2. Celery Beat (PID: $CELERY_BEAT_PID) - task scheduler"
echo "  3. NutriAI Bot (PID: $BOT_PID) - main application"
echo ""
echo "Logs are available in the logs/ directory:"
echo "  - logs/celery_worker.log"
echo "  - logs/celery_beat.log"
echo "  - logs/bot.log"
echo ""
echo "To stop the bot:"
echo "  - Run: ./stop.sh"
echo "  - Or manually: kill $BOT_PID $CELERY_WORKER_PID $CELERY_BEAT_PID"
echo ""
echo "To view logs in real-time:"
echo "  - tail -f logs/bot.log"
echo "  - tail -f logs/celery_worker.log"
echo "  - tail -f logs/celery_beat.log"
echo ""
echo "Monitoring:"
echo "  - Bot metrics: http://localhost:8000/metrics"
echo "  - Grafana (if running): http://localhost:3000"
echo ""

# Save PIDs to file for stop.sh
echo "$CELERY_WORKER_PID" > .celery_worker.pid
echo "$CELERY_BEAT_PID" > .celery_beat.pid
echo "$BOT_PID" > .bot.pid

echo "Process IDs saved. Use ./stop.sh to stop all services."
echo ""
