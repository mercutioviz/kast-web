"""
kast-web CLI entry point.

Usage:
    kast-web serve   [--host HOST] [--port PORT] [--workers N] [--config FILE]
    kast-web worker  [--loglevel LEVEL] [--concurrency N]
    kast-web dev     [--host HOST] [--port PORT]
    kast-web --version
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def _version():
    try:
        return (Path(__file__).parent / "VERSION").read_text().strip()
    except Exception:
        return "unknown"


def _bin(name):
    """Return the path to an executable in the same venv as this script."""
    return str(Path(sys.executable).parent / name)


def main():
    parser = argparse.ArgumentParser(
        prog="kast-web",
        description="KAST Web — web frontend for the Kali Automated Scan Tool",
    )
    parser.add_argument("--version", action="version", version=f"kast-web {_version()}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # serve — production Gunicorn server
    p_serve = sub.add_parser("serve", help="Start the production Gunicorn server")
    p_serve.add_argument("--host", default="127.0.0.1", metavar="HOST",
                         help="Bind address (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8000, metavar="PORT",
                         help="Bind port (default: 8000)")
    p_serve.add_argument("--workers", type=int, default=4, metavar="N",
                         help="Worker processes (default: 4)")
    p_serve.add_argument("--timeout", type=int, default=120, metavar="SECS",
                         help="Worker timeout in seconds (default: 120)")
    p_serve.add_argument("--config", default=None, metavar="FILE",
                         help="Path to a Gunicorn config file")

    # worker — Celery task worker
    p_worker = sub.add_parser("worker", help="Start the Celery task worker")
    p_worker.add_argument("--loglevel", default="info", metavar="LEVEL",
                          choices=["debug", "info", "warning", "error"],
                          help="Log level (default: info)")
    p_worker.add_argument("--concurrency", type=int, default=None, metavar="N",
                          help="Worker concurrency (default: CPU count)")

    # dev — Flask development server
    p_dev = sub.add_parser("dev", help="Start the Flask development server")
    p_dev.add_argument("--host", default="127.0.0.1", metavar="HOST",
                       help="Bind address (default: 127.0.0.1)")
    p_dev.add_argument("--port", type=int, default=5000, metavar="PORT",
                       help="Bind port (default: 5000)")

    args = parser.parse_args()

    if args.command == "serve":
        cmd = [
            _bin("gunicorn"),
            f"--bind={args.host}:{args.port}",
            f"--workers={args.workers}",
            f"--timeout={args.timeout}",
        ]
        if args.config:
            cmd += ["--config", args.config]
        cmd.append("wsgi:app")
        sys.exit(subprocess.call(cmd))

    elif args.command == "worker":
        cmd = [
            _bin("celery"), "-A", "celery_worker.celery",
            "worker", f"--loglevel={args.loglevel}",
        ]
        if args.concurrency:
            cmd += ["--concurrency", str(args.concurrency)]
        sys.exit(subprocess.call(cmd))

    elif args.command == "dev":
        from dotenv import load_dotenv
        load_dotenv()
        os.environ.setdefault("FLASK_ENV", "development")
        from app import create_app
        app = create_app("development")
        app.run(host=args.host, port=args.port, debug=True)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
