import os
from decimal import Decimal
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

venta_bp = Blueprint("venta", __name__, url_prefix="/ventas")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "heic", "heif"}


def extension_permitida(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def guardar_foto(foto, carpeta_destino):
    if foto and foto.filename and extension_permitida(foto.filename):
        filename = secure_filename(foto.filename)
        carpeta = os.path.join(current_app.root_path, "static", "uploads", carpeta_destino)
        os.makedirs(carpeta, exist_ok=True)
        ruta_completa = os.path.join(carpeta, filename)
        foto.save(ruta_completa)
        return f"uploads/{carpeta_destino}/{filename}"
    return None


def asegurar_medios_cobro(empresa_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) FROM medios_cobro WHERE empresa_id = %s", (empresa_id,))
    cantidad = cur.fetchone()[0]

    if cantidad == 0:
        medios = ["Efectivo", "Transferencia", "Tarjeta de Crédito", "Tarjeta de Débito", "Dólares"]
        for medio in medios:
            cur.execute("""
                INSERT INTO medios_cobro (empresa_id, nombre, activo)
                VALUES (%s, %s, 1)
            """, (empresa_id, medio))
        mysql.connection.commit()

    cur.close()


@venta_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Vendedor", "Atención al público", "Cajero")
def listar_ventas():
    empresa_id = session["empresa_id"]

    cliente = request.args.get("cliente", "")
    vendedor_id = request.args.get("vendedor_id", "")
    sucursal_id = request.args.get("sucursal_id", "")
    fecha_desde = request.args.get("fecha_desde", "")
    fecha_hasta = request.args.get("fecha_hasta", "")
    buscar = request.args.get("buscar", "")

    ventas = []
    cur = mysql.connection.cursor()

    cur.execute("SELECT id, nombre FROM sucursales WHERE empresa_id = %s AND activo = 1", (empresa_id,))
    sucursales = cur.fetchall()

    cur.execute("""
        SELECT u.id, u.nombre, u.apellido
        FROM usuarios u
        INNER JOIN roles r ON u.rol_id = r.id
        WHERE u.empresa_id = %s
        AND r.nombre IN ('Vendedor', 'Atención al público')
        AND u.activo = 1
    """, (empresa_id,))
    vendedores = cur.fetchall()

    if buscar == "1":
        query = """
            SELECT
                v.id, v.fecha, c.nombre, c.apellido,
                u.nombre, u.apellido, s.nombre,
                v.tipo_venta, v.moneda, v.total, v.estado, v.firma_estado
            FROM ventas v
            INNER JOIN clientes c ON v.cliente_id = c.id
            INNER JOIN usuarios u ON v.vendedor_id = u.id
            INNER JOIN sucursales s ON v.sucursal_id = s.id
            WHERE v.empresa_id = %s
        """
        params = [empresa_id]

        if cliente:
            query += " AND (c.nombre LIKE %s OR c.apellido LIKE %s OR c.dni LIKE %s)"
            params.extend([f"%{cliente}%", f"%{cliente}%", f"%{cliente}%"])

        if vendedor_id:
            query += " AND v.vendedor_id = %s"
            params.append(vendedor_id)

        if sucursal_id:
            query += " AND v.sucursal_id = %s"
            params.append(sucursal_id)

        if fecha_desde:
            query += " AND DATE(v.fecha) >= %s"
            params.append(fecha_desde)

        if fecha_hasta:
            query += " AND DATE(v.fecha) <= %s"
            params.append(fecha_hasta)

        query += " ORDER BY v.fecha DESC LIMIT 100"

        cur.execute(query, params)
        ventas = cur.fetchall()

    cur.close()

    return render_template(
        "ventas/listar_ventas.html",
        ventas=ventas,
        sucursales=sucursales,
        vendedores=vendedores,
        filtros={
            "cliente": cliente,
            "vendedor_id": vendedor_id,
            "sucursal_id": sucursal_id,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "buscar": buscar
        }
    )


@venta_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Vendedor", "Atención al público", "Cajero")
def crear_venta():
    empresa_id = session["empresa_id"]
    usuario_id = session["usuario_id"]

    asegurar_medios_cobro(empresa_id)

    cur = mysql.connection.cursor()

    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        sucursal_id = request.form["sucursal_id"]
        vendedor_id = request.form.get("vendedor_id") or usuario_id

        # El sistema trabaja siempre en dólares. La cotización solo se usa si
        # el cliente paga alguno de los medios de pago en pesos (cash ARS).
        moneda = "USD"
        cotizacion_dolar = Decimal(request.form.get("cotizacion_dolar") or "0")
        descuento = Decimal(request.form.get("descuento") or "0")

        productos_ids = request.form.getlist("producto_id[]")
        cantidades = request.form.getlist("cantidad[]")

        medios_cobro_ids = request.form.getlist("medio_cobro_id[]")
        monedas_pago = request.form.getlist("moneda_pago[]")
        montos_pago = request.form.getlist("monto_pago[]")

        usa_plan_canje = request.form.get("usa_plan_canje") == "1"

        try:
            if not productos_ids or not cantidades:
                flash("Debe agregar al menos un producto.", "danger")
                return redirect(url_for("venta.crear_venta"))

            if not medios_cobro_ids or not montos_pago:
                flash("Debe agregar al menos un pago.", "danger")
                return redirect(url_for("venta.crear_venta"))

            items = []
            subtotal_general = Decimal("0")

            for producto_id, cantidad_txt in zip(productos_ids, cantidades):
                cantidad = int(cantidad_txt)

                if cantidad <= 0:
                    flash("La cantidad debe ser mayor a 0.", "danger")
                    return redirect(url_for("venta.crear_venta"))

                cur.execute("""
                    SELECT id, marca, modelo, precio_venta_usd
                    FROM productos
                    WHERE id = %s AND empresa_id = %s AND activo = 1
                """, (producto_id, empresa_id))

                producto = cur.fetchone()

                if not producto:
                    flash("Uno de los productos no existe o está inactivo.", "danger")
                    return redirect(url_for("venta.crear_venta"))

                cur.execute("""
                    SELECT id, cantidad
                    FROM stock
                    WHERE producto_id = %s AND sucursal_id = %s
                """, (producto_id, sucursal_id))

                stock_actual = cur.fetchone()

                if not stock_actual or stock_actual[1] < cantidad:
                    flash(f"Stock insuficiente para {producto[1]} {producto[2]}.", "danger")
                    return redirect(url_for("venta.crear_venta"))

                precio_unitario = Decimal(producto[3] or 0)

                if precio_unitario <= 0:
                    flash(f"El producto {producto[1]} {producto[2]} no tiene precio en USD cargado.", "danger")
                    return redirect(url_for("venta.crear_venta"))

                subtotal_item = precio_unitario * Decimal(cantidad)
                subtotal_general += subtotal_item

                items.append({
                    "producto_id": producto[0],
                    "marca": producto[1],
                    "modelo": producto[2],
                    "cantidad": cantidad,
                    "precio_unitario": precio_unitario,
                    "subtotal": subtotal_item,
                    "stock_id": stock_actual[0],
                    "stock_actual": stock_actual[1]
                })

            valor_tomado = Decimal("0")
            importe_abona_cliente = Decimal("0")
            tipo_venta = "directa"
            ruta_foto_canje = None

            if usa_plan_canje:
                tipo_venta = "plan_canje"

                marca_entrega = request.form.get("marca_entrega", "").strip()
                modelo_entrega = request.form.get("modelo_entrega", "").strip()
                nro_serie_entrega = request.form.get("nro_serie_entrega", "").strip()
                estado_equipo = request.form.get("estado_equipo", "").strip()
                valor_tomado = Decimal(request.form.get("valor_tomado") or "0")
                importe_abona_cliente = Decimal(request.form.get("importe_abona_cliente") or "0")
                foto_equipo = request.files.get("foto_equipo")

                if not marca_entrega or not modelo_entrega:
                    flash("En Plan Canje debés ingresar marca y modelo del equipo entregado.", "danger")
                    return redirect(url_for("venta.crear_venta"))

                if valor_tomado < 0:
                    flash("El valor tomado no puede ser negativo.", "danger")
                    return redirect(url_for("venta.crear_venta"))

                ruta_foto_canje = guardar_foto(foto_equipo, "plan_canje")

            if descuento < 0:
                descuento = Decimal("0")

            descuento_total = descuento + valor_tomado

            if descuento_total > subtotal_general:
                flash("El descuento más el valor tomado no puede superar el subtotal.", "danger")
                return redirect(url_for("venta.crear_venta"))

            total = subtotal_general - descuento_total

            if usa_plan_canje:
                if round(importe_abona_cliente, 2) != round(total, 2):
                    flash("En Plan Canje, el importe que abona el cliente debe coincidir con el total final.", "danger")
                    return redirect(url_for("venta.crear_venta"))

            pagos = []
            total_pagado_en_moneda_venta = Decimal("0")

            for medio_id, moneda_pago, monto_txt in zip(medios_cobro_ids, monedas_pago, montos_pago):
                monto = Decimal(monto_txt or "0")

                if moneda_pago not in ["ARS", "USD"]:
                    flash("Moneda de pago inválida.", "danger")
                    return redirect(url_for("venta.crear_venta"))

                if monto <= 0:
                    flash("Todos los pagos deben tener monto mayor a 0.", "danger")
                    return redirect(url_for("venta.crear_venta"))

                if moneda_pago == moneda:
                    monto_convertido = monto
                elif moneda == "ARS" and moneda_pago == "USD":
                    if cotizacion_dolar <= 0:
                        flash("Para pagar en USD una venta en ARS debés cargar cotización.", "danger")
                        return redirect(url_for("venta.crear_venta"))
                    monto_convertido = monto * cotizacion_dolar
                elif moneda == "USD" and moneda_pago == "ARS":
                    if cotizacion_dolar <= 0:
                        flash("Para pagar en ARS una venta en USD debés cargar cotización.", "danger")
                        return redirect(url_for("venta.crear_venta"))
                    monto_convertido = monto / cotizacion_dolar
                else:
                    monto_convertido = monto

                pagos.append({
                    "medio_cobro_id": medio_id,
                    "moneda": moneda_pago,
                    "monto": monto,
                    "monto_convertido": monto_convertido
                })

                total_pagado_en_moneda_venta += monto_convertido

            if round(total_pagado_en_moneda_venta, 2) != round(total, 2):
                flash(
                    f"La suma de pagos equivale a {moneda} {round(total_pagado_en_moneda_venta, 2)} "
                    f"y debe ser igual al total de la venta ({moneda} {round(total, 2)}).",
                    "danger"
                )
                return redirect(url_for("venta.crear_venta"))

            cur.execute("""
                INSERT INTO ventas (
                    empresa_id, sucursal_id, cliente_id, vendedor_id,
                    tipo_venta, moneda, cotizacion_dolar,
                    subtotal, descuento, total, estado, firma_estado
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pagada', 'pendiente')
            """, (
                empresa_id,
                sucursal_id,
                cliente_id,
                vendedor_id,
                tipo_venta,
                moneda,
                cotizacion_dolar,
                subtotal_general,
                descuento_total,
                total
            ))

            venta_id = cur.lastrowid

            for item in items:
                cur.execute("""
                    INSERT INTO detalle_venta (
                        venta_id, producto_id, cantidad, moneda,
                        precio_unitario, subtotal
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    venta_id,
                    item["producto_id"],
                    item["cantidad"],
                    moneda,
                    item["precio_unitario"],
                    item["subtotal"]
                ))

                nuevo_stock = item["stock_actual"] - item["cantidad"]

                cur.execute("""
                    UPDATE stock
                    SET cantidad = %s
                    WHERE id = %s
                """, (nuevo_stock, item["stock_id"]))

                cur.execute("""
                    INSERT INTO movimientos_stock (
                        producto_id, sucursal_id, usuario_id, tipo, cantidad, observacion
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    item["producto_id"],
                    sucursal_id,
                    usuario_id,
                    "plan_canje" if usa_plan_canje else "venta",
                    item["cantidad"],
                    f"Venta N° {venta_id}"
                ))

            if usa_plan_canje:
                cur.execute("""
                    INSERT INTO plan_canje (
                        venta_id, marca_entrega, modelo_entrega,
                        nro_serie_entrega, estado_equipo, moneda,
                        valor_tomado, importe_abona_cliente, foto_equipo
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    venta_id,
                    marca_entrega,
                    modelo_entrega,
                    nro_serie_entrega,
                    estado_equipo,
                    moneda,
                    valor_tomado,
                    importe_abona_cliente,
                    ruta_foto_canje
                ))

            for pago in pagos:
                cur.execute("""
                    INSERT INTO pagos (
                        empresa_id, venta_id, medio_cobro_id, cajero_id,
                        moneda, cotizacion_dolar, monto, observacion
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    empresa_id,
                    venta_id,
                    pago["medio_cobro_id"],
                    usuario_id,
                    pago["moneda"],
                    cotizacion_dolar,
                    pago["monto"],
                    "Pago generado por venta"
                ))

            mysql.connection.commit()
            flash("Venta registrada correctamente.", "success")
            return redirect(url_for("venta.detalle_venta", id=venta_id))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al registrar venta: {e}", "danger")
            return redirect(url_for("venta.crear_venta"))

        finally:
            cur.close()

    cur.execute("""
        SELECT id, nombre, apellido, dni
        FROM clientes
        WHERE empresa_id = %s AND activo = 1
        ORDER BY apellido, nombre
        LIMIT 100
    """, (empresa_id,))
    clientes = cur.fetchall()

    cur.execute("""
        SELECT
            p.id,
            p.marca,
            p.modelo,
            s.nombre,
            st.cantidad,
            p.precio_venta_usd
        FROM stock st
        INNER JOIN productos p ON st.producto_id = p.id
        INNER JOIN sucursales s ON st.sucursal_id = s.id
        WHERE p.empresa_id = %s
        AND p.activo = 1
        AND st.cantidad > 0
        ORDER BY p.marca, p.modelo
        LIMIT 100
    """, (empresa_id,))
    productos = cur.fetchall()

    cur.execute("""
        SELECT id, nombre
        FROM sucursales
        WHERE empresa_id = %s AND activo = 1
    """, (empresa_id,))
    sucursales = cur.fetchall()

    cur.execute("""
        SELECT id, nombre
        FROM medios_cobro
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    medios_cobro = cur.fetchall()

    cur.execute("""
        SELECT u.id, u.nombre, u.apellido
        FROM usuarios u
        INNER JOIN roles r ON u.rol_id = r.id
        WHERE u.empresa_id = %s
        AND r.nombre IN ('Vendedor', 'Atención al público')
        AND u.activo = 1
    """, (empresa_id,))
    vendedores = cur.fetchall()

    cur.close()

    return render_template(
        "ventas/crear_venta.html",
        clientes=clientes,
        productos=productos,
        sucursales=sucursales,
        medios_cobro=medios_cobro,
        vendedores=vendedores
    )


@venta_bp.route("/detalle/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Vendedor", "Atención al público", "Cajero")
def detalle_venta(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            v.id, v.fecha, c.nombre, c.apellido, c.dni, c.telefono,
            u.nombre, u.apellido, s.nombre, v.tipo_venta,
            v.moneda, v.cotizacion_dolar, v.total,
            v.estado, v.firma_estado, v.fecha_firma, v.firma_cliente,
            v.token_firma
        FROM ventas v
        INNER JOIN clientes c ON v.cliente_id = c.id
        INNER JOIN usuarios u ON v.vendedor_id = u.id
        INNER JOIN sucursales s ON v.sucursal_id = s.id
        WHERE v.id = %s AND v.empresa_id = %s
    """, (id, empresa_id))

    venta = cur.fetchone()

    if not venta:
        cur.close()
        flash("Venta no encontrada.", "danger")
        return redirect(url_for("venta.listar_ventas"))

    cur.execute("""
        SELECT p.marca, p.modelo, d.cantidad, d.moneda, d.precio_unitario, d.subtotal
        FROM detalle_venta d
        INNER JOIN productos p ON d.producto_id = p.id
        WHERE d.venta_id = %s
    """, (id,))
    detalles = cur.fetchall()

    cur.execute("""
        SELECT m.nombre, p.moneda, p.monto, p.fecha
        FROM pagos p
        INNER JOIN medios_cobro m ON p.medio_cobro_id = m.id
        WHERE p.venta_id = %s
    """, (id,))
    pagos = cur.fetchall()

    cur.execute("""
        SELECT marca_entrega, modelo_entrega, nro_serie_entrega,
               estado_equipo, moneda, valor_tomado, importe_abona_cliente, foto_equipo
        FROM plan_canje
        WHERE venta_id = %s
        LIMIT 1
    """, (id,))
    plan_canje = cur.fetchone()

    cur.close()

    return render_template(
        "ventas/detalle_venta.html",
        venta=venta,
        detalles=detalles,
        pagos=pagos,
        plan_canje=plan_canje
    )