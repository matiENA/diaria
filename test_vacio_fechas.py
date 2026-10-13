#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_vacio_fechas.py
Pruebas unitarias para validar las reglas de Columna X, composición de notas
y el motor unificado de capas.
"""

import unittest
from sync_operativas_unificadas import (
    format_vacio_datetime,
    compose_final_note,
    clean_destino,
    format_tracking_text,
    is_dispo_excluded,
    is_chofer_excluded
)


class TestVacioFechasYCapas(unittest.TestCase):

    def test_format_vacio_dates_without_time(self):
        """Verifica que las fechas puras de Col X no se descarten y generen 'VACIO d/m hs'."""
        self.assertEqual(format_vacio_datetime("08/10/2026"), "VACIO 8/10 hs")
        self.assertEqual(format_vacio_datetime("09/10/2026"), "VACIO 9/10 hs")
        self.assertEqual(format_vacio_datetime("10/10/2026"), "VACIO 10/10 hs")
        self.assertEqual(format_vacio_datetime("8/10/26"), "VACIO 8/10 hs")
        self.assertEqual(format_vacio_datetime("8/10"), "VACIO 8/10 hs")

    def test_format_vacio_midnight_format(self):
        """Verifica que fechas con medianoche 0:00 no se descarten."""
        self.assertEqual(format_vacio_datetime("08/10/2026 0:00"), "VACIO 8/10 hs")
        self.assertEqual(format_vacio_datetime("09/10/2026 0:00"), "VACIO 9/10 hs")
        self.assertEqual(format_vacio_datetime("10/10/2026 0:00:00"), "VACIO 10/10 hs")

    def test_format_vacio_with_explicit_time(self):
        """Verifica que fechas con hora se formateen con hora y minutos."""
        self.assertEqual(format_vacio_datetime("4/10/2026 8:10:00"), "VACIO 4/10 8:10 hs")
        self.assertEqual(format_vacio_datetime("01/10/2026 12:15"), "VACIO 1/10 12:15 hs")
        self.assertEqual(format_vacio_datetime("5/10/26 23 HS"), "VACIO 5/10 23:00 hs")
        self.assertEqual(format_vacio_datetime("7/10 23:40"), "VACIO 7/10 23:40 hs")
        self.assertEqual(format_vacio_datetime("VACIO"), "VACIO")

    def test_format_vacio_exclusions(self):
        """Verifica que valores falsos o no vacíos se descarten."""
        for val in ["FALSE", "TRUE", "#N/A", "TLC", "TPH", "NO", "", None]:
            self.assertEqual(format_vacio_datetime(val), "", f"Fallo descartando: {val}")

    def test_compose_final_note_layering(self):
        """
        Verifica que VACÍO vaya en la primera línea si existe en Col X,
        y que Col H permanezca debajo como tracking puro.
        """
        vacio_header = "VACIO 9/10 hs"
        tracking_body = "31349 - RIO NEUQUEN COMBUSTIBLES S.A.\n/14HS VACIO /8HS CAMINO AÑELO"

        res = compose_final_note(vacio_header, tracking_body)
        expected = "VACIO 9/10 hs\n31349 - RIO NEUQUEN COMBUSTIBLES S.A.\n/14HS VACIO /8HS CAMINO AÑELO"
        self.assertEqual(res, expected)

    def test_compose_final_note_without_col_x(self):
        """
        Si Col X no tiene vacío, la nota debe contener únicamente el tracking de Col H,
        sin inventar cabecera de VACÍO aunque Col H tenga texto con la palabra vacio.
        """
        vacio_header = ""
        tracking_body = "/14HS VACIO /8HS CAMINO AÑELO"

        res = compose_final_note(vacio_header, tracking_body)
        self.assertEqual(res, "/14HS VACIO /8HS CAMINO AÑELO")

    def test_dispo_exclusions(self):
        """Verifica que las localidades y estados no operativos en Dispo se identifiquen correctamente."""
        self.assertTrue(is_dispo_excluded("TLC-cm"))
        self.assertTrue(is_dispo_excluded("dock sud"))
        self.assertTrue(is_dispo_excluded("tds"))
        self.assertTrue(is_dispo_excluded("TLC"))
        self.assertTrue(is_dispo_excluded("PP"))
        self.assertTrue(is_dispo_excluded("No Disponible"))
        self.assertTrue(is_dispo_excluded("Mantenimiento"))
        self.assertTrue(is_dispo_excluded("Reparación"))
        self.assertTrue(is_dispo_excluded("ND"))
        self.assertFalse(is_dispo_excluded("en viaje CM"))
        self.assertFalse(is_dispo_excluded("Disponible"))
        self.assertFalse(is_dispo_excluded(""))
        self.assertFalse(is_dispo_excluded(None))

    def test_parse_day_from_cell_month_filtering(self):
        """Verifica que parse_day_from_cell filtre correctamente por mes objetivo."""
        from sync_operativas_unificadas import parse_day_from_cell
        # Strings con formato d/m/yyyy
        self.assertEqual(parse_day_from_cell("13/10/2026", expected_month=10), 13)
        self.assertEqual(parse_day_from_cell("28/09/2026", expected_month=10), None)
        self.assertEqual(parse_day_from_cell("28/09/2026", expected_month=9), 28)
        # Strings con formato d/m
        self.assertEqual(parse_day_from_cell("12/10", expected_month=10), 12)
        self.assertEqual(parse_day_from_cell("12/9", expected_month=10), None)

    def test_standby_unit_qualifies_without_trips_in_ruteos(self):
        """
        Verifica que unidades sin ningún viaje en Ruteos (como AG426OA fila 10)
        califiquen para pintado celeste si tienen chofer asignado y Dispo válida.
        """
        from sync_operativas_unificadas import is_default_or_unpainted_bg

        trk = "AG426OA"
        tractor_all_trips = {}  # 0 viajes en Ruteos
        tractors_vacio_sin_nuevo_td = {}

        # 1. Caso Fila 10 Día 13: Chofer asignado, Dispo vacía/None, celda vacía -> CALIFICA
        chofer_val = "GUTIERREZ SANHUEZA MARCELO ANDRES"
        dispo_val = ""
        cell_s1 = {"value": "", "note": "7:42 UTE", "bg": None}
        current_bg = cell_s1["bg"]

        tiene_chofer = bool(chofer_val and chofer_val.strip() and not is_chofer_excluded(chofer_val))
        dispo_valida = not is_dispo_excluded(dispo_val)
        slot1_vacio = not cell_s1["value"]
        bg_elegible = is_default_or_unpainted_bg(current_bg)

        es_vacio_reciente = (trk in tractors_vacio_sin_nuevo_td)
        es_standby_disponible = (trk not in tractor_all_trips) and tiene_chofer
        chofer_ok = (not is_chofer_excluded(chofer_val)) if es_vacio_reciente else tiene_chofer

        qualifies_day13 = (
            (es_vacio_reciente or es_standby_disponible)
            and chofer_ok
            and dispo_valida
            and slot1_vacio
            and bg_elegible
        )
        self.assertTrue(qualifies_day13, "AG426OA debió calificar en día 13")

        # 2. Caso Fila 10 Día 11: Chofer '1' y Dispo 'No Disponible' -> NO CALIFICA
        chofer_d11 = "1"
        dispo_d11 = "No Disponible"
        tiene_chofer_d11 = bool(chofer_d11 and chofer_d11.strip() and not is_chofer_excluded(chofer_d11))
        dispo_valida_d11 = not is_dispo_excluded(dispo_d11)
        es_standby_d11 = (trk not in tractor_all_trips) and tiene_chofer_d11
        qualifies_day11 = (
            (es_vacio_reciente or es_standby_d11)
            and tiene_chofer_d11
            and dispo_valida_d11
            and slot1_vacio
            and bg_elegible
        )
        self.assertFalse(qualifies_day11, "AG426OA NO debió calificar en día 11")

        # 3. Caso unidad sin chofer asignado (chofer vacío) -> NO CALIFICA
        chofer_vacio = ""
        tiene_chofer_vacio = bool(chofer_vacio and chofer_vacio.strip() and not is_chofer_excluded(chofer_vacio))
        es_standby_vacio = (trk not in tractor_all_trips) and tiene_chofer_vacio
        self.assertFalse(es_standby_vacio, "Unidad sin chofer no debe calificar como standby")

    def test_execution_shield_mutual_exclusion(self):
        """Verifica que ExecutionShield impida dos ejecuciones concurrentes."""
        from execution_shield import ExecutionShield, ShieldBlockedException, LOCK_FILE
        # Asegurar limpieza previa
        LOCK_FILE.unlink(missing_ok=True)

        with ExecutionShield("Test1"):
            self.assertTrue(LOCK_FILE.exists())
            # Un segundo intento debe detectar el bloqueo
            second_shield_blocked = False
            try:
                with ExecutionShield("Test2"):
                    pass
            except ShieldBlockedException:
                second_shield_blocked = True
            self.assertTrue(second_shield_blocked, "El segundo escudo debió ser bloqueado por el primero")

    def test_ignore_hold_annotation_without_td(self):
        """Verifica que filas en hold sin TD numérico no anulen el vacío del último viaje legítimo."""
        # Simulación de filas estilo Ruteos
        mock_ruteos = [
            # Fila 4354: Viaje real con TD y Vacío
            ["AD355XA"] + [""] * 10 + ["1298875"] + [""] * 11 + ["11/10/2026 12:06"],
            # Fila 4847: Anotación en hold por operarios (sin TD, sin Vacío)
            ["AD355XA"] + [""] * 10 + [""] + [""] * 11 + [""]
        ]

        tractor_all_trips = {}
        for r in mock_ruteos:
            trk = r[0]
            td = str(r[11]).strip()
            # Filtro canónico por TD numérico
            if not td or not td.isdigit():
                continue
            vac = format_vacio_datetime(r[23])
            if trk not in tractor_all_trips:
                tractor_all_trips[trk] = []
            tractor_all_trips[trk].append({"td": td, "has_vacio": bool(vac), "vacio_header": vac})

        self.assertIn("AD355XA", tractor_all_trips)
        self.assertEqual(len(tractor_all_trips["AD355XA"]), 1)
        last_trip = tractor_all_trips["AD355XA"][-1]
        self.assertEqual(last_trip["td"], "1298875")
        self.assertTrue(last_trip["has_vacio"])
        self.assertEqual(last_trip["vacio_header"], "VACIO 11/10 12:06 hs")


if __name__ == "__main__":
    unittest.main()
