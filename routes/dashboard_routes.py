from datetime import date
from flask import Blueprint, render_template, session
from utils.decorators import login_requerido
from extensions import mysql

dashboard_bp = Blueprint("dashboard", __name__)


def obtener_datos_financieros_dueno(cur, empresa_id):
    """
    Números reales del negocio para el dashboard del Dueño/Socio: ventas brutas
    (desglosadas por categoría de producto, ej. Accesorios/Equipos), ingresos por
    reparación (mano de obra + repuestos), ganancia bruta del mes, y rankings de
    vendedor y técnico. Todo el sistema trabaja en dólares (USD).
    """

    # Ventas brutas del mes (equipos + accesorios)
    cur.execute("""
        SELECT COALESCE(SUM(total),0)
        FROM ventas
        WHERE empresa_id=%s AND estado='pagada'
        AND MONTH(fecha)=MONTH(CURDATE()) AND YEAR(fecha)=YEAR(CURDATE())
    """, (empresa_id,))
    ventas_brutas_mes = cur.fetchone()[0]

    # Desglose de esas ventas por categoría de producto (Accesorios, Equipos, etc.)
    cur.execute("""
        SELECT COALESCE(c.nombre, 'Sin categoría') AS categoria,
               COALESCE(SUM(d.subtotal),0) AS total,
               COALESCE(SUM(d.cantidad),0) AS unidades
        FROM detalle_venta d
        INNER JOIN ventas v ON d.venta_id=v.id
        INNER JOIN productos p ON d.producto_id=p.id
        LEFT JOIN categorias_producto c ON p.categoria_id=c.id
        WHERE v.empresa_id=%s AND v.estado='pagada'
        AND MONTH(v.fecha)=MONTH(CURDATE()) AND YEAR(v.fecha)=YEAR(CURDATE())
        GROUP BY c.id, c.nombre
        ORDER BY total DESC
    """, (empresa_id,))
    ventas_por_categoria = cur.fetchall()

    # Ingresos por reparación del mes: mano de obra aplicada + repuestos usados
    cur.execute("""
        SELECT COALESCE(SUM(rm.precio_aplicado),0)
        FROM reparacion_mano_obra rm
        INNER JOIN equipos_reparacion e ON rm.equipo_id=e.id
        WHERE e.empresa_id=%s
        AND MONTH(e.fecha_ingreso)=MONTH(CURDATE()) AND YEAR(e.fecha_ingreso)=YEAR(CURDATE())
    """, (empresa_id,))
    mano_obra_mes = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(rr.subtotal),0)
        FROM reparacion_repuestos rr
        INNER JOIN equipos_reparacion e ON rr.equipo_id=e.id
        WHERE e.empresa_id=%s
        AND MONTH(e.fecha_ingreso)=MONTH(CURDATE()) AND YEAR(e.fecha_ingreso)=YEAR(CURDATE())
    """, (empresa_id,))
    repuestos_reparacion_mes = cur.fetchone()[0]

    ingresos_reparacion_mes = mano_obra_mes + repuestos_reparacion_mes

    # Ganancia bruta de ventas (precio de venta - costo)
    cur.execute("""
        SELECT COALESCE(SUM((d.precio_unitario - p.precio_costo_usd) * d.cantidad),0)
        FROM detalle_venta d
        INNER JOIN ventas v ON d.venta_id=v.id
        INNER JOIN productos p ON d.producto_id=p.id
        WHERE v.empresa_id=%s AND v.estado='pagada'
        AND MONTH(v.fecha)=MONTH(CURDATE()) AND YEAR(v.fecha)=YEAR(CURDATE())
    """, (empresa_id,))
    ganancia_ventas_mes = cur.fetchone()[0]

    # Ganancia de los repuestos usados en reparaciones (precio aplicado - costo)
    cur.execute("""
        SELECT COALESCE(SUM((rr.precio_unitario - p.precio_costo_usd) * rr.cantidad),0)
        FROM reparacion_repuestos rr
        INNER JOIN equipos_reparacion e ON rr.equipo_id=e.id
        INNER JOIN productos p ON rr.producto_id=p.id
        WHERE e.empresa_id=%s
        AND MONTH(e.fecha_ingreso)=MONTH(CURDATE()) AND YEAR(e.fecha_ingreso)=YEAR(CURDATE())
    """, (empresa_id,))
    ganancia_repuestos_mes = cur.fetchone()[0]

    # La mano de obra se cuenta como ganancia al 100% (no tiene costo de mercadería)
    ganancia_bruta_mes = ganancia_ventas_mes + mano_obra_mes + ganancia_repuestos_mes

    # Vendedor que más vendió en el mes
    cur.execute("""
        SELECT u.id, u.nombre, u.apellido,
               COALESCE(SUM(v.total),0) AS total_vendido,
               COUNT(v.id) AS cantidad_ventas
        FROM ventas v
        INNER JOIN usuarios u ON v.vendedor_id=u.id
        WHERE v.empresa_id=%s AND v.estado='pagada'
        AND MONTH(v.fecha)=MONTH(CURDATE()) AND YEAR(v.fecha)=YEAR(CURDATE())
        GROUP BY u.id, u.nombre, u.apellido
        ORDER BY total_vendido DESC
        LIMIT 5
    """, (empresa_id,))
    ranking_vendedores = cur.fetchall()

    # Técnico que más reparó en el mes
    cur.execute("""
        SELECT u.id, u.nombre, u.apellido,
               COUNT(DISTINCT e.id) AS cantidad_reparaciones,
               COALESCE(SUM(rm.precio_aplicado),0) AS total_mano_obra
        FROM equipos_reparacion e
        INNER JOIN usuarios u ON e.tecnico_id=u.id
        LEFT JOIN reparacion_mano_obra rm ON rm.equipo_id=e.id
        WHERE e.empresa_id=%s
        AND MONTH(e.fecha_ingreso)=MONTH(CURDATE()) AND YEAR(e.fecha_ingreso)=YEAR(CURDATE())
        GROUP BY u.id, u.nombre, u.apellido
        ORDER BY cantidad_reparaciones DESC
        LIMIT 5
    """, (empresa_id,))
    ranking_tecnicos = cur.fetchall()

    return {
        "ventas_brutas_mes": ventas_brutas_mes,
        "ventas_por_categoria": ventas_por_categoria,
        "mano_obra_mes": mano_obra_mes,
        "repuestos_reparacion_mes": repuestos_reparacion_mes,
        "ingresos_reparacion_mes": ingresos_reparacion_mes,
        "ganancia_ventas_mes": ganancia_ventas_mes,
        "ganancia_repuestos_mes": ganancia_repuestos_mes,
        "ganancia_bruta_mes": ganancia_bruta_mes,
        "ranking_vendedores": ranking_vendedores,
        "ranking_tecnicos": ranking_tecnicos,
    }


def obtener_datos_vendedor(cur, empresa_id, usuario_id):
    """
    Números del mes para el propio vendedor: total vendido, desglose por
    categoría (equipos/accesorios), porcentaje de comisión y comisión ganada.
    """

    cur.execute("""
        SELECT
            COALESCE(SUM(total),0),
            COUNT(*)
        FROM ventas
        WHERE empresa_id=%s AND vendedor_id=%s AND estado='pagada'
        AND MONTH(fecha)=MONTH(CURDATE()) AND YEAR(fecha)=YEAR(CURDATE())
    """, (empresa_id, usuario_id))
    total_vendido_mes, cantidad_ventas_mes = cur.fetchone()

    cur.execute("""
        SELECT COALESCE(c.nombre, 'Sin categoría') AS categoria,
               COALESCE(SUM(d.subtotal),0) AS total,
               COALESCE(SUM(d.cantidad),0) AS unidades
        FROM detalle_venta d
        INNER JOIN ventas v ON d.venta_id=v.id
        INNER JOIN productos p ON d.producto_id=p.id
        LEFT JOIN categorias_producto c ON p.categoria_id=c.id
        WHERE v.empresa_id=%s AND v.vendedor_id=%s AND v.estado='pagada'
        AND MONTH(v.fecha)=MONTH(CURDATE()) AND YEAR(v.fecha)=YEAR(CURDATE())
        GROUP BY c.id, c.nombre
        ORDER BY total DESC
    """, (empresa_id, usuario_id))
    ventas_por_categoria = cur.fetchall()

    cur.execute("SELECT porcentaje_comision FROM usuarios WHERE id=%s", (usuario_id,))
    fila = cur.fetchone()
    porcentaje_comision = fila[0] if fila and fila[0] else 0

    comision_mes = total_vendido_mes * (porcentaje_comision / 100)

    cur.execute("""
        SELECT c.nombre, c.apellido, v.total, v.fecha
        FROM ventas v
        INNER JOIN clientes c ON v.cliente_id=c.id
        WHERE v.empresa_id=%s AND v.vendedor_id=%s
        ORDER BY v.fecha DESC
        LIMIT 10
    """, (empresa_id, usuario_id))
    ultimas_ventas = cur.fetchall()

    return {
        "total_vendido_mes": total_vendido_mes,
        "cantidad_ventas_mes": cantidad_ventas_mes,
        "ventas_por_categoria": ventas_por_categoria,
        "porcentaje_comision": porcentaje_comision,
        "comision_mes": comision_mes,
        "ultimas_ventas": ultimas_ventas,
    }


def obtener_datos_tecnico(cur, empresa_id, usuario_id):
    """
    Números del mes para el propio técnico: reparaciones activas/pendientes,
    mano de obra generada, y el pago del mes (comisión sobre mano de obra si
    tiene porcentaje cargado, o sueldo fijo si no). Incluye modo_estudiante.
    """

    cur.execute("""
        SELECT COUNT(*) FROM equipos_reparacion
        WHERE empresa_id=%s AND tecnico_id=%s
        AND estado IN ('pendiente','realizado','para_entregar')
    """, (empresa_id, usuario_id))
    reparaciones_activas = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM equipos_reparacion
        WHERE empresa_id=%s AND tecnico_id=%s AND estado='pendiente'
    """, (empresa_id, usuario_id))
    reparaciones_pendientes = cur.fetchone()[0]

    cur.execute("""
        SELECT
            COALESCE(SUM(rm.precio_aplicado),0),
            COUNT(DISTINCT e.id)
        FROM reparacion_mano_obra rm
        INNER JOIN equipos_reparacion e ON rm.equipo_id=e.id
        WHERE e.empresa_id=%s AND e.tecnico_id=%s
        AND MONTH(e.fecha_ingreso)=MONTH(CURDATE()) AND YEAR(e.fecha_ingreso)=YEAR(CURDATE())
    """, (empresa_id, usuario_id))
    mano_obra_mes, reparaciones_facturadas_mes = cur.fetchone()

    cur.execute("""
        SELECT porcentaje_comision, sueldo_usd, modo_estudiante
        FROM usuarios WHERE id=%s
    """, (usuario_id,))
    fila_usuario = cur.fetchone()
    porcentaje_comision = fila_usuario[0] or 0
    sueldo_usd = fila_usuario[1] or 0
    modo_estudiante = bool(fila_usuario[2])

    if porcentaje_comision and porcentaje_comision > 0:
        pago_mes = mano_obra_mes * (porcentaje_comision / 100)
        modalidad_pago = "comision"
    else:
        pago_mes = sueldo_usd
        modalidad_pago = "sueldo_fijo"

    cur.execute("""
        SELECT c.nombre, c.apellido, e.marca, e.modelo, e.estado, e.fecha_ingreso
        FROM equipos_reparacion e
        INNER JOIN clientes c ON e.cliente_id=c.id
        WHERE e.empresa_id=%s AND e.tecnico_id=%s
        AND e.fecha_ingreso >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        ORDER BY e.fecha_ingreso DESC
        LIMIT 20
    """, (empresa_id, usuario_id))
    ultimas_reparaciones = cur.fetchall()

    return {
        "reparaciones_activas": reparaciones_activas,
        "reparaciones_pendientes": reparaciones_pendientes,
        "mano_obra_mes": mano_obra_mes,
        "reparaciones_facturadas_mes": reparaciones_facturadas_mes,
        "porcentaje_comision": porcentaje_comision,
        "sueldo_usd": sueldo_usd,
        "modo_estudiante": modo_estudiante,
        "pago_mes": pago_mes,
        "modalidad_pago": modalidad_pago,
        "ultimas_reparaciones": ultimas_reparaciones,
    }


