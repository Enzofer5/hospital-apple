import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, current_app
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos
from utils.pdf_utils import generar_pdf_factura

factura_bp = Blueprint("factura", __name__, url_prefix="/facturas")


def generar_numero_factura(empresa_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM facturas
        WHERE empresa_id = %s
    """, (empresa_id,))
    cantidad = cur.fetchone()[0] + 1
    cur.close()

    return f"X-{cantidad:08d}"


@factura_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Cajero")
def listar_facturas():
    empresa_id = session["empresa_id"]

    cliente = request.args.get("cliente", "")
    tipo = request.args.get("tipo", "")
    estado = request.args.get("estado", "")
    fecha_desde = request.args.get("fecha_desde", "")
    fecha_hasta = request.args.get("fecha_hasta", "")
    buscar = request.args.get("buscar", "")

    facturas = []
    cur = mysql.connection.cursor()

    if buscar == "1":
        query = """
            SELECT 
                f.id, f.numero, f.tipo, f.concepto, f.total,
                f.estado, f.fecha, c.nombre, c.apellido, f.pdf
            FROM facturas f
            INNER JOIN clientes c ON f.cliente_id = c.id
            WHERE f.empresa_id = %s
        """
        params = [empresa_id]

        if cliente:
            query += " AND (c.nombre LIKE %s OR c.apellido LIKE %s OR c.dni LIKE %s)"
            params.extend([f"%{cliente}%", f"%{cliente}%", f"%{cliente}%"])

        if tipo:
            query += " AND f.tipo = %s"
            params.append(tipo)

        if estado:
            query += " AND f.estado = %s"
            params.append(estado)

        if fecha_desde:
            query += " AND DATE(f.fecha) >= %s"
            params.append(fecha_desde)

        if fecha_hasta:
            query += " AND DATE(f.fecha) <= %s"
            params.append(fecha_hasta)

        query += " ORDER BY f.fecha DESC LIMIT 100"

        cur.execute(query, params)
        facturas = cur.fetchall()

    cur.close()

    return render_template(
        "facturas/listar_facturas.html",
        facturas=facturas,
        filtros={
            "cliente": cliente,
            "tipo": tipo,
            "estado": estado,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "buscar": buscar
        }
    )


@factura_bp.route("/venta/<int:venta_id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Cajero")
def crear_factura_venta(venta_id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            SELECT id, empresa_id, sucursal_id, cliente_id, subtotal, descuento, total
            FROM ventas
            WHERE id = %s AND empresa_id = %s
        """, (venta_id, empresa_id))

        venta = cur.fetchone()

        if not venta:
            flash("Venta no encontrada.", "danger")
            return redirect(url_for("venta.listar_ventas"))

        cur.execute("""
            SELECT id
            FROM facturas
            WHERE venta_id = %s AND empresa_id = %s AND estado = 'emitida'
            LIMIT 1
        """, (venta_id, empresa_id))

        factura_existente = cur.fetchone()

        if factura_existente:
            flash("Esta venta ya tiene una factura emitida.", "warning")
            return redirect(url_for("factura.detalle_factura", id=factura_existente[0]))

        numero = generar_numero_factura(empresa_id)

        cur.execute("""
            INSERT INTO facturas (
                empresa_id, sucursal_id, cliente_id, venta_id,
                numero, tipo, concepto, subtotal, descuento, total, estado
            )
            VALUES (%s, %s, %s, %s, %s, 'X', 'venta', %s, %s, %s, 'emitida')
        """, (
            empresa_id, venta[2], venta[3], venta_id,
            numero, venta[4], venta[5], venta[6]
        ))

        factura_id = cur.lastrowid

        cur.execute("""
            SELECT d.producto_id, p.marca, p.modelo, d.cantidad, d.precio_unitario, d.subtotal
            FROM detalle_venta d
            INNER JOIN productos p ON d.producto_id = p.id
            WHERE d.venta_id = %s
        """, (venta_id,))

        detalles = cur.fetchall()

        for d in detalles:
            descripcion = f"{d[1]} {d[2]}"

            cur.execute("""
                INSERT INTO detalle_factura (
                    factura_id, producto_id, descripcion,
                    cantidad, precio_unitario, subtotal
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (factura_id, d[0], descripcion, d[3], d[4], d[5]))

        mysql.connection.commit()
        flash("Factura de venta emitida correctamente.", "success")
        return redirect(url_for("factura.detalle_factura", id=factura_id))

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al facturar venta: {e}", "danger")
        return redirect(url_for("venta.listar_ventas"))

    finally:
        cur.close()


@factura_bp.route("/reparacion/<int:equipo_id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Cajero")
def crear_factura_reparacion(equipo_id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            SELECT id, sucursal_id, cliente_id
            FROM equipos_reparacion
            WHERE id = %s AND empresa_id = %s
        """, (equipo_id, empresa_id))

        reparacion = cur.fetchone()

        if not reparacion:
            flash("Reparación no encontrada.", "danger")
            return redirect(url_for("reparacion.listar_reparaciones"))

        cur.execute("""
            SELECT id
            FROM facturas
            WHERE equipo_id = %s AND empresa_id = %s AND estado = 'emitida'
            LIMIT 1
        """, (equipo_id, empresa_id))

        factura_existente = cur.fetchone()

        if factura_existente:
            flash("Esta reparación ya tiene una factura emitida.", "warning")
            return redirect(url_for("factura.detalle_factura", id=factura_existente[0]))

        cur.execute("""
            SELECT rm.mano_obra_id, mo.nombre, rm.precio_aplicado
            FROM reparacion_mano_obra rm
            INNER JOIN mano_obra mo ON rm.mano_obra_id = mo.id
            WHERE rm.equipo_id = %s
        """, (equipo_id,))
        mano_obra = cur.fetchall()

        cur.execute("""
            SELECT rr.producto_id, p.marca, p.modelo, rr.cantidad, rr.precio_unitario, rr.subtotal
            FROM reparacion_repuestos rr
            INNER JOIN productos p ON rr.producto_id = p.id
            WHERE rr.equipo_id = %s
        """, (equipo_id,))
        repuestos = cur.fetchall()

        total_mano_obra = sum(float(m[2]) for m in mano_obra)
        total_repuestos = sum(float(r[5]) for r in repuestos)
        total = total_mano_obra + total_repuestos

        if total <= 0:
            flash("No se puede facturar una reparación sin importes.", "warning")
            return redirect(url_for("reparacion.detalle_reparacion", id=equipo_id))

        numero = generar_numero_factura(empresa_id)

        cur.execute("""
            INSERT INTO facturas (
                empresa_id, sucursal_id, cliente_id, equipo_id,
                numero, tipo, concepto, subtotal, descuento, total, estado
            )
            VALUES (%s, %s, %s, %s, %s, 'X', 'reparacion', %s, 0, %s, 'emitida')
        """, (
            empresa_id, reparacion[1], reparacion[2],
            equipo_id, numero, total, total
        ))

        factura_id = cur.lastrowid

        for m in mano_obra:
            cur.execute("""
                INSERT INTO detalle_factura (
                    factura_id, mano_obra_id, descripcion,
                    cantidad, precio_unitario, subtotal
                )
                VALUES (%s, %s, %s, 1, %s, %s)
            """, (factura_id, m[0], m[1], m[2], m[2]))

        for r in repuestos:
            descripcion = f"{r[1]} {r[2]}"

            cur.execute("""
                INSERT INTO detalle_factura (
                    factura_id, producto_id, descripcion,
                    cantidad, precio_unitario, subtotal
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (factura_id, r[0], descripcion, r[3], r[4], r[5]))

        mysql.connection.commit()
        flash("Factura de reparación emitida correctamente.", "success")
        return redirect(url_for("factura.detalle_factura", id=factura_id))

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al facturar reparación: {e}", "danger")
        return redirect(url_for("reparacion.detalle_reparacion", id=equipo_id))

    finally:
        cur.close()


@factura_bp.route("/detalle/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Cajero")
def detalle_factura(id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            f.id, f.numero, f.tipo, f.concepto, f.subtotal,
            f.descuento, f.total, f.estado, f.fecha,
            c.nombre, c.apellido, c.dni, c.email, c.telefono, f.pdf
        FROM facturas f
        INNER JOIN clientes c ON f.cliente_id = c.id
        WHERE f.id = %s AND f.empresa_id = %s
    """, (id, empresa_id))

    factura = cur.fetchone()

    if not factura:
        cur.close()
        flash("Factura no encontrada.", "danger")
        return redirect(url_for("factura.listar_facturas"))

    cur.execute("""
        SELECT descripcion, cantidad, precio_unitario, subtotal
        FROM detalle_factura
        WHERE factura_id = %s
    """, (id,))

    detalles = cur.fetchall()
    cur.close()

    return render_template(
        "facturas/detalle_factura.html",
        factura=factura,
        detalles=detalles
    )


