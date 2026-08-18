import asyncio
import json
import urllib.request

from app.config import settings

_cache: dict[str, dict] = {}
_lock = asyncio.Lock()


def _fetch_jwks() -> dict[str, dict]:
    url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return {key["kid"]: key for key in data["keys"]}


async def get_jwk(kid: str) -> dict | None:
    """Devuelve la clave pública (JWK) para el `kid` dado, refrescando el
    caché una vez si no se encuentra (cubre la rotación de claves de Supabase)."""
    if kid in _cache:
        return _cache[kid]

    async with _lock:
        if kid in _cache:
            return _cache[kid]
        fresh = await asyncio.to_thread(_fetch_jwks)
        _cache.update(fresh)

    return _cache.get(kid)
