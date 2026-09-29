from flask import Blueprint, render_template, session
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

reporte_bp = Blueprint("reporte", __name__, url_prefix="/reportes")


@reporte_bp.route("/")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def dashboard_reportes():
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM ventas
        WHERE empresa_id = %s
        AND MONTH(fecha) = MONTH(CURRENT_DATE())
        AND YEAR(fecha) = YEAR(CURRENT_DATE())
        AND estado = 'pagada'
    """, (empresa_id,))
    ventas_mes = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM ventas
        WHERE empresa_id = %s
        AND MONTH(fecha) = MONTH(CURRENT_DATE())
        AND YEAR(fecha) = YEAR(CURRENT_DATE())
    """, (empresa_id,))
    cantidad_ventas_mes = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM clientes
        WHERE empresa_id = %s
        AND activo = 1
    """, (empresa_id,))
    clientes_activos = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM equipos_reparacion
        WHERE empresa_id = %s
        AND estado IN ('pendiente', 'realizado', 'para_entregar')
    """, (empresa_id,))
    reparaciones_pendientes = cur.fetchone()[0]

    cur.execute("""
        SELECT 
            u.nombre,
            u.apellido,
            COUNT(e.id) AS total
        FROM equipos_reparacion e
        LEFT JOIN usuarios u ON e.tecnico_id = u.id
        WHERE e.empresa_id = %s
        GROUP BY u.id, u.nombre, u.apellido
        ORDER BY total DESC
        LIMIT 5
    """, (empresa_id,))
    reparaciones_por_tecnico = cur.fetchall()

    cur.execute("""
        SELECT 
            p.marca,
            p.modelo,
            SUM(d.cantidad) AS total_vendido
        FROM detalle_venta d
        INNER JOIN ventas v ON d.venta_id = v.id
        INNER JOIN productos p ON d.producto_id = p.id
        WHERE v.empresa_id = %s
        GROUP BY p.id, p.marca, p.modelo
        ORDER BY total_vendido DESC
        LIMIT 5
    """, (empresa_id,))
    productos_mas_vendidos = cur.fetchall()

    cur.execute("""
        SELECT 
            p.marca,
            p.modelo,
            s.nombre,
            st.cantidad
        FROM stock st
        INNER JOIN productos p ON st.producto_id = p.id
        INNER JOIN sucursales s ON st.sucursal_id = s.id
        WHERE p.empresa_id = %s
        AND st.cantidad <= 2
        ORDER BY st.cantidad ASC
        LIMIT 10
    """, (empresa_id,))
    stock_bajo = cur.fetchall()

    cur.execute("""
        SELECT COALESCE(SUM(precio_aplicado), 0)
        FROM reparacion_mano_obra rm
        INNER JOIN equipos_reparacion e ON rm.equipo_id = e.id
        WHERE e.empresa_id = %s
        AND MONTH(e.fecha_ingreso) = MONTH(CURRENT_DATE())
        AND YEAR(e.fecha_ingreso) = YEAR(CURRENT_DATE())
    """, (empresa_id,))
    mano_obra_mes = cur.fetchone()[0]

    cur.close()

    return render_template(
        "reportes/dashboard_reportes.html",
        ventas_mes=ventas_mes,
        cantidad_ventas_mes=cantidad_ventas_mes,
        clientes_activos=clientes_activos,
        reparaciones_pendientes=reparaciones_pendientes,
        reparaciones_por_tecnico=reparaciones_por_tecnico,
        productos_mas_vendidos=productos_mas_vendidos,
        stock_bajo=stock_bajo,
        mano_obra_mes=mano_obra_mes
    )