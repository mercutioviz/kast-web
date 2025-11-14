"""
Gunicorn Configuration File for KAST Web
Production-ready settings for running Flask app with Gunicorn
"""

import multiprocessing
import os

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Process naming
proc_name = "kast-web"

# Logging
accesslog = "/var/log/kast-web/access.log"
errorlog = "/var/log/kast-web/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process management
daemon = False
pidfile = "/var/run/kast-web/gunicorn.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# Server mechanics
preload_app = True
sendfile = True
reuse_port = True

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    pass

def when_ready(server):
    """Called just after the server is started."""
    pass

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    pass

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    pass

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    pass

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    pass

def pre_exec(server):
    """Called just before a new master process is forked."""
    pass

def pre_request(worker, req):
    """Called just before a worker processes the request."""
    worker.log.debug("%s %s" % (req.method, req.path))

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    pass

def child_exit(server, worker):
    """Called just after a worker has been exited."""
    pass

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    pass

def nworkers_changed(server, new_value, old_value):
    """Called just after num_workers has been changed."""
    pass

def on_exit(server):
    """Called just before exiting Gunicorn."""
    pass
