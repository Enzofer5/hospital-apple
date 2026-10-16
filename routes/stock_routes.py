from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

stock_bp = Blueprint("stock", __name__, url_prefix="/stock")


@stock_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Vendedor", "Recepcionista")
def listar_stock():
    empresa_id = session["empresa_id"]

    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    sucursal_id = request.args.get("sucursal_id", "")
    buscar = request.args.get("buscar", "")

    stock = []

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre
        FROM sucursales
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    sucursales = cur.fetchall()

    if buscar == "1":
        query = """
            SELECT 
                st.id,
                p.marca,
                p.modelo,
                p.descripcion,
                s.nombre AS sucursal,
                st.cantidad,
                p.precio_costo_usd,
                p.precio_venta_usd,
                p.foto
            FROM stock st
            INNER JOIN productos p ON st.producto_id = p.id
            INNER JOIN sucursales s ON st.sucursal_id = s.id
            WHERE p.empresa_id = %s
            AND p.activo = 1
        """

        params = [empresa_id]

        if marca:
            query += " AND p.marca LIKE %s"
            params.append(f"%{marca}%")

        if modelo:
            query += " AND p.modelo LIKE %s"
            params.append(f"%{modelo}%")

        if sucursal_id:
            query += " AND st.sucursal_id = %s"
            params.append(sucursal_id)

        query += " ORDER BY p.marca ASC, p.modelo ASC LIMIT 50"

        cur.execute(query, params)
        stock = cur.fetchall()

    cur.close()

    return render_template(
        "stock/listar_stock.html",
        stock=stock,
        sucursales=sucursales,
        filtros={
            "marca": marca,
            "modelo": modelo,
            "sucursal_id": sucursal_id,
            "buscar": buscar
        }
    )


@stock_bp.route("/cargar", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def cargar_stock():
    empresa_id = session["empresa_id"]
    usuario_id = session["usuario_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        producto_id = request.form["producto_id"]
        sucursal_id = request.form["sucursal_id"]
        cantidad = int(request.form["cantidad"])
        observacion = request.form["observacion"]

        try:
            cur.execute("""
                SELECT id, cantidad
                FROM stock
                WHERE producto_id = %s AND sucursal_id = %s
            """, (producto_id, sucursal_id))

            stock_actual = cur.fetchone()

            if stock_actual:
                nuevo_stock = stock_actual[1] + cantidad

                cur.execute("""
                    UPDATE stock
                    SET cantidad = %s
                    WHERE id = %s
                """, (nuevo_stock, stock_actual[0]))
            else:
                cur.execute("""
                    INSERT INTO stock(producto_id, sucursal_id, cantidad)
                    VALUES (%s, %s, %s)
                """, (producto_id, sucursal_id, cantidad))

            cur.execute("""
                INSERT INTO movimientos_stock(
                    producto_id, sucursal_id, usuario_id, tipo, cantidad, observacion
                )
                VALUES (%s, %s, %s, 'ingreso', %s, %s)
            """, (producto_id, sucursal_id, usuario_id, cantidad, observacion))

            mysql.connection.commit()
            flash("Stock cargado correctamente.", "success")
            return redirect(url_for("stock.listar_stock"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al cargar stock: {e}", "danger")

        finally:
            cur.close()

    else:
        cur.execute("""
            SELECT id, marca, modelo
            FROM productos
            WHERE empresa_id = %s AND activo = 1
            ORDER BY marca, modelo
        """, (empresa_id,))
        productos = cur.fetchall()

        cur.execute("""
            SELECT id, nombre
            FROM sucursales
            WHERE empresa_id = %s AND activo = 1
            ORDER BY nombre
        """, (empresa_id,))
        sucursales = cur.fetchall()

        cur.close()

        return render_template(
            "stock/cargar_stock.html",
            productos=productos,
            sucursales=sucursales
        )


@stock_bp.route("/movimientos", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def movimientos_stock():
    empresa_id = session["empresa_id"]

    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    sucursal_id = request.args.get("sucursal_id", "")
    tipo = request.args.get("tipo", "")
    buscar = request.args.get("buscar", "")

    movimientos = []

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre
        FROM sucursales
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    sucursales = cur.fetchall()

    if buscar == "1":
        query = """
            SELECT 
                m.id,
                p.marca,
                p.modelo,
                s.nombre AS sucursal,
                u.nombre,
                u.apellido,
                m.tipo,
                m.cantidad,
                m.fecha,
                m.observacion
            FROM movimientos_stock m
            INNER JOIN productos p ON m.producto_id = p.id
            INNER JOIN sucursales s ON m.sucursal_id = s.id
            LEFT JOIN usuarios u ON m.usuario_id = u.id
            WHERE p.empresa_id = %s
        """

        params = [empresa_id]

        if marca:
            query += " AND p.marca LIKE %s"
            params.append(f"%{marca}%")

        if modelo:
            query += " AND p.modelo LIKE %s"
            params.append(f"%{modelo}%")

        if sucursal_id:
            query += " AND m.sucursal_id = %s"
            params.append(sucursal_id)

        if tipo:
            query += " AND m.tipo = %s"
            params.append(tipo)

        query += " ORDER BY m.fecha DESC LIMIT 100"

        cur.execute(query, params)
        movimientos = cur.fetchall()

    cur.close()

    return render_template(
        "stock/movimiento_stock.html",
        movimientos=movimientos,
        sucursales=sucursales,
        filtros={
            "marca": marca,
            "modelo": modelo,
            "sucursal_id": sucursal_id,
            "tipo": tipo,
            "buscar": buscar
        }
    )