# AGENTS.md — project context

> **DAW template.** Fill in the `[...]` with what is true of YOUR project and delete what does not
> apply. This file describes **the project**; **the process** is DAW's job (phases, gates, when to
> test, when to commit). Do not mix the two: process rules written here compete with the pipeline's.
>
> It is **tool-agnostic on purpose**: Claude Code reads it through the import in `CLAUDE.md`, Codex
> CLI, Copilot CLI, Cursor and OpenCode read it directly, and Gemini CLI gets it through
> `GEMINI.md`. The same file serves whichever tool you open the repo with — which is the point:
> porting the pipeline to another tool must not mean rewriting what your project is.

---

## Language

**Always respond in the language the user writes in Spanish ** Write every artifact you produce — PRDs,
specs, ADRs, reports, commit messages, status lines — in that same language, regardless of the
language these instructions are written in.

If this project has a fixed working language, state it here and use it instead:

> Working language: write all artifacts in Spanish

---

# Reserva de Vehículos Corporativos

Reserva por parte de los empleados de vehículos corporativos para usarlos en una fecha determinada. El empleado que reserva es el conductor. Un administrador gestiona el pool de vehículos.

**Reference PRD:** `docs/daw/prd/[your-prd].md`

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React + Vite |
| Backend | Python + FastAPI |
| Base de datos | PostgreSQL |
| Lint (frontend) | `npm run lint` (eslint) |
| Lint (backend) | `ruff check .` (dentro de `backend/`, con el venv activado) |

---

## Architecture conventions

**DAW validates your code against this section** during the CODE phase, via `daw-validate-arch`.
Leave it empty and that validation has nothing to compare against, so it stops being worth running.

- **Folder structure:** Separa los features.
   **Error handling:** Tipear errores; Nunca captura silenciosa.

- **Layer separation:** [e.g. the UI never talks to the database; always through a service]
- **Naming:** [e.g. files in kebab-case, components in PascalCase]
- **Dependencies:** [e.g. no new libraries without justifying them in the spec]

---

## Code conventions

- [e.g. No `any`. If it is unavoidable, it comes with a comment explaining why.]
- [e.g. Pure functions wherever possible; side effects at the edges.]
- [e.g. Comments only when the *why* is not obvious from the code.]

---



## Qué hacer / Qué no hacer

### General

#### Qué hacer
- Separar claramente las responsabilidades: UI en el frontend, lógica de negocio en el backend, persistencia en la base de datos.
- Validar los datos en el backend siempre, independientemente de lo que valide el frontend.
- Documentar los endpoints de la API con OpenAPI/Swagger (FastAPI lo genera automáticamente).
- Manejar errores con mensajes claros y códigos HTTP apropiados (400, 404, 409, 500).
- Usar variables de entorno para credenciales y configuración sensible (nunca hardcodear).

#### Qué no hacer
- No poner lógica de negocio en el frontend (ej: validar solapamiento de reservas solo en React).
- No exponer mensajes de error internos ni stack traces al cliente.
- No mezclar la capa de datos con la capa de presentación.
- No hardcodear URLs, credenciales ni configuraciones en el código fuente.

---

### Frontend — React + Vite

#### Qué hacer
- Organizar el proyecto en componentes reutilizables (formulario de reserva, listado de vehículos, filtros).
- Usar un cliente HTTP centralizado (ej: `axios` o `fetch` wrapper) para todas las llamadas a la API.
- Mostrar feedback visual claro al usuario: spinner de carga, mensajes de éxito y error.
- Validar campos en el formulario antes de enviar (nombre, legajo, licencia, fechas, destino).
- Verificar que la fecha/hora de fin sea posterior a la de inicio antes de enviar el formulario.
- Usar variables de entorno de Vite (`import.meta.env.VITE_API_URL`) para la URL del backend.

#### Qué no hacer
- No confiar únicamente en las validaciones del cliente; el backend debe validar todo igualmente.
- No guardar datos sensibles (credenciales del admin) en `localStorage` o `sessionStorage`.
- No hacer llamadas directas a la base de datos desde el frontend.
- No renderizar listas sin `key` única en React (genera problemas de reconciliación).
- No bloquear la UI durante las llamadas a la API; usar estados de carga asíncronos.

---

### Backend — Python + FastAPI

#### Qué hacer
- Usar modelos Pydantic para validar y tipar todos los datos de entrada y salida.
- Usar transacciones de base de datos al crear reservas para prevenir race conditions (`SELECT FOR UPDATE`).
- Separar el código en capas: routers (endpoints), servicios (lógica de negocio) y repositorios (acceso a datos).
- Usar un ORM (SQLAlchemy) o query builder para interactuar con PostgreSQL.
- Retornar códigos HTTP semánticos: 201 al crear, 409 si hay conflicto de reserva, 404 si no existe el recurso.
- Proteger los endpoints de administración con autenticación (ej: HTTP Basic o JWT simple).
- Configurar CORS correctamente para permitir solo el origen del frontend.

