import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

producto_bp = Blueprint("producto", __name__, url_prefix="/productos")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def extension_permitida(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def guardar_foto_producto(foto):
    if foto and foto.filename and extension_permitida(foto.filename):
        filename = secure_filename(foto.filename)
        carpeta = os.path.join(current_app.root_path, "static", "uploads", "productos")
        os.makedirs(carpeta, exist_ok=True)

        ruta_completa = os.path.join(carpeta, filename)
        foto.save(ruta_completa)

        return f"uploads/productos/{filename}"

    return None


@producto_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Vendedor", "Recepcionista")
def listar_productos():
    empresa_id = session["empresa_id"]

    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    categoria_id = request.args.get("categoria_id", "")
    proveedor_id = request.args.get("proveedor_id", "")
    estado = request.args.get("estado", "")
    buscar = request.args.get("buscar", "")

    productos = []
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT id, nombre
        FROM categorias_producto
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    categorias = cur.fetchall()

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
                p.id,
                p.marca,
                p.modelo,
                p.descripcion,
                p.precio_costo_usd,
                p.precio_venta_usd,
                p.foto,
                p.activo,
                c.nombre AS categoria,
                pr.nombre AS proveedor
            FROM productos p
            LEFT JOIN categorias_producto c ON p.categoria_id = c.id
            LEFT JOIN proveedores pr ON p.proveedor_id = pr.id
            WHERE p.empresa_id = %s
        """

        params = [empresa_id]

        if marca:
            query += " AND p.marca LIKE %s"
            params.append(f"%{marca}%")

        if modelo:
            query += " AND p.modelo LIKE %s"
            params.append(f"%{modelo}%")

        if categoria_id:
            query += " AND p.categoria_id = %s"
            params.append(categoria_id)

        if proveedor_id:
            query += " AND p.proveedor_id = %s"
            params.append(proveedor_id)

        if estado != "":
            query += " AND p.activo = %s"
            params.append(estado)

        query += " ORDER BY p.marca ASC, p.modelo ASC LIMIT 50"

        cur.execute(query, params)
        productos = cur.fetchall()

    cur.close()

    return render_template(
        "productos/listar_producto.html",
        productos=productos,
        categorias=categorias,
        proveedores=proveedores,
        filtros={
            "marca": marca,
            "modelo": modelo,
            "categoria_id": categoria_id,
            "proveedor_id": proveedor_id,
            "estado": estado,
            "buscar": buscar
        }
    )


@producto_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def crear_producto():
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    if request.method == "POST":
        proveedor_id = request.form.get("proveedor_id") or None
        categoria_id = request.form.get("categoria_id") or None
        marca = request.form["marca"]
        modelo = request.form["modelo"]
        descripcion = request.form["descripcion"]

        precio_costo_usd = request.form.get("precio_costo_usd") or 0
        precio_venta_usd = request.form.get("precio_venta_usd") or 0

        foto = request.files.get("foto")
        ruta_foto = guardar_foto_producto(foto)

        try:
            cur.execute("""
                INSERT INTO productos (
                    empresa_id, proveedor_id, categoria_id, marca, modelo,
                    descripcion, precio_costo_usd, precio_venta_usd, foto, activo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            """, (
                empresa_id, proveedor_id, categoria_id, marca, modelo,
                descripcion, precio_costo_usd, precio_venta_usd, ruta_foto
            ))

            mysql.connection.commit()
            flash("Producto creado correctamente.", "success")
            return redirect(url_for("producto.listar_productos"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear producto: {e}", "danger")

        finally:
            cur.close()

    else:
        cur.execute("""
            SELECT id, nombre
            FROM categorias_producto
            WHERE empresa_id = %s AND activo = 1
            ORDER BY nombre
        """, (empresa_id,))
        categorias = cur.fetchall()

        cur.execute("""
            SELECT id, nombre
            FROM proveedores
            WHERE empresa_id = %s AND activo = 1
            ORDER BY nombre
        """, (empresa_id,))
        proveedores = cur.fetchall()

        cur.close()

        return render_template(
            "productos/crear_producto.html",
            categorias=categorias,
            proveedores=proveedores
        )


@producto_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def editar_producto(id):
    empresa_id = session["empresa_id"]
    cur = mysql.connection.cursor()

    if request.method == "POST":
        proveedor_id = request.form.get("proveedor_id") or None
        categoria_id = request.form.get("categoria_id") or None
        marca = request.form["marca"]
        modelo = request.form["modelo"]
        descripcion = request.form["descripcion"]

        precio_costo_usd = request.form.get("precio_costo_usd") or 0
        precio_venta_usd = request.form.get("precio_venta_usd") or 0

        foto = request.files.get("foto")
        ruta_foto = guardar_foto_producto(foto)

        try:
            if ruta_foto:
                cur.execute("""
                    UPDATE productos
                    SET proveedor_id=%s,
                        categoria_id=%s,
                        marca=%s,
                        modelo=%s,
                        descripcion=%s,
                        precio_costo_usd=%s,
                        precio_venta_usd=%s,
                        foto=%s
                    WHERE id=%s AND empresa_id=%s
                """, (
                    proveedor_id, categoria_id, marca, modelo, descripcion,
                    precio_costo_usd, precio_venta_usd,
                    ruta_foto, id, empresa_id
                ))
            else:
                cur.execute("""
                    UPDATE productos
                    SET proveedor_id=%s,
                        categoria_id=%s,
                        marca=%s,
                        modelo=%s,
                        descripcion=%s,
                        precio_costo_usd=%s,
                        precio_venta_usd=%s
                    WHERE id=%s AND empresa_id=%s
                """, (
                    proveedor_id, categoria_id, marca, modelo, descripcion,
                    precio_costo_usd, precio_venta_usd,
                    id, empresa_id
                ))

            mysql.connection.commit()
            flash("Producto actualizado correctamente.", "success")
            return redirect(url_for("producto.listar_productos"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al actualizar producto: {e}", "danger")

        finally:
            cur.close()

    cur.execute("""
        SELECT id, proveedor_id, categoria_id, marca, modelo,
               descripcion, precio_costo_usd, precio_venta_usd, foto
        FROM productos
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))

    producto = cur.fetchone()

    if not producto:
        cur.close()
        flash("Producto no encontrado.", "danger")
        return redirect(url_for("producto.listar_productos"))

    cur.execute("""
        SELECT id, nombre
        FROM categorias_producto
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    categorias = cur.fetchall()

    cur.execute("""
        SELECT id, nombre
        FROM proveedores
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    proveedores = cur.fetchall()

    cur.close()

    return render_template(
        "productos/editar_producto.html",
        producto=producto,
        categorias=categorias,
        proveedores=proveedores
    )


@producto_bp.route("/eliminar/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio")
def eliminar_producto(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE productos
        SET activo = 0
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))

    mysql.connection.commit()
    cur.close()

    flash("Producto dado de baja correctamente.", "success")
    return redirect(url_for("producto.listar_productos"))


@producto_bp.route("/categorias/crear", methods=["POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio")
def crear_categoria():
    empresa_id = session["empresa_id"]
    nombre = request.form["nombre_categoria"]

    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            INSERT INTO categorias_producto (empresa_id, nombre, activo)
            VALUES (%s, %s, 1)
        """, (empresa_id, nombre))

        mysql.connection.commit()
        flash("Categoría creada correctamente.", "success")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al crear categoría: {e}", "danger")

    finally:
        cur.close()

    return redirect(url_for("producto.listar_productos"))