@factura_bp.route("/generar-pdf/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Cajero")
def generar_pdf(id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            SELECT
                f.id, f.numero, f.tipo, f.concepto, f.subtotal,
                f.descuento, f.total, f.estado, f.fecha,
                c.nombre, c.apellido, c.dni, c.email, c.telefono, f.pdf
            FROM facturas f
            INNER JOIN clientes c ON f.cliente_id = c.id
            WHERE f.id = %s AND f.empresa_id = %s
        """, (id, empresa_id))

        factura = cur.fetchone()

        if not factura:
            flash("Factura no encontrada.", "danger")
            return redirect(url_for("factura.listar_facturas"))

        cur.execute("""
            SELECT descripcion, cantidad, precio_unitario, subtotal
            FROM detalle_factura
            WHERE factura_id = %s
        """, (id,))

        detalles = cur.fetchall()

        ruta_pdf = generar_pdf_factura(factura, detalles)

        cur.execute("""
            UPDATE facturas
            SET pdf = %s
            WHERE id = %s AND empresa_id = %s
        """, (ruta_pdf, id, empresa_id))

        mysql.connection.commit()

        flash("PDF generado correctamente.", "success")
        return redirect(url_for("factura.detalle_factura", id=id))

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al generar PDF: {e}", "danger")
        return redirect(url_for("factura.detalle_factura", id=id))

    finally:
        cur.close()


@factura_bp.route("/ver-pdf/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Cajero")
def ver_pdf(id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT pdf
        FROM facturas
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))

    factura = cur.fetchone()
    cur.close()

    if not factura or not factura[0]:
        flash("Primero tenés que generar el PDF.", "warning")
        return redirect(url_for("factura.detalle_factura", id=id))

    ruta_pdf = os.path.join(current_app.root_path, "static", factura[0])

    if not os.path.exists(ruta_pdf):
        flash("El archivo PDF no existe. Generá el PDF nuevamente.", "danger")
        return redirect(url_for("factura.detalle_factura", id=id))

    return send_file(ruta_pdf, as_attachment=False)


@factura_bp.route("/anular/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def anular_factura(id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE facturas
        SET estado = 'anulada'
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))

    mysql.connection.commit()
    cur.close()

    flash("Factura anulada correctamente.", "success")
    return redirect(url_for("factura.listar_facturas"))