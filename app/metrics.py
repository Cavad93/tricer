"""
Prometheus metrics for NutriAI Bot monitoring
"""
from prometheus_client import Counter, Histogram, Gauge, Info
from functools import wraps
import time
import asyncio
from loguru import logger

# === COUNTERS (always increasing) ===

# Total messages received
messages_total = Counter(
    'bot_messages_total',
    'Total number of messages received by the bot',
    ['command', 'user_type']  # Labels: command name, user type (free/premium)
)

# Total errors
errors_total = Counter(
    'bot_errors_total',
    'Total number of errors',
    ['error_type', 'handler']  # Labels: exception type, handler name
)

# Claude API calls
claude_api_calls_total = Counter(
    'claude_api_calls_total',
    'Total Claude API calls',
    ['method', 'status']  # Labels: method name, status (success/failure)
)

# Celery tasks
celery_tasks_total = Counter(
    'celery_tasks_total',
    'Total Celery tasks created',
    ['task_name', 'status']  # Labels: task name, status (pending/started/success/failure)
)

# User registrations
user_registrations_total = Counter(
    'bot_user_registrations_total',
    'Total number of new user registrations'
)

# Meal plans created
meal_plans_created_total = Counter(
    'bot_meal_plans_created_total',
    'Total number of meal plans created',
    ['period_type']  # Labels: day/week/month
)

# === HISTOGRAMS (distribution of values) ===

# Command response time
command_duration_seconds = Histogram(
    'bot_command_duration_seconds',
    'Time spent processing commands',
    ['command'],  # Label: command name
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120]  # Buckets in seconds
)

# Claude API response time
claude_api_duration_seconds = Histogram(
    'claude_api_duration_seconds',
    'Claude API call duration',
    ['method'],  # Label: method name
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60]  # Buckets in seconds
)

# Meal plan generation time
meal_plan_generation_duration_seconds = Histogram(
    'meal_plan_generation_duration_seconds',
    'Meal plan generation duration (full pipeline)',
    buckets=[10, 30, 60, 120, 180, 300]  # Buckets in seconds
)

# Database query time
db_query_duration_seconds = Histogram(
    'bot_db_query_duration_seconds',
    'Database query duration',
    ['operation'],  # Label: select/insert/update/delete
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5]  # Buckets in seconds
)

# === GAUGES (can go up and down) ===

# Active users (currently interacting with bot)
active_users = Gauge(
    'bot_active_users',
    'Number of currently active users'
)

# Concurrent requests being processed
concurrent_requests = Gauge(
    'bot_concurrent_requests',
    'Number of concurrent requests being processed'
)

# Database pool connections
db_pool_connections = Gauge(
    'bot_db_pool_connections',
    'Number of database connections',
    ['state']  # Labels: available/in_use/total
)

# Celery queue size
celery_queue_size = Gauge(
    'celery_queue_size',
    'Number of tasks in Celery queue',
    ['queue_name']  # Label: queue name (default/celery)
)

# Claude API rate limiter
claude_rate_limiter_available = Gauge(
    'claude_rate_limiter_available',
    'Number of available Claude API calls in current window'
)

# === INFO (static labels) ===

# Bot information
bot_info = Info(
    'bot_info',
    'Information about the bot'
)

# Set bot info (call once at startup)
def set_bot_info(version: str = "1.0.0", env: str = "production"):
    """Set static bot information"""
    bot_info.info({
        'version': version,
        'environment': env,
        'name': 'NutriAI'
    })


# === DECORATORS FOR AUTOMATIC TRACKING ===

