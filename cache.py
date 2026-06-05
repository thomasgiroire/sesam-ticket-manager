"""cache.py — Moteur de cache générique : disque atomique + LRU mémoire optionnel.

Caractéristiques :
- Entrées permanentes (p=True) : jamais expirées, résistent à invalidate(prefix=...)
- Cache mémoire LRU borné (mem_max=0 → disque uniquement)
- Écriture atomique (tmp + rename)
- Format JSON unifié : {key: {"ts": float, "v": any, "p": bool}}

LocalCache :
- Cache partagé entre web_app et main CLI
- Stockage mémoire LRU (OrderedDict, tuples (ts, data)) + disque (atomic write)
- API : get / set / cached / invalidate / peek
- _mem_cache exposé publiquement pour compatibilité avec les tests existants
- Helpers de sérialisation pour Ticket et Message
"""

import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Optional


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


# ─── LocalCache ───────────────────────────────────────────────────────────────

class LocalCache:
    """
    Cache LRU mémoire + disque partagé entre web_app et CLI.

    Format mémoire : _mem_cache[key] = (ts: float, data: any)
    Format disque  : {key: {"ts": float, "v": any, "validator": str|None}}

    Note : _mem_cache est un attribut public (OrderedDict) pour permettre
    aux tests d'inspecter / modifier directement le cache mémoire.
    """

    DEFAULT_PATH = Path(".sesam_cache.json")

    def __init__(self, path: Optional[Path] = None, mem_max: int = 500):
        self._path: Path = path or self.DEFAULT_PATH
        self._mem_max = mem_max
        # _mem_cache exposé publiquement : format (ts, data) pour compat tests
        self._mem_cache: OrderedDict = OrderedDict()

    # ── Mémoire LRU ──────────────────────────────────────────────────────────

    def _mem_put(self, key: str, ts: float, data: Any) -> None:
        """Insère ou met à jour une entrée mémoire (LRU). Évince le plus ancien si plein."""
        if key in self._mem_cache:
            self._mem_cache.move_to_end(key)
        self._mem_cache[key] = (ts, data)
        if len(self._mem_cache) > self._mem_max:
            self._mem_cache.popitem(last=False)

    def _mem_get(self, key: str, ttl: int) -> Optional[Any]:
        """Retourne la valeur mémoire si dans le TTL, sinon None."""
        entry = self._mem_cache.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.time() - ts < ttl:
            self._mem_cache.move_to_end(key)
            return data
        return None

    # ── Disque (atomic: write to .tmp then rename) ────────────────────────────

    def _disk_read(self) -> dict:
        """Lit le fichier cache disque. Retourne {} si absent ou illisible."""
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _disk_write(self, data: dict) -> None:
        """Écriture atomique (tmp + rename) du cache disque."""
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._path)
        except Exception:
            pass

    # ── API publique ──────────────────────────────────────────────────────────

    def peek(self, key: str) -> Optional[tuple]:
        """
        Retourne le tuple brut (ts, data) depuis le cache mémoire, sans vérification TTL.
        Utilisé par _enrich_gie_relance pour lire les messages sans déclencher de fetch.
        """
        return self._mem_cache.get(key)

    def get(self, key: str, ttl: int, validator: Optional[str] = None) -> Optional[Any]:
        """
        Retourne la valeur cachée si dans le TTL (et si le validator correspond).
        Vérifie d'abord la mémoire (si pas de validator), puis le disque.
        Retourne None si absent/expiré/validator invalide.

        validator : si fourni, l'entrée n'est valide que si son validator stocké correspond.
                    Quand un validator est fourni, le disque fait autorité (le validator n'est
                    pas stocké dans _mem_cache pour garder la compatibilité avec les tests).
        """
        now = time.time()

        # 1. Cache mémoire (seulement si pas de validator — le validator n'y est pas stocké)
        if validator is None:
            entry = self._mem_cache.get(key)
            if entry is not None:
                ts, data = entry
                if now - ts < ttl:
                    self._mem_cache.move_to_end(key)
                    return data

        # 2. Cache disque
        disk = self._disk_read()
        disk_entry = disk.get(key)
        if disk_entry is not None:
            entry_ts = disk_entry.get("ts", 0)
            entry_val = disk_entry.get("v")
            entry_validator = disk_entry.get("validator")
            if now - entry_ts < ttl:
                if validator is None or entry_validator == validator:
                    self._mem_put(key, entry_ts, entry_val)
                    return entry_val

        return None

    def set(self, key: str, data: Any, validator: Optional[str] = None) -> None:
        """
        Stocke une valeur en mémoire ET sur disque.
        validator : valeur opaque stockée avec l'entrée (ex: updated_at du ticket).
        """
        now = time.time()
        self._mem_put(key, now, data)
        disk = self._disk_read()
        disk[key] = {"ts": now, "v": data, "validator": validator}
        self._disk_write(disk)

    def cached(self, key: str, ttl: int, fn: Callable, validator: Optional[str] = None) -> Any:
        """
        Retourne la valeur en cache si valide, sinon appelle fn() et met en cache.
        fn() doit retourner une valeur JSON-sérialisable.
        """
        result = self.get(key, ttl, validator=validator)
        if result is not None:
            return result
        result = fn()
        self.set(key, result, validator=validator)
        return result

    def invalidate(self, prefix: str = "") -> None:
        """
        Supprime du cache mémoire et disque toutes les clés commençant par prefix.
        Si prefix="" → purge totale.
        """
        # Mémoire
        keys_to_del = [k for k in self._mem_cache if k.startswith(prefix)]
        for k in keys_to_del:
            del self._mem_cache[k]

        # Disque
        disk = self._disk_read()
        disk_keys_to_del = [k for k in disk if k.startswith(prefix)]
        for k in disk_keys_to_del:
            del disk[k]
        self._disk_write(disk)


# ─── Helpers de sérialisation ─────────────────────────────────────────────────

def serialize_tickets(tickets) -> list:
    """Convertit une liste de Ticket en liste de dicts JSON-sérialisables."""
    return [t.to_dict() for t in tickets]


def deserialize_tickets(data: list) -> list:
    """Reconstruit des objets Ticket depuis une liste de dicts. Skip les entrées invalides."""
    from portal import Ticket
    result = []
    for d in data:
        try:
            result.append(Ticket(**{k: v for k, v in d.items() if k != "raw"}))
        except Exception:
            pass
    return result


def serialize_messages(msgs) -> list:
    """Convertit une liste de Message en liste de dicts JSON-sérialisables."""
    return [vars(m) for m in msgs]


def deserialize_messages(data: list) -> list:
    """Reconstruit des objets Message depuis une liste de dicts. Skip les entrées invalides."""
    from portal import Message
    result = []
    for d in data:
        try:
            result.append(Message(**d))
        except Exception:
            pass
    return result
