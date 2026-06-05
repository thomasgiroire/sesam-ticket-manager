"""cache.py — Moteur de cache générique : disque atomique + LRU mémoire optionnel.

Caractéristiques :
- Entrées permanentes (p=True) : jamais expirées, résistent à invalidate(prefix=...)
- Cache mémoire LRU borné (mem_max=0 → disque uniquement)
- Écriture atomique (tmp + rename)
- Format JSON unifié : {key: {"ts": float, "v": any, "p": bool}}
"""

import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional


class CacheStore:
    def __init__(self, path: Path, mem_max: int = 500):
        self._path = path
        self._mem_max = mem_max
        self._mem: Optional[OrderedDict] = OrderedDict() if mem_max > 0 else None

    # ── Disque ───────────────────────────────────────────────────────────────

    def _disk_load(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _disk_save(self, data: dict) -> None:
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._path)
        except Exception:
            pass

    # ── Mémoire LRU ──────────────────────────────────────────────────────────

    def _mem_set(self, key: str, entry: dict) -> None:
        if self._mem is None:
            return
        if key in self._mem:
            self._mem.move_to_end(key)
        self._mem[key] = entry
        if len(self._mem) > self._mem_max:
            self._mem.popitem(last=False)

    def _mem_get(self, key: str) -> Optional[dict]:
        if self._mem is None or key not in self._mem:
            return None
        self._mem.move_to_end(key)
        return self._mem[key]

    # ── API publique ─────────────────────────────────────────────────────────

    def get(self, key: str, ttl: int) -> Optional[Any]:
        """Retourne la valeur si permanente ou dans le TTL, sinon None."""
        now = time.time()

        entry = self._mem_get(key)
        if entry:
            if entry.get("p") or now - entry["ts"] < ttl:
                return entry["v"]

        data = self._disk_load()
        entry = data.get(key)
        if entry:
            if entry.get("p") or now - entry["ts"] < ttl:
                self._mem_set(key, entry)
                return entry["v"]

        return None

    def get_raw(self, key: str) -> Optional[Any]:
        """Retourne la valeur sans vérification de TTL (lecture de référence)."""
        entry = self._mem_get(key)
        if entry:
            return entry["v"]
        data = self._disk_load()
        entry = data.get(key)
        if entry:
            self._mem_set(key, entry)
            return entry["v"]
        return None

    def put(self, key: str, value: Any, permanent: bool = False) -> None:
        """Stocke une valeur. permanent=True → jamais expiré, résiste à invalidate(prefix)."""
        entry = {"ts": time.time(), "v": value, "p": permanent}
        self._mem_set(key, entry)
        data = self._disk_load()
        data[key] = entry
        self._disk_save(data)

    def put_batch(self, items: dict[str, tuple[Any, bool]]) -> None:
        """Stocke plusieurs entrées en un seul write disque.
        items = {key: (value, permanent)}
        """
        data = self._disk_load()
        now = time.time()
        for key, (value, permanent) in items.items():
            entry = {"ts": now, "v": value, "p": permanent}
            self._mem_set(key, entry)
            data[key] = entry
        self._disk_save(data)

    def invalidate(self, prefix: str = "") -> None:
        """Supprime les entrées non permanentes dont la clé commence par prefix.
        Si prefix="" → purge totale y compris permanentes.
        """
        if self._mem is not None:
            if prefix:
                to_del = [k for k in self._mem if k.startswith(prefix) and not self._mem[k].get("p")]
            else:
                to_del = list(self._mem.keys())
            for k in to_del:
                del self._mem[k]

        data = self._disk_load()
        if prefix:
            to_del = [k for k in data if k.startswith(prefix) and not data[k].get("p")]
        else:
            to_del = list(data.keys())
        for k in to_del:
            del data[k]
        self._disk_save(data)

    def age_seconds(self, key: str) -> Optional[float]:
        """Retourne l'âge en secondes d'une entrée, None si absente."""
        entry = self._mem_get(key)
        if entry:
            return time.time() - entry["ts"]
        data = self._disk_load()
        entry = data.get(key)
        if entry:
            return time.time() - entry["ts"]
        return None

    def has_data(self) -> bool:
        """Vrai si le fichier cache existe et contient des entrées."""
        return self._path.exists() and bool(self._disk_load())

    def stats(self) -> dict:
        """Statistiques sur le cache disque."""
        data = self._disk_load()
        permanent = sum(1 for e in data.values() if e.get("p"))
        return {
            "total": len(data),
            "permanent": permanent,
            "volatile": len(data) - permanent,
            "file": str(self._path),
        }