def obtener_datos_atencion_publico(cur, empresa_id, usuario_id):
    """
    Igual que el vendedor (básico + comisión sobre lo que vendió), pero la
    comisión solo se paga si la facturación TOTAL del negocio del mes supera
    la meta configurada en Configuración (metas_empresa / meta_mensual_negocio).
    """

    cur.execute("""
        SELECT
            COALESCE(SUM(total),0),
            COUNT(*)
        FROM ventas
        WHERE empresa_id=%s AND vendedor_id=%s AND estado='pagada'
        AND MONTH(fecha)=MONTH(CURDATE()) AND YEAR(fecha)=YEAR(CURDATE())
    """, (empresa_id, usuario_id))
    total_vendido_mes, cantidad_ventas_mes = cur.fetchone()

    cur.execute("""
        SELECT COALESCE(c.nombre, 'Sin categoría') AS categoria,
               COALESCE(SUM(d.subtotal),0) AS total,
               COALESCE(SUM(d.cantidad),0) AS unidades
        FROM detalle_venta d
        INNER JOIN ventas v ON d.venta_id=v.id
        INNER JOIN productos p ON d.producto_id=p.id
        LEFT JOIN categorias_producto c ON p.categoria_id=c.id
        WHERE v.empresa_id=%s AND v.vendedor_id=%s AND v.estado='pagada'
        AND MONTH(v.fecha)=MONTH(CURDATE()) AND YEAR(v.fecha)=YEAR(CURDATE())
        GROUP BY c.id, c.nombre
        ORDER BY total DESC
    """, (empresa_id, usuario_id))
    ventas_por_categoria = cur.fetchall()

    cur.execute("SELECT porcentaje_comision, sueldo_usd FROM usuarios WHERE id=%s", (usuario_id,))
    fila_usuario = cur.fetchone()
    porcentaje_comision = fila_usuario[0] or 0
    sueldo_usd = fila_usuario[1] or 0

    # Facturación TOTAL del negocio este mes (todos los vendedores, no solo este usuario)
    cur.execute("""
        SELECT COALESCE(SUM(total),0)
        FROM ventas
        WHERE empresa_id=%s AND estado='pagada'
        AND MONTH(fecha)=MONTH(CURDATE()) AND YEAR(fecha)=YEAR(CURDATE())
    """, (empresa_id,))
    facturacion_total_negocio_mes = cur.fetchone()[0]

    cur.execute("""
        SELECT monto FROM metas_empresa
        WHERE empresa_id=%s AND concepto='meta_mensual_negocio'
    """, (empresa_id,))
    fila_meta = cur.fetchone()
    meta_mensual_negocio = fila_meta[0] if fila_meta else 0

    meta_configurada = meta_mensual_negocio and meta_mensual_negocio > 0
    meta_alcanzada = bool(meta_configurada and facturacion_total_negocio_mes >= meta_mensual_negocio)

    comision_mes = total_vendido_mes * (porcentaje_comision / 100) if meta_alcanzada else 0

    cur.execute("""
        SELECT c.nombre, c.apellido, v.total, v.fecha
        FROM ventas v
        INNER JOIN clientes c ON v.cliente_id=c.id
        WHERE v.empresa_id=%s AND v.vendedor_id=%s
        ORDER BY v.fecha DESC
        LIMIT 10
    """, (empresa_id, usuario_id))
    ultimas_ventas = cur.fetchall()

    return {
        "total_vendido_mes": total_vendido_mes,
        "cantidad_ventas_mes": cantidad_ventas_mes,
        "ventas_por_categoria": ventas_por_categoria,
        "porcentaje_comision": porcentaje_comision,
        "sueldo_usd": sueldo_usd,
        "facturacion_total_negocio_mes": facturacion_total_negocio_mes,
        "meta_mensual_negocio": meta_mensual_negocio,
        "meta_configurada": meta_configurada,
        "meta_alcanzada": meta_alcanzada,
        "comision_mes": comision_mes,
        "ultimas_ventas": ultimas_ventas,
    }


