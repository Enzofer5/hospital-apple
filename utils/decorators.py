from functools import wraps
from flask import session, redirect, url_for, flash

def login_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Primero debés iniciar sesión.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorador


def roles_requeridos(*roles):
    def wrapper(f):
        @wraps(f)
        def decorador(*args, **kwargs):
            if "usuario_id" not in session:
                flash("Primero debés iniciar sesión.", "warning")
                return redirect(url_for("auth.login"))

            if session.get("rol") not in roles:
                flash("No tenés permiso para acceder a esta sección.", "danger")
                return redirect(url_for("dashboard.dashboard"))

            return f(*args, **kwargs)
        return decorador
    return wrapper