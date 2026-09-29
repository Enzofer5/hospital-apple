import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cambiar-esta-clave")

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DB = os.environ.get("MYSQL_DB", "hospital_apple")

    # El modo debug muestra el código fuente y una consola interactiva
    # ante cualquier error. Está pensado solo para desarrollo: en la PC
    # del negocio debe quedar apagado (DEBUG=False) para que un error
    # nunca exponga datos ni permita ejecutar código desde el navegador.
    # Para activarlo temporalmente en desarrollo, definí la variable de
    # entorno FLASK_DEBUG=1 antes de correr appy.py.
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"