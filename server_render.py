#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  API WEB & SCHEDULER EN NUBE PARA RENDER (OPERATIVAS DIARIAS)
================================================================================
Descripción:
  Servidor FastAPI autónomo para ejecutar y calendarizar todas las tareas
  operativas en Render Cloud sin depender de una PC local encendida.
  
Características:
  1. Scheduler en segundo plano (APScheduler) para ejecución continua 24/7 en la nube.
  2. Endpoints HTTP REST para disparadores manuales / webhooks desde n8n o dashboards.
  3. Soporte multi-entorno: lee credenciales directamente desde GOOGLE_SERVICE_ACCOUNT_JSON.
================================================================================
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False

BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable

app = FastAPI(
    title="Servicio de Operativas Diarias (Render Cloud)",
    description="Motor central de sincronizaciones y calendarización automática de flotas y viajes.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de estados en memoria
EXECUTION_STATE: Dict[str, Any] = {
    "tracking": {"last_run": None, "status": "idle", "duration": 0, "output": ""},
    "vacio": {"last_run": None, "status": "idle", "duration": 0, "output": ""},
    "seguimiento": {"last_run": None, "status": "idle", "duration": 0, "output": ""},
    "dispo": {"last_run": None, "status": "idle", "duration": 0, "output": ""},
    "cordillera": {"last_run": None, "status": "idle", "duration": 0, "output": ""},
    "conf_viaje": {"last_run": None, "status": "idle", "duration": 0, "output": ""},
    "limpiar": {"last_run": None, "status": "idle", "duration": 0, "output": ""},
    "poll_vacio": {"last_run": None, "status": "idle", "duration": 0, "output": ""},
    "all": {"last_run": None, "status": "idle", "duration": 0, "output": ""}
}


def run_command(cmd: list, key: str) -> Dict[str, Any]:
    """Ejecuta un comando capturando la salida y actualizando el estado."""
    t0 = datetime.now()
    EXECUTION_STATE[key]["status"] = "running"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        elapsed = round((datetime.now() - t0).total_seconds(), 2)
        success = (proc.returncode == 0)
        stdout_txt = proc.stdout.strip()
        stderr_txt = proc.stderr.strip()

        result = {
            "task": key,
            "success": success,
            "exit_code": proc.returncode,
            "duration_seconds": elapsed,
            "timestamp": t0.isoformat(),
            "output": stdout_txt if success else (stderr_txt or stdout_txt),
            "errors": stderr_txt if not success else ""
        }
        EXECUTION_STATE[key] = {
            "last_run": t0.isoformat(),
            "status": "success" if success else "failed",
            "duration": elapsed,
            "output": result["output"][:500]
        }
        return result
    except Exception as e:
        elapsed = round((datetime.now() - t0).total_seconds(), 2)
        res_err = {
            "task": key,
            "success": False,
            "exit_code": -1,
            "duration_seconds": elapsed,
            "timestamp": t0.isoformat(),
            "output": "",
            "errors": str(e)
        }
        EXECUTION_STATE[key] = {
            "last_run": t0.isoformat(),
            "status": "error",
            "duration": elapsed,
            "output": str(e)
        }
        return res_err


# ==============================================================================
# ENDPOINTS REST
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
def root_dashboard():
    sched_ok = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
    badge_color = "#10b981" if sched_ok else "#f59e0b"
    badge_text = "ACTIVO 24/7" if sched_ok else "MANUAL"
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Servicio de Operativas Diarias (Render Cloud)</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }}
        .card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            max-width: 600px;
            width: 100%;
            padding: 32px;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
        }}
        h1 {{
            font-size: 1.5rem;
            margin: 0 0 8px 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .badge {{
            display: inline-block;
            background: {badge_color};
            color: #0f172a;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 9999px;
            text-transform: uppercase;
        }}
        p {{
            color: #94a3b8;
            margin: 0 0 24px 0;
            line-height: 1.5;
        }}
        .links {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px;
            margin-top: 24px;
        }}
        .btn {{
            display: block;
            text-align: center;
            text-decoration: none;
            padding: 12px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }}
        .btn-primary {{
            background: #3b82f6;
            color: white;
        }}
        .btn-primary:hover {{
            background: #2563eb;
        }}
        .btn-secondary {{
            background: #334155;
            color: #e2e8f0;
        }}
        .btn-secondary:hover {{
            background: #475569;
        }}
        .tasks-list {{
            background: #0f172a;
            border-radius: 8px;
            padding: 16px;
            font-size: 0.85rem;
            color: #cbd5e1;
            margin-top: 20px;
        }}
        .tasks-list li {{
            margin-bottom: 6px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">● {badge_text}</span>
        <h1 style="margin-top: 12px;">Servicio de Operativas Diarias</h1>
        <p>Motor de sincronización y automatización en la nube (Render Cloud) para planillas operativas, tracking, vacíos y disponibilidades.</p>
        
        <div class="tasks-list">
            <strong>Tareas programadas:</strong>
            <ul style="margin: 8px 0 0 0; padding-left: 20px;">
                <li>Tracking Hover (Col H) — Cada 15 min</li>
                <li>VACÍO (Col X) — Cada 20 min</li>
                <li>Seguimiento Vacío — Cada 15 min</li>
                <li>Viajes Cordillera — Cada 10 min</li>
                <li>Confirmación de Viaje — Cada 10 min</li>
                <li>Disponibilidad VTV — Diario 06:00 AM</li>
            </ul>
        </div>

        <div class="links">
            <a href="/docs" class="btn btn-primary">📖 Swagger UI (/docs)</a>
            <a href="/status" class="btn btn-secondary">📊 Estado (/status)</a>
            <a href="/health" class="btn btn-secondary">🩺 Salud (/health)</a>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "diaria-operativas",
        "scheduler_enabled": os.getenv("ENABLE_SCHEDULER", "true").lower() == "true",
        "has_scheduler_lib": HAS_SCHEDULER,
        "time": datetime.now().isoformat()
    }

@app.get("/status")
def get_status():
    return {
        "time": datetime.now().isoformat(),
        "tasks": EXECUTION_STATE
    }

@app.post("/sync/tracking")
def trigger_tracking(day: Optional[int] = Query(None)):
    args = [PYTHON_EXE, "sync_ruteos_movimientos.py", "--apply"]
    if day:
        args += ["--day", str(day)]
    return run_command(args, "tracking")

@app.post("/sync/vacio")
def trigger_vacio(day: Optional[int] = Query(None)):
    args = [PYTHON_EXE, "sync_vacio.py", "--apply", "--borders"]
    if day:
        args += ["--day", str(day)]
    return run_command(args, "vacio")

@app.post("/sync/poll-vacio")
def trigger_poll_vacio(day: Optional[int] = Query(None), force: bool = Query(False)):
    args = [PYTHON_EXE, "poll_sync_vacio.py", "--apply", "--borders"]
    if day:
        args += ["--day", str(day)]
    if force:
        args.append("--force")
    return run_command(args, "poll_vacio")

@app.post("/sync/seguimiento-vacio")
def trigger_seguimiento_vacio(day: Optional[int] = Query(None)):
    args = [PYTHON_EXE, "sync_seguimiento_vacio.py", "--apply"]
    if day:
        args += ["--day", str(day)]
    return run_command(args, "seguimiento")

@app.post("/sync/dispo")
def trigger_dispo():
    return run_command(["node", "pintarDisponibilidad.js"], "dispo")

@app.post("/sync/cordillera")
def trigger_cordillera():
    return run_command([PYTHON_EXE, "main.py", "--seguridad-vial"], "cordillera")

@app.post("/sync/conf-viaje")
def trigger_conf_viaje():
    return run_command([PYTHON_EXE, "main.py", "--conf-viaje"], "conf_viaje")

@app.post("/sync/limpiar-vacio")
def trigger_limpiar_vacio(day: Optional[int] = Query(None)):
    args = [PYTHON_EXE, "limpiar_vacio.py", "--apply"]
    if day:
        args += ["--day", str(day)]
    return run_command(args, "limpiar")

@app.post("/sync/all")
def trigger_all(day: Optional[int] = Query(None)):
    args = [PYTHON_EXE, "run_all_syncs.py", "--apply", "--module", "all"]
    if day:
        args += ["--day", str(day)]
    return run_command(args, "all")


# ==============================================================================
# SCHEDULER EN SEGUNDO PLANO (APScheduler)
# ==============================================================================

if HAS_SCHEDULER and os.getenv("ENABLE_SCHEDULER", "true").lower() == "true":
    scheduler = BackgroundScheduler(timezone="America/Argentina/Buenos_Aires")

    # 1. Tracking: cada 15m
    scheduler.add_job(
        lambda: run_command([PYTHON_EXE, "sync_ruteos_movimientos.py", "--apply"], "tracking"),
        trigger=IntervalTrigger(minutes=15),
        id="job_tracking",
        replace_existing=True
    )

    # 2. VACIO: cada 20m
    scheduler.add_job(
        lambda: run_command([PYTHON_EXE, "sync_vacio.py", "--apply", "--borders"], "vacio"),
        trigger=IntervalTrigger(minutes=20),
        id="job_vacio",
        replace_existing=True
    )

    # 3. Seguimiento Vacío: cada 15m
    scheduler.add_job(
        lambda: run_command([PYTHON_EXE, "sync_seguimiento_vacio.py", "--apply"], "seguimiento"),
        trigger=IntervalTrigger(minutes=15),
        id="job_seguimiento",
        replace_existing=True
    )

    # 4. Disponibilidad: diario 06:00 AM
    scheduler.add_job(
        lambda: run_command(["node", "pintarDisponibilidad.js"], "dispo"),
        trigger=CronTrigger(hour=6, minute=0),
        id="job_dispo",
        replace_existing=True
    )

    # 5. Cordillera: cada 10m
    scheduler.add_job(
        lambda: run_command([PYTHON_EXE, "main.py", "--seguridad-vial"], "cordillera"),
        trigger=IntervalTrigger(minutes=10),
        id="job_cordillera",
        replace_existing=True
    )

    # 6. CONF. DE VIAJE: cada 10m
    scheduler.add_job(
        lambda: run_command([PYTHON_EXE, "main.py", "--conf-viaje"], "conf_viaje"),
        trigger=IntervalTrigger(minutes=10),
        id="job_conf_viaje",
        replace_existing=True
    )

    scheduler.start()
    print("[SCHEDULER] ✅ APScheduler iniciado con 6 tareas operativas periódicas.")
