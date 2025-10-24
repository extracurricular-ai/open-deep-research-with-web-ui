# Gunicorn configuration file for production deployment

import multiprocessing

# Server socket
bind = "0.0.0.0:5080"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 0  # Disable timeout for long-running agent tasks (tasks can run indefinitely)
keepalive = 2
graceful_timeout = 30  # Give workers 30s to finish when shutting down

# Process naming
proc_name = "open_deep_research"

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment and configure for HTTPS)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print("Gunicorn server starting...")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    print("Gunicorn reloading...")

def when_ready(server):
    """Called just after the server is started."""
    print(f"Gunicorn ready. Workers: {workers}, Bind: {bind}")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"Worker spawned (pid: {worker.pid})")

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    print(f"Worker exited (pid: {worker.pid})")
