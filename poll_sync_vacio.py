#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  POLLING INTELIGENTE Y SINCRONIZADOR DE VACÍO (FASE 1: GATEKEEPER + FASE 2: MERGE)
================================================================================
Descripción:
  Monitorea de forma ultraliviana la Columna X (VACÍO) y la Columna L (TDs) en 'Ruteos',
  así como las columnas del día en 'OCTUBRE 2026- Mov.Unidades y Choferes'.
  
  Fase 1 (Gatekeeper):
    - Lee únicamente los rangos críticos mediante una sola llamada batchGet.
    - Genera una firma criptográfica (SHA-256) del estado actual.
    - Si el hash es IDÉNTICO al de la última ejecución, aborta en ~3 segundos
      evitando lecturas pesadas, consumo de CPU y escrituras innecesarias.
      
  Fase 2 (Merge y Sincronización):
    - Si se detecta un cambio (nuevo dato de vacío, nuevo TD en Ruteos o cambio en Movimientos),
      dispara el chequeo completo con MERGE VIRTUAL de TD y Patente:
        1. Tarea 2: Sincronización de VACÍO (Col X) en Hover + Bordes dobles.
        2. Tarea 3: Seguimiento de Vacío (#9fc5e8 / sin TD nuevo) + Limpieza automática.
    - Actualiza el archivo de estado 'last_poll_state.json'.
================================================================================
"""

import os
import sys
import json
import time
import hashlib
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List

# Configurar salida UTF-8 para consola de Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from googleapiclient.discovery import build
from credentials_helper import get_google_credentials, resolve_credentials_file
from sync_seguimiento_vacio import get_day_column_indices, index_to_col_letter

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "last_poll_state.json"
PYTHON_EXE = sys.executable

DEFAULT_RUTEOS_ID = "1-wNLgr2b1TibP_MPwA9ToF9jlH_jiPxjN0iirWbFb3o"
DEFAULT_MOV_ID = "14Mb5rD853zxDkaLDS-IrW-OBDTDBjuJxn_3olXeWlkc"
SOURCE_TAB_RUTEOS = "Ruteos"
TARGET_TAB_MOV = "OCTUBRE 2026- Mov.Unidades y Choferes"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


class VacioPoller:
    def __init__(
        self,
        ruteos_id: str = DEFAULT_RUTEOS_ID,
        mov_id: str = DEFAULT_MOV_ID,
        day: Optional[int] = None
    ):
        self.ruteos_id = ruteos_id
        self.mov_id = mov_id
        self.day_explicit = (day is not None)
        self.day = day or datetime.now().day
        self._creds = get_google_credentials(scopes=SCOPES)
        self._service = build("sheets", "v4", credentials=self._creds)

    def load_previous_state(self) -> Dict[str, Any]:
        """Carga el último estado registrado desde el archivo JSON local."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] No se pudo leer {STATE_FILE.name}: {e}")
        return {}

    def save_state(self, state: Dict[str, Any]) -> None:
        """Persiste el nuevo estado detectado en disco."""
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARN] Error guardando estado en {STATE_FILE.name}: {e}")

    def fetch_fingerprint(self) -> Tuple[str, Dict[str, Any]]:
        """
        Fase 1: Lee únicamente las columnas indispensables para detectar cambios.
        Retorna (hash_sha256, metadata_resumen).
        """
        t0 = time.time()

        # 1. Rangos de Ruteos: TDs (Col L) y Vacíos (Col X)
        ruteos_ranges = [
            f"'{SOURCE_TAB_RUTEOS}'!L4:L",
            f"'{SOURCE_TAB_RUTEOS}'!X4:X"
        ]

        # 2. Rangos de Movimientos para el día activo (Chofer, Dispo, Date)
        col_ch, col_disp, col_dt = get_day_column_indices(self.day)
        let_ch = index_to_col_letter(col_ch)
        let_dt = index_to_col_letter(col_dt)
        mov_range = f"'{TARGET_TAB_MOV}'!{let_ch}3:{let_dt}350"

        # Consulta combinada a Ruteos (1 sola petición HTTP)
        res_ruteos = self._service.spreadsheets().values().batchGet(
            spreadsheetId=self.ruteos_id,
            ranges=ruteos_ranges,
            valueRenderOption="FORMATTED_VALUE"
        ).execute()

        # Consulta combinada a Movimientos (1 sola petición HTTP)
        res_mov = self._service.spreadsheets().values().get(
            spreadsheetId=self.mov_id,
            range=mov_range,
            valueRenderOption="FORMATTED_VALUE"
        ).execute()

        elapsed_read = round(time.time() - t0, 2)

        val_ranges = res_ruteos.get("valueRanges", [])
        raw_tds = val_ranges[0].get("values", []) if len(val_ranges) > 0 else []
        raw_x = val_ranges[1].get("values", []) if len(val_ranges) > 1 else []
        raw_mov = res_mov.get("values", [])

        # Filtrar valores significativos de Columna X (Vacío)
        vacio_items = []
        for idx, row in enumerate(raw_x):
            val = row[0].strip() if row and row[0] else ""
            if val and val != "#N/A":
                vacio_items.append({"row": idx + 4, "val": val})

        # Muestra de los últimos 150 TDs en Ruteos para detectar nuevas filas operativas
        td_tail = []
        for idx, row in enumerate(raw_tds[-150:], start=max(4, len(raw_tds) - 146)):
            val = row[0].strip() if row and row[0] else ""
            if val:
                td_tail.append({"row": idx, "td": val})

        # Matriz simplificada del día en Movimientos
        mov_items = []
        for idx, row in enumerate(raw_mov):
            row_num = idx + 3
            cells = [c.strip() for c in row if c and c.strip()]
            if cells:
                mov_items.append({"row": row_num, "cells": cells})

        payload = {
            "day": self.day,
            "vacio_count": len(vacio_items),
            "vacio_items": vacio_items,
            "total_td_rows": len(raw_tds),
            "td_tail": td_tail,
            "mov_items": mov_items
        }

        raw_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        current_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

        metadata = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_check_sec": elapsed_read,
            "hash": current_hash,
            "day": self.day,
            "vacio_count": len(vacio_items),
            "total_td_rows": len(raw_tds),
            "mov_active_rows": len(mov_items),
            "sample_last_vacio": vacio_items[-3:] if vacio_items else []
        }

        return current_hash, metadata

    def run_sync_tasks(
        self,
        apply: bool = False,
        borders: bool = True,
        tasks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fase 2: Ejecuta los procesos completos de Merge y Sincronización.
        """
        if tasks is None:
            tasks = ["vacio", "seguimiento"]

        results = {}
        t_start = time.time()

        print("\n" + "="*80)
        print(f"  FASE 2: EJECUTANDO SINCRONIZACIÓN COMPLETA (MERGE TD Y PATENTE)")
        print(f"  Modo: {'APLICAR CAMBIOS (--apply)' if apply else 'SIMULACIÓN (dry-run)'}")
        print(f"  Día objetivo: {self.day}")
        print(f"  Tareas a ejecutar: {', '.join(tasks)}")
        print("="*80)

        # 1. Tarea 2: sync_vacio.py
        if "vacio" in tasks:
            print("\n[FASE 2.1] 🚀 Ejecutando Tarea 2: Sincronización de VACÍO (Col X) + Notas Hover...")
            cmd_vacio = [PYTHON_EXE, "sync_vacio.py"]
            if self.day_explicit:
                cmd_vacio.extend(["--day", str(self.day)])
            if apply:
                cmd_vacio.append("--apply")
            if borders:
                cmd_vacio.append("--borders")

            p_v = subprocess.run(
                cmd_vacio,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            print(p_v.stdout.strip())
            if p_v.stderr.strip():
                print(f"[STDERR]\n{p_v.stderr.strip()}")
            results["vacio"] = {
                "success": (p_v.returncode == 0),
                "exit_code": p_v.returncode
            }

        # 2. Tarea 3: sync_seguimiento_vacio.py
        if "seguimiento" in tasks:
            print("\n[FASE 2.2] 🚀 Ejecutando Tarea 3: Seguimiento de Vacío (#9fc5e8 / sin nuevo TD)...")
            cmd_seg = [PYTHON_EXE, "sync_seguimiento_vacio.py", "--day", str(self.day)]
            if apply:
                cmd_seg.append("--apply")

            p_s = subprocess.run(
                cmd_seg,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            print(p_s.stdout.strip())
            if p_s.stderr.strip():
                print(f"[STDERR]\n{p_s.stderr.strip()}")
            results["seguimiento"] = {
                "success": (p_s.returncode == 0),
                "exit_code": p_s.returncode
            }

        # 3. Tarea 1: sync_ruteos_movimientos.py (Opcional si se especifica)
        if "tracking" in tasks:
            print("\n[FASE 2.3] 🚀 Ejecutando Tarea 1: Tracking Hover (Col H)...")
            cmd_trk = [PYTHON_EXE, "sync_ruteos_movimientos.py"]
            if self.day_explicit:
                cmd_trk.extend(["--day", str(self.day)])
            if apply:
                cmd_trk.append("--apply")

            p_t = subprocess.run(
                cmd_trk,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            print(p_t.stdout.strip())
            results["tracking"] = {
                "success": (p_t.returncode == 0),
                "exit_code": p_t.returncode
            }

        total_elapsed = round(time.time() - t_start, 2)
        results["total_duration_sec"] = total_elapsed
        print("\n" + "="*80)
        print(f"  FASE 2 COMPLETADA EN {total_elapsed}s")
        print("="*80)

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Polling Inteligente de VACÍO con detección rápida (Gatekeeper) y merge completo."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios reales en Google Sheets. Si se omite, corre en modo simulación."
    )
    parser.add_argument(
        "--borders",
        action="store_true",
        default=True,
        help="Aplica bordes dobles a celdas con VACÍO (por defecto activo)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fuerza la ejecución completa de la Fase 2 ignorando el checksum anterior."
    )
    parser.add_argument(
        "--day",
        type=int,
        default=None,
        help="Día del mes de octubre (por defecto toma el día actual)."
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Solo realiza la verificación de cambios (Fase 1) sin ejecutar tareas."
    )
    parser.add_argument(
        "--tasks",
        type=str,
        default="vacio,seguimiento",
        help="Tareas separadas por comas a ejecutar ante cambios: vacio,seguimiento,tracking,all (default: vacio,seguimiento)."
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Modo continuo / daemon: ejecuta el poller cada N segundos indefinidamente."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Intervalo en segundos para el modo --watch (por defecto 60s)."
    )

    args = parser.parse_args()

    selected_tasks = [t.strip() for t in args.tasks.split(",")]
    if "all" in selected_tasks:
        selected_tasks = ["vacio", "seguimiento", "tracking"]

    poller = VacioPoller(day=args.day)

    def execute_single_poll() -> int:
        prev_state = poller.load_previous_state()
        prev_hash = prev_state.get("hash")

        print(f"[{datetime.now().strftime('%H:%M:%S')}] [FASE 1] Verificando cambios en Ruteos y Movimientos (Día {poller.day})...")
        current_hash, meta = poller.fetch_fingerprint()

        print(f"      - Verificación completada en: {meta['elapsed_check_sec']}s")
        print(f"      - Entradas activas en Col X:   {meta['vacio_count']}")
        print(f"      - Filas totales con TD:       {meta['total_td_rows']}")
        print(f"      - Hash actual:                {current_hash[:12]}...")

        has_changed = (current_hash != prev_hash) or args.force

        if not has_changed:
            print(f"⚡ [GATEKEEPER] Sin cambios detectados. Omitiendo sincronización pesada.")
            print(f"   (Tiempo total invertido: ~{meta['elapsed_check_sec']}s | Peticiones API: 2 lecturas | 0 escrituras)")
            return 0

        print(f"\n🔔 [CAMBIO DETECTADO] Estado modificado o ejecución forzada. Procediendo a Fase 2...")
        if args.check_only:
            print("Modo --check-only activo. No se dispararán las tareas.")
            return 1

        # Ejecutar Fase 2
        results = poller.run_sync_tasks(
            apply=args.apply,
            borders=args.borders,
            tasks=selected_tasks
        )

        # Actualizar estado guardado
        meta["last_run_results"] = results
        poller.save_state(meta)
        print(f"💾 Estado actualizado exitosamente en {STATE_FILE.name}")
        return 0

    if args.watch:
        print(f"[*] Modo continuo (--watch) activo. Consultando cada {args.interval} segundos...")
        try:
            while True:
                execute_single_poll()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[!] Modo continuo finalizado por el usuario.")
            return 0
    else:
        sys.exit(execute_single_poll())


if __name__ == "__main__":
    main()
