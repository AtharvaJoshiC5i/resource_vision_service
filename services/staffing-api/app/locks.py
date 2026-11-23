from __future__ import annotations

import threading

# Re-entrant: confirmation holds the employee lock and then frees competing blocks under it.
_employee_locks: dict[str, threading.RLock] = {}
_lock_guard = threading.Lock()


def lock_for_employee(employee_key: str) -> threading.RLock:
    with _lock_guard:
        return _employee_locks.setdefault(employee_key.upper(), threading.RLock())