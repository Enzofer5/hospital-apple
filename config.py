import os


class Config:
    SECRET_KEY = "clave_secreta_segura"

    MYSQL_HOST = "localhost"
    MYSQL_USER = "root"
    MYSQL_PASSWORD = "43772036"
    MYSQL_DB = "hospital_apple"

    # El modo debug muestra el código fuente y una consola interactiva
    # ante cualquier error. Está pensado solo para desarrollo: en la PC
    # del negocio debe quedar apagado (DEBUG=False) para que un error
    # nunca exponga datos ni permita ejecutar código desde el navegador.
    # Para activarlo temporalmente en desarrollo, definí la variable de
    # entorno FLASK_DEBUG=1 antes de correr appy.py.
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"