def obtener_datos_objetivos(cur, empresa_id, usuario_id):
    """
    Objetivos del mes para el usuario: los cargados a su nombre puntualmente,
    más los cargados para todo su sector/rol. Usado por Administracion y Marketing.
    """

    cur.execute("SELECT rol_id, sueldo_usd FROM usuarios WHERE id=%s", (usuario_id,))
    fila_usuario = cur.fetchone()
    rol_id = fila_usuario[0]
    sueldo_usd = fila_usuario[1] or 0

    hoy = date.today()

    cur.execute("""
        SELECT id, titulo, descripcion, monto_bonus, estado
        FROM objetivos
        WHERE empresa_id=%s
        AND (usuario_id=%s OR rol_id=%s)
        AND mes=%s AND anio=%s
        ORDER BY estado ASC, id DESC
    """, (empresa_id, usuario_id, rol_id, hoy.month, hoy.year))
    objetivos = cur.fetchall()

    bonus_ganado = sum(float(o[3]) for o in objetivos if o[4] == "cumplido")

    return {
        "objetivos": objetivos,
        "bonus_ganado": bonus_ganado,
        "sueldo_usd": sueldo_usd,
        "total_mes": float(sueldo_usd) + bonus_ganado,
    }


def obtener_datos_alertas_administracion(cur, empresa_id):
    """Servicios (luz, agua, gas, alquiler, etc.) por vencer para Administracion."""

    # Servicios (luz, agua, gas, alquiler, etc.) que vencen dentro de los
    # próximos 10 días o que ya vencieron y siguen sin pagar.
    cur.execute("""
        SELECT id, nombre, monto, fecha_vencimiento
        FROM servicios_empresa
        WHERE empresa_id = %s
        AND estado = 'pendiente'
        AND fecha_vencimiento <= DATE_ADD(CURDATE(), INTERVAL 10 DAY)
        ORDER BY fecha_vencimiento ASC
    """, (empresa_id,))
    servicios_por_vencer = cur.fetchall()

    return {
        "servicios_por_vencer": servicios_por_vencer,
    }


