from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import traceback

from .config import APP_DIR


def user_data_dir() -> Path:
    return APP_DIR


def app_log(level: str, message: str, **context) -> None:
    """Schreibt ein lokales App-Log ohne sensible Daten."""
    try:
        log_dir = user_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        safe_context = {k: v for k, v in context.items() if k.lower() not in {"password", "token", "api_token", "authorization"}}
        line = f"{datetime.now().isoformat(timespec='seconds')} [{level.upper()}] {message}"
        if safe_context:
            line += " | " + "; ".join(f"{k}={v}" for k, v in safe_context.items())
        with (log_dir / "app.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def app_log_exception(message: str, exc: BaseException | None = None, **context) -> None:
    if exc is not None:
        context["error"] = str(exc)
        context["error_type"] = type(exc).__name__
    app_log("error", message, **context)
    try:
        log_dir = user_data_dir() / "logs"
        with (log_dir / "app_trace.log").open("a", encoding="utf-8") as fh:
            fh.write(f"\n{datetime.now().isoformat(timespec='seconds')} {message}\n")
            if exc is not None:
                fh.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass
