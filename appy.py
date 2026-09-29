from flask import Flask, render_template, session
from config import Config
from extensions import mysql

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    mysql.init_app(app)

    @app.context_processor
    def inyectar_empresa_actual():
        # Disponible en TODOS los templates como "empresa_actual": permite que
        # cada empresa vea su propio logo y nombre en vez del de Apple Hospital
        # a la hora de mostrar el sistema como algo propio (marca blanca).
        empresa_id = session.get("empresa_id")
        if not empresa_id:
            return {"empresa_actual": None}

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT nombre, logo FROM empresas WHERE id = %s", (empresa_id,))
            fila = cur.fetchone()
            cur.close()
        except Exception:
            fila = None

        if not fila:
            return {"empresa_actual": None}

        return {"empresa_actual": {"nombre": fila[0], "logo": fila[1]}}

    @app.errorhandler(404)
    def pagina_no_encontrada(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def error_interno(error):
        # Si quedó una transacción a medio hacer, la deshacemos para que
        # la conexión no quede colgada para el próximo request.
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return render_template("errors/500.html"), 500

    from routes.auth_routes import auth_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.empleado_routes import empleado_bp
    from routes.cliente_routes import cliente_bp
    from routes.proveedor_routes import proveedor_bp
    from routes.producto_routes import producto_bp
    from routes.stock_routes import stock_bp
    from routes.venta_routes import venta_bp
    from routes.reparacion_routes import reparacion_bp
    from routes.mano_obra_routes import mano_obra_bp
    from routes.turno_routes import turno_bp 
    from routes.reporte_routes import reporte_bp     
    from routes.factura_routes import factura_bp   
    from routes.firma_routes import firma_bp
    from routes.compra_routes import (compra_bp)
    from routes.ficha_tecnica_routes import ficha_tecnica_bp
    from routes.configuracion_routes import configuracion_bp
    from routes.objetivo_routes import objetivo_bp
    from routes.ayuda_economica_routes import ayuda_economica_bp
    from routes.servicio_routes import servicio_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(empleado_bp)
    app.register_blueprint(cliente_bp)
    app.register_blueprint(proveedor_bp)
    app.register_blueprint(producto_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(venta_bp)
    app.register_blueprint(reparacion_bp)
    app.register_blueprint(mano_obra_bp)
    app.register_blueprint(turno_bp)
    app.register_blueprint(reporte_bp)
    app.register_blueprint(factura_bp)
    app.register_blueprint(firma_bp)
    app.register_blueprint(compra_bp)
    app.register_blueprint(ficha_tecnica_bp)
    app.register_blueprint(configuracion_bp)
    app.register_blueprint(objetivo_bp)
    app.register_blueprint(ayuda_economica_bp)
    app.register_blueprint(servicio_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    # host="0.0.0.0" hace que el servidor sea accesible desde otros dispositivos
    # de la misma red wifi (por ejemplo, un celular), no solo desde esta PC.
    # debug sale de config.py (Config.DEBUG) y por defecto está apagado,
    # para no exponer código ni datos si algo falla en la PC del negocio.
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])