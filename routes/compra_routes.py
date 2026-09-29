from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

compra_bp = Blueprint("compra", __name__, url_prefix="/compras")


@compra_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def listar_compras():
    empresa_id = session["empresa_id"]

    proveedor_id = request.args.get("proveedor_id", "")
    fecha_desde = request.args.get("fecha_desde", "")
    fecha_hasta = request.args.get("fecha_hasta", "")
    buscar = request.args.get("buscar", "")

    compras = []

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre
        FROM proveedores
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    proveedores = cur.fetchall()

    if buscar == "1":
        query = """
            SELECT
                c.id,
                c.fecha,
                p.nombre,
                s.nombre,
                u.nombre,
                u.apellido,
                c.numero_factura,
                c.total
            FROM compras c
            INNER JOIN proveedores p ON c.proveedor_id = p.id
            INNER JOIN sucursales s ON c.sucursal_id = s.id
            INNER JOIN usuarios u ON c.usuario_id = u.id
            WHERE c.empresa_id = %s
        """
        params = [empresa_id]

        if proveedor_id:
            query += " AND c.proveedor_id = %s"
            params.append(proveedor_id)

        if fecha_desde:
            query += " AND DATE(c.fecha) >= %s"
            params.append(fecha_desde)

        if fecha_hasta:
            query += " AND DATE(c.fecha) <= %s"
            params.append(fecha_hasta)

        query += " ORDER BY c.fecha DESC LIMIT 100"

        cur.execute(query, params)
        compras = cur.fetchall()

    cur.close()

    return render_template(
        "compras/listar_compras.html",
        compras=compras,
        proveedores=proveedores,
        filtros={
            "proveedor_id": proveedor_id,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "buscar": buscar
        }
    )


@compra_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def crear_compra():
    empresa_id = session["empresa_id"]
    usuario_id = session["usuario_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        sucursal_id = request.form["sucursal_id"]
        proveedor_id = request.form["proveedor_id"]
        numero_factura = request.form.get("numero_factura", "")
        observacion = request.form.get("observacion", "")

        productos_ids = request.form.getlist("producto_id[]")
        cantidades = request.form.getlist("cantidad[]")
        precios_costos = request.form.getlist("precio_costo[]")

        if not productos_ids:
            flash("Debe agregar al menos un producto.", "danger")
            return redirect(url_for("compra.crear_compra"))

        try:
            items = []
            total = 0

            for producto_id, cantidad_txt, precio_txt in zip(productos_ids, cantidades, precios_costos):
                cantidad = int(cantidad_txt)
                precio_costo = float(precio_txt)

                if cantidad <= 0 or precio_costo < 0:
                    flash("La cantidad debe ser mayor a 0 y el costo no puede ser negativo.", "danger")
                    return redirect(url_for("compra.crear_compra"))

                subtotal = cantidad * precio_costo
                total += subtotal

                items.append({
                    "producto_id": producto_id,
                    "cantidad": cantidad,
                    "precio_costo": precio_costo,
                    "subtotal": subtotal
                })

            cur.execute("""
                INSERT INTO compras (
                    empresa_id, sucursal_id, proveedor_id, usuario_id,
                    numero_factura, total, observacion
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                empresa_id,
                sucursal_id,
                proveedor_id,
                usuario_id,
                numero_factura,
                total,
                observacion
            ))

            compra_id = cur.lastrowid

            for item in items:
                cur.execute("""
                    INSERT INTO detalle_compra (
                        compra_id, producto_id, cantidad, precio_costo, subtotal
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    compra_id,
                    item["producto_id"],
                    item["cantidad"],
                    item["precio_costo"],
                    item["subtotal"]
                ))

                cur.execute("""
                    UPDATE productos
                    SET precio_costo_usd = %s
                    WHERE id = %s AND empresa_id = %s
                """, (
                    item["precio_costo"],
                    item["producto_id"],
                    empresa_id
                ))

                cur.execute("""
                    SELECT id, cantidad
                    FROM stock
                    WHERE producto_id = %s AND sucursal_id = %s
                """, (
                    item["producto_id"],
                    sucursal_id
                ))

                stock_actual = cur.fetchone()

                if stock_actual:
                    nueva_cantidad = stock_actual[1] + item["cantidad"]

                    cur.execute("""
                        UPDATE stock
                        SET cantidad = %s
                        WHERE id = %s
                    """, (
                        nueva_cantidad,
                        stock_actual[0]
                    ))
                else:
                    cur.execute("""
                        INSERT INTO stock (
                            producto_id, sucursal_id, cantidad
                        )
                        VALUES (%s, %s, %s)
                    """, (
                        item["producto_id"],
                        sucursal_id,
                        item["cantidad"]
                    ))

                cur.execute("""
                    INSERT INTO movimientos_stock (
                        producto_id, sucursal_id, usuario_id, tipo, cantidad, observacion
                    )
                    VALUES (%s, %s, %s, 'ingreso', %s, %s)
                """, (
                    item["producto_id"],
                    sucursal_id,
                    usuario_id,
                    item["cantidad"],
                    f"Compra N° {compra_id}"
                ))

            mysql.connection.commit()
            flash("Compra registrada correctamente.", "success")
            return redirect(url_for("compra.detalle_compra", id=compra_id))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al registrar compra: {e}", "danger")
            return redirect(url_for("compra.crear_compra"))

        finally:
            cur.close()

    cur.execute("""
        SELECT id, nombre
        FROM proveedores
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    proveedores = cur.fetchall()

    cur.execute("""
        SELECT id, nombre
        FROM sucursales
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    sucursales = cur.fetchall()

    cur.execute("""
        SELECT id, marca, modelo
        FROM productos
        WHERE empresa_id = %s AND activo = 1
        ORDER BY marca, modelo
    """, (empresa_id,))
    productos = cur.fetchall()

    cur.close()

    return render_template(
        "compras/crear_compra.html",
        proveedores=proveedores,
        sucursales=sucursales,
        productos=productos
    )


@compra_bp.route("/detalle/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def detalle_compra(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            c.id,
            c.fecha,
            p.nombre,
            s.nombre,
            u.nombre,
            u.apellido,
            c.numero_factura,
            c.total,
            c.observacion
        FROM compras c
        INNER JOIN proveedores p ON c.proveedor_id = p.id
        INNER JOIN sucursales s ON c.sucursal_id = s.id
        INNER JOIN usuarios u ON c.usuario_id = u.id
        WHERE c.id = %s AND c.empresa_id = %s
    """, (id, empresa_id))

    compra = cur.fetchone()

    if not compra:
        cur.close()
        flash("Compra no encontrada.", "danger")
        return redirect(url_for("compra.listar_compras"))

    cur.execute("""
        SELECT
            p.marca,
            p.modelo,
            d.cantidad,
            d.precio_costo,
            d.subtotal
        FROM detalle_compra d
        INNER JOIN productos p ON d.producto_id = p.id
        WHERE d.compra_id = %s
    """, (id,))

    detalles = cur.fetchall()
    cur.close()

    return render_template(
        "compras/detalle_compra.html",
        compra=compra,
        detalles=detalles
    )