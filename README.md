# Safe Pickup — Backend (FastAPI + Supabase)

## Arquitectura

```
Frontend (index.html/app.js)
   │
   ├── supabase-js  ──────────────►  Supabase Auth   (login, signup, recuperar contraseña)
   │                                        │
   │                                        ▼ emite JWT
   │
   └── fetch(Authorization: Bearer <jwt>) ─► FastAPI (este backend)
                                                  │
                                                  ▼ SQLAlchemy (asyncpg)
                                          Supabase Postgres (schema.sql)
```

- **Supabase Auth** es la única fuente de contraseñas/sesión. El frontend usa `supabase-js`
  directamente contra Supabase para login, registro y "olvidé mi contraseña". Nunca le
  manda la contraseña a FastAPI.
- **FastAPI** recibe el JWT que entrega Supabase Auth, lo verifica y aplica toda la lógica
  de negocio del documento (`Safe_Pickup_Definicion_Completa.md`): quién puede solicitar un
  recojo, quién puede llamar/entregar, verificación de autorización, turnos por jornada, etc.
  Los tokens de sesión de Supabase Auth se firman con una clave **asimétrica (ES256)**, no
  con un secreto compartido: `app/auth.py` verifica cada token contra el JWKS público del
  proyecto (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, cacheado en memoria en
  `app/jwks.py`), no contra un "JWT Secret" copiado a mano.
- **Row Level Security** está habilitada en todas las tablas pero sin políticas para
  `anon`/`authenticated`: la API pública de Supabase (PostgREST/supabase-js) queda cerrada
  para estas tablas. Sólo este backend, conectado vía el connection pooler de Postgres,
  puede leer/escribir los datos. Así toda la autorización vive en un solo lugar (Python),
  no repartida entre RLS y backend.

## Credenciales de Supabase que necesito

Crea (o usa) un proyecto en https://supabase.com y comparte/coloca en `backend/.env`
(copiando `backend/.env.example`):

1. **`DATABASE_URL`** — Project Settings → Database → Connection string → modo
   **"Session pooler"** (puerto 5432). No uses la conexión directa
   (`db.<ref>.supabase.co`): esa solo resuelve por IPv6, y hosts como Render no tienen
   salida IPv6, lo que produce `OSError: Network is unreachable` en producción aunque
   funcione perfecto en tu máquina. Cambia el prefijo `postgresql://` por
   `postgresql+asyncpg://` y reemplaza `[YOUR-PASSWORD]` por la contraseña de la base de
   datos que definiste al crear el proyecto.
2. **`SUPABASE_URL`** — Project Settings → API → Project URL. FastAPI la usa tanto para
   verificar tokens (JWKS) como el frontend para inicializar `supabase-js`.
3. *(Opcional para el MVP)* **`SUPABASE_SERVICE_ROLE_KEY`** — Project Settings → API →
   Project API keys → `service_role`. Sólo se necesita si más adelante el backend llama a la
   Admin API de Supabase Auth (por ejemplo, para bloquear una cuenta). Es secreta: nunca va
   en el frontend.
4. El frontend, por separado, necesita **`SUPABASE_URL`** y la clave **`anon` (public)**
   (Project Settings → API → Project API keys → `anon public`) para inicializar
   `supabase-js` y manejar login/signup.

No necesito la contraseña de tu cuenta de Supabase ni acceso al dashboard: sólo estos
valores del proyecto.

## Puesta en marcha

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
copy .env.example .env            # y completa los valores reales
```

Aplica el esquema (una sola vez, o cuando cambie): pega el contenido de `schema.sql`
(en la raíz del proyecto) en el SQL Editor de Supabase y ejecútalo, o:

```bash
psql "$DATABASE_URL_SIN_ASYNC" -f ../schema.sql
```

Levanta la API:

```bash
uvicorn app.main:app --reload
```

Documentación interactiva en `http://127.0.0.1:8000/docs`.

## Qué implementa el MVP

- `GET /me` — perfil, roles por colegio y membresías familiares del usuario autenticado.
- `POST /families/{family_id}/invitations` — OWNER/ADMIN invita a otro miembro (el token se
  devuelve en la respuesta; el envío real por email/SMS no está implementado todavía).
- `POST /families/invitations/accept` — el invitado (ya registrado en Supabase Auth) canjea
  el token y queda vinculado a la familia.
- `POST /families/{family_id}/students/link` — la familia solicita vincularse a un
  estudiante por `student_code` (queda `PENDING`).
- `POST /admin/schools/{school_id}/family-students/{id}/verify` — el colegio (ADMIN)
  aprueba o rechaza ese vínculo. Sin esto, la familia no puede autorizar recojos.
- `POST /families/{family_id}/authorizations` — OWNER/ADMIN autoriza (o revoca) a un
  miembro familiar para recoger a un estudiante ya verificado.
- `POST /admin/schools/{school_id}/pickup-sessions` — el colegio abre la jornada de salida
  del día.
- `POST /pickup/requests` — un familiar solicita el recojo: valida sesión abierta, vínculo
  verificado y que la persona que recogerá esté autorizada; asigna turno correlativo dentro
  de la jornada.
- `POST /pickup/requests/{id}/cancel` — el solicitante cancela mientras esté en espera.
- `GET /teacher/classrooms/{id}/queue` — cola ordenada por turno, sólo para el docente
  asignado a esa aula.
- `POST /teacher/requests/{id}/call` — el docente llama al turno.
- `POST /teacher/requests/{id}/deliver` — el docente registra la entrega. Vuelve a validar
  que quien recoge esté autorizado (aunque no sea la persona prevista originalmente) y
  guarda `verification_method` (`DIGITAL_REQUEST` / `MANUAL_IDENTITY_CHECK` / `QR`).
- `GET /admin/schools/{school_id}/deliveries` — historial de entregas del colegio.
- Cada acción relevante queda en `audit_logs`.

## Lo que queda pendiente (ver sección 27 del documento)

Esto no rompe el modelo de datos, pero no está resuelto en el código todavía:

- Envío real de invitaciones por email/SMS (hoy el token se devuelve en la respuesta HTTP).
- Verificación de identidad presencial más allá de `MANUAL_IDENTITY_CHECK` como string libre.
- Lectura de QR (el campo `verification_method = 'QR'` existe, falta el escaneo/generación).
- Modo de contingencia sin internet.
- Endpoints de administración completos para altas de colegio/aula/estudiante (hoy sólo
  están los necesarios para el flujo de recojo; el resto se puede insertar directamente
  por SQL mientras no haya UI de administración).
