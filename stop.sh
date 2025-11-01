#!/bin/bash
# ============================================
# NutriAI Bot - Stop Script for Linux
# ============================================
# This script stops all running NutriAI services
# ============================================

echo ""
echo "============================================"
echo "  Stopping NutriAI Bot..."
echo "============================================"
echo ""

STOPPED=0

# Stop Bot
if [ -f ".bot.pid" ]; then
    BOT_PID=$(cat .bot.pid)
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo "[STOPPING] NutriAI Bot (PID: $BOT_PID)..."
        kill $BOT_PID
        sleep 2
        if ps -p $BOT_PID > /dev/null 2>&1; then
            echo "[WARNING] Process didn't stop gracefully, forcing..."
            kill -9 $BOT_PID
        fi
        echo "[OK] Bot stopped"
        STOPPED=$((STOPPED + 1))
    fi
    rm -f .bot.pid
else
    echo "[INFO] No Bot PID file found, trying to find process..."
    pkill -f "app.bot.main"
    if [ $? -eq 0 ]; then
        echo "[OK] Bot process killed"
        STOPPED=$((STOPPED + 1))
    fi
fi

# Stop Celery Worker
if [ -f ".celery_worker.pid" ]; then
    WORKER_PID=$(cat .celery_worker.pid)
    if ps -p $WORKER_PID > /dev/null 2>&1; then
        echo "[STOPPING] Celery Worker (PID: $WORKER_PID)..."
        kill $WORKER_PID
        sleep 2
        if ps -p $WORKER_PID > /dev/null 2>&1; then
            echo "[WARNING] Process didn't stop gracefully, forcing..."
            kill -9 $WORKER_PID
        fi
        echo "[OK] Celery Worker stopped"
        STOPPED=$((STOPPED + 1))
    fi
    rm -f .celery_worker.pid
else
    echo "[INFO] No Celery Worker PID file found, trying to find process..."
    pkill -f "celery.*worker"
    if [ $? -eq 0 ]; then
        echo "[OK] Celery Worker process killed"
        STOPPED=$((STOPPED + 1))
    fi
fi

# Stop Celery Beat
if [ -f ".celery_beat.pid" ]; then
    BEAT_PID=$(cat .celery_beat.pid)
    if ps -p $BEAT_PID > /dev/null 2>&1; then
        echo "[STOPPING] Celery Beat (PID: $BEAT_PID)..."
        kill $BEAT_PID
        sleep 2
        if ps -p $BEAT_PID > /dev/null 2>&1; then
            echo "[WARNING] Process didn't stop gracefully, forcing..."
            kill -9 $BEAT_PID
        fi
        echo "[OK] Celery Beat stopped"
        STOPPED=$((STOPPED + 1))
    fi
    rm -f .celery_beat.pid
else
    echo "[INFO] No Celery Beat PID file found, trying to find process..."
    pkill -f "celery.*beat"
    if [ $? -eq 0 ]; then
        echo "[OK] Celery Beat process killed"
        STOPPED=$((STOPPED + 1))
    fi
fi

# Clean up Celery Beat schedule
if [ -f "celerybeat-schedule.db" ]; then
    rm -f celerybeat-schedule.db
    echo "[OK] Celery Beat schedule cleaned up"
fi

echo ""
echo "============================================"
if [ $STOPPED -gt 0 ]; then
    echo "  Stopped $STOPPED service(s)"
else
    echo "  No running services found"
fi
echo "============================================"
echo ""