def track_command(command_name: str, user_type: str = "free"):
    """
    Decorator to track command execution time and count

    Usage:
        @track_command('start')
        async def start_handler(update, context):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Increment message counter
            messages_total.labels(command=command_name, user_type=user_type).inc()

            # Track concurrent requests
            concurrent_requests.inc()

            # Track execution time
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                # Track errors
                errors_total.labels(
                    error_type=type(e).__name__,
                    handler=command_name
                ).inc()
                raise
            finally:
                # Decrement concurrent requests
                concurrent_requests.dec()

                # Record duration
                duration = time.time() - start_time
                command_duration_seconds.labels(command=command_name).observe(duration)

        return wrapper
    return decorator


def track_api_call(method_name: str):
    """
    Decorator to track Claude API calls

    Usage:
        @track_api_call('analyze_food_photo')
        async def analyze_food_photo(self, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                # Success
                claude_api_calls_total.labels(
                    method=method_name,
                    status='success'
                ).inc()
                return result
            except Exception as e:
                # Failure
                claude_api_calls_total.labels(
                    method=method_name,
                    status='failure'
                ).inc()
                raise
            finally:
                # Record duration
                duration = time.time() - start_time
                claude_api_duration_seconds.labels(method=method_name).observe(duration)

        return wrapper
    return decorator


def track_db_operation(operation: str):
    """
    Decorator to track database operations

    Usage:
        @track_db_operation('select')
        async def get_user(user_id):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                db_query_duration_seconds.labels(operation=operation).observe(duration)

        return wrapper
    return decorator


# === HELPER FUNCTIONS ===

def update_db_pool_metrics(pool):
    """
    Update database pool metrics

    Call this periodically (every 15-30 seconds) to update gauge metrics
    """
    try:
        if hasattr(pool, 'size') and hasattr(pool, 'checkedout'):
            total = pool.size()
            in_use = pool.checkedout()
            available = total - in_use

            db_pool_connections.labels(state='total').set(total)
            db_pool_connections.labels(state='in_use').set(in_use)
            db_pool_connections.labels(state='available').set(available)
    except Exception as e:
        logger.error(f"Error updating DB pool metrics: {e}")


def update_celery_queue_metrics(app):
    """
    Update Celery queue metrics

    Call this periodically to update gauge metrics
    """
    try:
        # Use Celery 5.x compatible import
        if app is None:
            celery_queue_size.labels(queue_name='default').set(0)
            return

        i = app.control.inspect()

        # Get reserved tasks (tasks in queue)
        reserved = i.reserved()
        if reserved:
            queue_size = sum(len(tasks) for tasks in reserved.values())
            celery_queue_size.labels(queue_name='default').set(queue_size)
        else:
            celery_queue_size.labels(queue_name='default').set(0)
    except Exception as e:
        logger.error(f"Error updating Celery queue metrics: {e}")
        # Set to 0 on error to avoid missing metric
        celery_queue_size.labels(queue_name='default').set(0)


def track_meal_plan_created(period_type: str):
    """
    Track meal plan creation

    Usage:
        track_meal_plan_created('week')
    """
    meal_plans_created_total.labels(period_type=period_type).inc()


def track_user_registration():
    """
    Track new user registration

    Usage:
        track_user_registration()
    """
    user_registrations_total.inc()


# === METRICS UPDATER (background task) ===

class MetricsUpdater:
    """
    Background task to update gauge metrics periodically
    """

    def __init__(self, db_pool=None, celery_app=None, update_interval=15):
        """
        Args:
            db_pool: SQLAlchemy pool object
            celery_app: Celery application
            update_interval: Update interval in seconds
        """
        self.db_pool = db_pool
        self.celery_app = celery_app
        self.update_interval = update_interval
        self.running = False
        self.task = None

    async def start(self):
        """Start the metrics updater"""
        if self.running:
            logger.warning("Metrics updater already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._update_loop())
        logger.info(f"Metrics updater started (interval: {self.update_interval}s)")

    async def stop(self):
        """Stop the metrics updater"""
        if not self.running:
            logger.debug("Metrics updater already stopped or not running")
            return

        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.debug("Metrics updater task cancelled successfully")
            except Exception as e:
                logger.error(f"Error while stopping metrics updater: {e}")
        logger.info("Metrics updater stopped")

    async def _update_loop(self):
        """Main update loop"""
        while self.running:
            try:
                # Update DB pool metrics
                if self.db_pool:
                    update_db_pool_metrics(self.db_pool)

                # Update Celery queue metrics
                if self.celery_app:
                    update_celery_queue_metrics(self.celery_app)

                # Sleep until next update
                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics updater: {e}")
                await asyncio.sleep(self.update_interval)
