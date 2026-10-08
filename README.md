# 🚀 Central Operativa Diaria (Flotas, Ruteos & Cordillera)

Repositorio centralizado que consolida todas las sincronizaciones, automatizaciones y workflows operativos en una única ubicación autónoma:
`C:\Users\Matias Rodriguez\Documents\diaria`

Diseñado para funcionar **100% independiente** tanto en el entorno local (Windows) como en la nube (**Render Cloud**) sin depender de una PC encendida.

---

## 📋 Módulos Operativos Integrados

| # | Tarea / Módulo | Script Principal | Periodicidad Cron | Disparador Manual | Destino en Google Sheets |
|---|---|---|---|---|---|
| **1** | **Tracking Hover (Col H)** | `sync_ruteos_movimientos.py` | Cada 15m | Individual + Maestro | `OCTUBRE 2026- Mov.Unidades y Choferes` (Notas en Hover) |
| **2** | **VACÍO con Bordes (Col X)** | `sync_vacio.py` | Cada 20m | Individual + Maestro | `OCTUBRE 2026- Mov.Unidades y Choferes` (Borde doble `SOLID_MEDIUM`) |
| **3** | **Seguimiento Vacío (#9fc5e8)** | `sync_seguimiento_vacio.py` | Cada 15m | Individual + Maestro | `OCTUBRE 2026- Mov.Unidades y Choferes` (Fondo celeste `#9fc5e8` + cleanup) |
| **4** | **Disponibilidad VTV** | `pintarDisponibilidad.js` | Diario 06:00 | Individual + Maestro | `OCTUBRE 2026- Mov.Unidades y Choferes` (Semáforo 33 cols Dispo) |
| **5** | **Viajes Cordillera** | `main.py --seguridad-vial` | Cada 10m | Individual + Maestro | `SEGURIDA VIAL` (Filtro 21 localidades cordilleranas por TD) |
| **6** | **CONF. DE VIAJE** | `main.py --conf-viaje` | Cada 10m | Individual + Maestro | `CONF. DE VIAJE` (Col W 'sujeto a seguimiento' por TD) |
| **7** | **Limpieza VACÍO (Fix)** | `limpiar_vacio.py` | Manual | Individual Exclusivo | `OCTUBRE 2026- Mov.Unidades y Choferes` (Reset de notas/bordes) |

---

## 🌐 n8n: Workflow Unificado Oficial

El workflow unificado se encuentra en:
📁 [`n8n_workflow_integrado_operativas.json`](./n8n_workflow_integrado_operativas.json)

### Características del Lienzo:
1. **🚀 Disparador Maestro (Ejecutar Todo):** Dispara en simultáneo las tareas 1 a 6 operativas con un solo clic.
2. **Disparadores Manuales Individuales:** Cada tarea posee su propio botón manual aislado para pruebas y forzados específicos.
3. **Programación Automática (Cron Triggers):** Frecuencias configuradas independientemente por carril.
4. **Seguridad en Limpieza:** La Tarea 7 (Limpieza) está desacoplada del disparador maestro y de los cron automáticos para evitar borrados accidentales no supervisados.
5. **Actualizado en la Base Local:** El flujo ya fue actualizado e inyectado directamente en la base SQLite de tu n8n local (`operativasIntegradas01`).

---

## ☁️ Despliegue en Render Cloud (24/7 Sin Depender de PC Local)

Para que todos los procesos corran de forma continua en la nube:

### 1. Arquitectura en Render
El proyecto cuenta con un servidor FastAPI de alto rendimiento (`server_render.py`) con un **Scheduler interno (APScheduler)**:
- Mantiene las 6 tareas corriendo según sus cronogramas de fondo 24/7.
- Expone endpoints REST para que puedas disparar cualquier tarea desde cualquier lugar (n8n Cloud, webhook, dashboard, móvil):
  - `POST /sync/all`
  - `POST /sync/tracking`
  - `POST /sync/vacio`
  - `POST /sync/seguimiento-vacio`
  - `POST /sync/dispo`
  - `POST /sync/cordillera`
  - `POST /sync/conf-viaje`
  - `POST /sync/limpiar-vacio`
  - `GET /health` y `GET /status`

### 2. Autenticación en la Nube
No necesitas subir archivos de claves privadas a GitHub/GitLab.
En el panel de Render, agrega la variable de entorno:
- **`GOOGLE_SERVICE_ACCOUNT_JSON`**: Copia y pega el contenido completo del archivo JSON de la cuenta de servicio (`ute-logistica-firebase-adminsdk-fbsvc-04f3a4a36e.json`).

Todos los scripts (`credentials_helper.py`, `core.js`, `sheets_client.py`) detectan automáticamente esta variable y autentican en memoria.

### 3. Archivos Listos para Render
- [`Dockerfile`](./Dockerfile): Imagen lista para producción con Python 3.11 + Node.js 20.
- [`render.yaml`](./render.yaml): Blueprint de despliegue con 1 clic.
- [`requirements.txt`](./requirements.txt) y [`package.json`](./package.json).

---

## 💻 Ejecución Local en Windows

Puedes ejecutar cualquier tarea con los archivos por lotes (`.bat`) o mediante CLI:

```bash
# Orquestador Maestro (corre todas las tareas)
run_all_syncs.bat
# o por CLI:
py -3.13 run_all_syncs.py --apply

# Tareas individuales
py -3.13 sync_ruteos_movimientos.py --apply
py -3.13 sync_vacio.py --apply --borders
py -3.13 sync_seguimiento_vacio.py --apply
node pintarDisponibilidad.js
py -3.13 main.py --seguridad-vial
py -3.13 main.py --conf-viaje
py -3.13 limpiar_vacio.py --apply
```

---

> ⚠️ **Nota de Seguridad sobre Migración:**
> Las carpetas originales (`sheets`, `col_h_mov`, `viajes cordillera`, `pintardisp`) se han conservado intactas sin eliminar ningún archivo. Una vez que verifiques el correcto funcionamiento en `diaria`, procederemos al borrado de las carpetas antiguas para mantener la organización limpia.