#### Qué no hacer
- No hacer consultas SQL crudas sin parámetros parametrizados (riesgo de SQL injection).
- No manejar la lógica de solapamiento de reservas en el frontend ni en SQL sin transacción.
- No ignorar los errores de base de datos; capturarlos y retornar respuestas adecuadas.
- No dejar los endpoints de administración sin protección.
- No bloquear el event loop con operaciones síncronas pesadas; usar `async/await` correctamente.

---

### Base de datos — PostgreSQL

#### Qué hacer
- Usar transacciones con `SELECT FOR UPDATE` al verificar disponibilidad y crear una reserva en la misma operación atómica.
- Definir constraints en la base de datos: `NOT NULL`, `CHECK` (fecha fin > fecha inicio), `UNIQUE` en patente.
- Crear índices en los campos más consultados: vehículo + fechas para las búsquedas de disponibilidad.
- Usar tipos de datos apropiados: `TIMESTAMP WITH TIME ZONE` para fechas, `VARCHAR` con longitud para patente y legajo.
- Implementar soft delete para vehículos (columna `activo`) en lugar de borrado físico, para preservar el historial.

#### Qué no hacer
- No permitir borrar un vehículo con reservas activas (validar en el backend y reforzar con constraint o trigger).
- No usar `TEXT` sin límite para campos que tienen longitud conocida (patente, legajo, licencia).
- No hacer consultas de disponibilidad sin índice en las columnas de fecha; en tablas grandes genera full scans.
- No almacenar contraseñas en texto plano; usar hashing (ej: `bcrypt`) para la credencial del administrador.
- No manejar la lógica de negocio en stored procedures o triggers; mantenerla en el backend para mayor mantenibilidad.

---

## Cómo ejecutar el proyecto

### Base de datos — PostgreSQL

```bash
# Crear la base de datos (y un usuario/rol de aplicación, si no existe)
psql -U postgres -c "CREATE USER reserva_app WITH PASSWORD 'elegí-una-password';"
psql -U postgres -c "CREATE DATABASE reserva_vehiculos OWNER reserva_app;"
```

### Backend — Python + FastAPI

```bash
cd backend

# Crear entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env: DATABASE_URL con la cadena de conexión a PostgreSQL, y
# ADMIN_PASSWORD_HASH con el hash bcrypt de la contraseña del admin,
# generado con:
#   python -c "from passlib.hash import bcrypt; print(bcrypt.hash('tu-password'))"

# Aplicar las migraciones
alembic upgrade head

# Ejecutar el servidor
uvicorn app.main:app --reload
# La API estará disponible en http://localhost:8000
# Documentación automática en http://localhost:8000/docs
```

### Frontend — React + Vite

```bash
cd frontend

# Instalar dependencias
npm install

# Configurar variables de entorno
cp .env.example .env
# Editar .env y setear VITE_API_URL=http://localhost:8000

# Ejecutar en modo desarrollo
npm run dev
# La app estará disponible en http://localhost:5173

# Generar build de producción
npm run build
```

---

## Reglas de negocio clave (para tener en cuenta en toda la implementación)

- Un vehículo no puede tener dos reservas activas que se solapen en el tiempo.
- Solo el empleado que creó la reserva puede cancelarla (validar por número de legajo).
- El empleado que reserva es el conductor; no se permiten reservas en nombre de terceros.
- Un vehículo con reservas activas no puede ser dado de baja del pool.
- Todos los campos de la reserva son obligatorios: nombre, legajo, licencia, vehículo, fecha/hora inicio, fecha/hora fin y destino.


---

> ℹ️ **What does NOT belong in this file, because DAW provides it:** the order work happens in, when
> the spec gets written, when tests run, when to commit, what it takes to move between phases. All
> of that lives in `.daw/` and applies on its own.

<!-- BEGIN DAW (managed by DAW — do not edit by hand) -->
# DAW — Dilux Agentic Workflow

This repo uses **DAW**: an agent-driven development pipeline with the phases
`CLASSIFY → DEFINE → PLAN → CODE → VERIFY → RELEASE`.

Before answering, read `.daw/orchestrator.md` and run its Boot Sequence. It is a strict state
machine: it decides what you are allowed to do based on the phase recorded in `.daw-state.json`.

The project's own context — stack, architecture, domain — is elsewhere in this file. It lives here,
in `AGENTS.md`, and not in any one tool's file, on purpose: it is tool-agnostic and comes along
unchanged when the pipeline is ported to another agent.
<!-- END DAW -->
