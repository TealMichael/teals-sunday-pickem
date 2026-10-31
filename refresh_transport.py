"""Close default provider sessions created inside one coordinated operation."""
from contextlib import contextmanager
from contextvars import ContextVar
_sessions = ContextVar('pickem_owned_provider_sessions', default=None)
def register_session(session):
    sessions = _sessions.get()
    if sessions is not None: sessions.append(session)
@contextmanager
def provider_scope():
    sessions = []; token = _sessions.set(sessions)
    try: yield
    finally:
        _sessions.reset(token)
        for session in reversed(sessions):
            try: session.close()
            except Exception: pass