@dashboard_bp.route("/dashboard")
@login_requerido
def dashboard():
    empresa_id = session["empresa_id"]
    usuario_id = session["usuario_id"]
    rol = session["rol"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM clientes
        WHERE empresa_id=%s AND activo=1
    """, (empresa_id,))
    clientes = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM productos
        WHERE empresa_id=%s AND activo=1
    """, (empresa_id,))
    productos = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM stock st
        INNER JOIN productos p ON st.producto_id = p.id
        WHERE p.empresa_id=%s
        AND p.activo=1
        AND st.cantidad<=5
    """, (empresa_id,))
    stock_bajo = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM equipos_reparacion
        WHERE empresa_id=%s
        AND estado IN ('pendiente','realizado','para_entregar')
    """, (empresa_id,))
    reparaciones = cur.fetchone()[0]

    cur.execute("""
        SELECT IFNULL(SUM(total),0)
        FROM ventas
        WHERE empresa_id=%s
        AND MONTH(fecha)=MONTH(CURDATE())
        AND YEAR(fecha)=YEAR(CURDATE())
    """, (empresa_id,))
    ventas_mes = cur.fetchone()[0]

    cur.execute("""
        SELECT IFNULL(SUM(total),0)
        FROM facturas
        WHERE empresa_id=%s
        AND estado='emitida'
        AND MONTH(fecha)=MONTH(CURDATE())
        AND YEAR(fecha)=YEAR(CURDATE())
    """, (empresa_id,))
    facturacion = cur.fetchone()[0]

    cur.execute("""
        SELECT IFNULL(SUM(precio_aplicado),0)
        FROM reparacion_mano_obra rm
        INNER JOIN equipos_reparacion e ON rm.equipo_id=e.id
        WHERE e.empresa_id=%s
    """, (empresa_id,))
    mano_obra = cur.fetchone()[0]

    cur.execute("""
        SELECT c.nombre, c.apellido, v.total, v.fecha
        FROM ventas v
        INNER JOIN clientes c ON v.cliente_id=c.id
        WHERE v.empresa_id=%s
        ORDER BY v.fecha DESC
        LIMIT 5
    """, (empresa_id,))
    ultimas_ventas = cur.fetchall()

    cur.execute("""
        SELECT marca, modelo, estado, fecha_ingreso
        FROM equipos_reparacion
        WHERE empresa_id=%s
        ORDER BY fecha_ingreso DESC
        LIMIT 5
    """, (empresa_id,))
    ultimas_reparaciones = cur.fetchall()

    datos = {
        "clientes": clientes,
        "productos": productos,
        "stock_bajo": stock_bajo,
        "reparaciones": reparaciones,
        "ventas_mes": ventas_mes,
        "facturacion": facturacion,
        "mano_obra": mano_obra,
        "ultimas_ventas": ultimas_ventas,
        "ultimas_reparaciones": ultimas_reparaciones
    }

    if rol in ("Dueño", "Socio"):
        datos.update(obtener_datos_financieros_dueno(cur, empresa_id))
    elif rol == "Vendedor":
        datos.update(obtener_datos_vendedor(cur, empresa_id, usuario_id))
    elif rol == "Tecnico":
        datos.update(obtener_datos_tecnico(cur, empresa_id, usuario_id))
    elif rol == "Atención al público":
        datos.update(obtener_datos_atencion_publico(cur, empresa_id, usuario_id))
    elif rol in ("Administracion", "Marketing"):
        datos.update(obtener_datos_objetivos(cur, empresa_id, usuario_id))
        if rol == "Administracion":
            datos.update(obtener_datos_alertas_administracion(cur, empresa_id))

    cur.close()

    plantillas = {
        "Dueño": "dashboard/dashboard_dueno.html",
        "Socio": "dashboard/dashboard_socio.html",
        "Administracion": "dashboard/dashboard_administracion.html",
        "Vendedor": "dashboard/dashboard_vendedor.html",
        "Recepcionista": "dashboard/dashboard_recepcionista.html",
        "Atención al público": "dashboard/dashboard_atencion_publico.html",
        "Marketing": "dashboard/dashboard_marketing.html",
        "Tecnico": "dashboard/dashboard_tecnico.html",
        "Cajero": "dashboard/dashboard_cajero.html"
    }

    if rol in plantillas:
        return render_template(plantillas[rol], datos=datos)

    return "Rol no autorizado"