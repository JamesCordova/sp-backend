from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, auth, families, pickup, schools, students, teacher

app = FastAPI(title="Safe Pickup API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # allow_credentials=False porque la autenticación va por header
    # "Authorization: Bearer <jwt>", no por cookies; así se puede combinar
    # con allow_origins=["*"] (los navegadores rechazan credentials+"*").
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(schools.router)
app.include_router(students.router)
app.include_router(families.router)
app.include_router(pickup.router)
app.include_router(teacher.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
