import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

reparacion_bp = Blueprint("reparacion", __name__, url_prefix="/reparaciones")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "heic", "heif"}


def extension_permitida(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def guardar_foto(foto, carpeta_destino):
    if foto and foto.filename and extension_permitida(foto.filename):
        filename = secure_filename(foto.filename)

        carpeta = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
            carpeta_destino
        )

        os.makedirs(carpeta, exist_ok=True)

        ruta_completa = os.path.join(carpeta, filename)
        foto.save(ruta_completa)

        return f"uploads/{carpeta_destino}/{filename}"

    return None


@reparacion_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def listar_reparaciones():
    empresa_id = session["empresa_id"]

    cliente = request.args.get("cliente", "")
    tecnico_id = request.args.get("tecnico_id", "")
    estado = request.args.get("estado", "")
    marca = request.args.get("marca", "")
    modelo = request.args.get("modelo", "")
    buscar = request.args.get("buscar", "")

    reparaciones = []

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT u.id, u.nombre, u.apellido
        FROM usuarios u
        INNER JOIN roles r ON u.rol_id = r.id
        WHERE u.empresa_id = %s
        AND r.nombre = 'Tecnico'
        AND u.activo = 1
        ORDER BY u.apellido, u.nombre
    """, (empresa_id,))
    tecnicos = cur.fetchall()

    if buscar == "1":
        query = """
            SELECT 
                e.id,
                c.nombre,
                c.apellido,
                e.marca,
                e.modelo,
                e.nro_serie,
                u.nombre,
                u.apellido,
                e.estado,
                e.fecha_ingreso
            FROM equipos_reparacion e
            INNER JOIN clientes c ON e.cliente_id = c.id
            LEFT JOIN usuarios u ON e.tecnico_id = u.id
            WHERE e.empresa_id = %s
        """

        params = [empresa_id]

        if cliente:
            query += " AND (c.nombre LIKE %s OR c.apellido LIKE %s OR c.dni LIKE %s)"
            params.extend([f"%{cliente}%", f"%{cliente}%", f"%{cliente}%"])

        if tecnico_id:
            query += " AND e.tecnico_id = %s"
            params.append(tecnico_id)

        if estado:
            query += " AND e.estado = %s"
            params.append(estado)

        if marca:
            query += " AND e.marca LIKE %s"
            params.append(f"%{marca}%")

        if modelo:
            query += " AND e.modelo LIKE %s"
            params.append(f"%{modelo}%")

        query += " ORDER BY e.fecha_ingreso DESC LIMIT 100"

        cur.execute(query, params)
        reparaciones = cur.fetchall()

    cur.close()

    return render_template(
        "reparaciones/listar_reparaciones.html",
        reparaciones=reparaciones,
        tecnicos=tecnicos,
        filtros={
            "cliente": cliente,
            "tecnico_id": tecnico_id,
            "estado": estado,
            "marca": marca,
            "modelo": modelo,
            "buscar": buscar
        }
    )


@reparacion_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista")
def crear_reparacion():
    empresa_id = session["empresa_id"]
    sucursal_id = session["sucursal_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        tecnico_id = request.form.get("tecnico_id") or None
        marca = request.form["marca"]
        modelo = request.form["modelo"]
        nro_serie = request.form["nro_serie"]
        descripcion_estado = request.form["descripcion_estado"]
        falla_declarada = request.form["falla_declarada"]
        fotos_antes = request.files.getlist("fotos_antes[]")
        fecha_turno = request.form.get("fecha_turno") or None

        mano_obra_id = request.form.get("mano_obra_id")
        precio_aplicado = request.form.get("precio_aplicado")

        try:
            cur.execute("""
                INSERT INTO equipos_reparacion (
                    empresa_id, sucursal_id, cliente_id, tecnico_id,
                    marca, modelo, nro_serie, descripcion_estado,
                    falla_declarada, estado
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente')
            """, (
                empresa_id, sucursal_id, cliente_id, tecnico_id,
                marca, modelo, nro_serie, descripcion_estado,
                falla_declarada
            ))

            equipo_id = cur.lastrowid

            for foto in fotos_antes:
                ruta_foto = guardar_foto(foto, "equipos_antes")
                if ruta_foto:
                    cur.execute("""
                        INSERT INTO fotos_reparacion (equipo_id, tipo, ruta)
                        VALUES (%s, 'antes', %s)
                    """, (equipo_id, ruta_foto))

            if mano_obra_id and precio_aplicado:
                cur.execute("""
                    INSERT INTO reparacion_mano_obra (
                        equipo_id, mano_obra_id, precio_aplicado
                    )
                    VALUES (%s, %s, %s)
                """, (equipo_id, mano_obra_id, precio_aplicado))

            if fecha_turno:
                cur.execute("""
                    INSERT INTO turnos (
                        empresa_id, sucursal_id, cliente_id, tecnico_id,
                        equipo_id, fecha_turno, estado, observacion,
                        recordatorio_1_dia, recordatorio_2_horas
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'pendiente', %s, 0, 0)
                """, (
                    empresa_id, sucursal_id, cliente_id, tecnico_id,
                    equipo_id, fecha_turno,
                    "Turno generado automáticamente al ingresar la reparación."
                ))

            mysql.connection.commit()
            flash("Reparación creada correctamente.", "success")
            return redirect(url_for("reparacion.detalle_reparacion", id=equipo_id))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear reparación: {e}", "danger")

        finally:
            cur.close()

    else:
        cur.execute("""
            SELECT id, nombre, apellido, dni
            FROM clientes
            WHERE empresa_id = %s AND activo = 1
            ORDER BY apellido, nombre
            LIMIT 100
        """, (empresa_id,))
        clientes = cur.fetchall()

        cur.execute("""
            SELECT u.id, u.nombre, u.apellido
            FROM usuarios u
            INNER JOIN roles r ON u.rol_id = r.id
            WHERE u.empresa_id = %s
            AND r.nombre = 'Tecnico'
            AND u.activo = 1
            ORDER BY u.apellido, u.nombre
        """, (empresa_id,))
        tecnicos = cur.fetchall()

        cur.execute("""
            SELECT id, nombre, precio_usd
            FROM mano_obra
            WHERE empresa_id = %s AND activo = 1
            ORDER BY nombre
        """, (empresa_id,))
        mano_obra = cur.fetchall()

        cur.close()

        return render_template(
            "reparaciones/crear_reparacion.html",
            clientes=clientes,
            tecnicos=tecnicos,
            mano_obra=mano_obra
        )


@reparacion_bp.route("/detalle/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def detalle_reparacion(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT 
            e.id,
            c.nombre,
            c.apellido,
            c.dni,
            c.telefono,
            e.marca,
            e.modelo,
            e.nro_serie,
            e.descripcion_estado,
            e.falla_declarada,
            e.foto_antes,
            e.foto_despues,
            e.estado,
            e.fecha_ingreso,
            e.fecha_entrega,
            u.nombre,
            u.apellido,
            e.firma_estado,
            e.fecha_firma,
            e.firma_cliente,
            e.token_firma
        FROM equipos_reparacion e
        INNER JOIN clientes c ON e.cliente_id = c.id
        LEFT JOIN usuarios u ON e.tecnico_id = u.id
        WHERE e.id = %s AND e.empresa_id = %s
    """, (id, empresa_id))

    reparacion = cur.fetchone()

    if not reparacion:
        cur.close()
        flash("Reparación no encontrada.", "danger")
        return redirect(url_for("reparacion.listar_reparaciones"))

    cur.execute("""
        SELECT id, nombre, precio_usd
        FROM mano_obra
        WHERE empresa_id = %s AND activo = 1
        ORDER BY nombre
    """, (empresa_id,))
    mano_obra = cur.fetchall()

    cur.execute("""
        SELECT 
            rm.id,
            mo.nombre,
            mo.descripcion,
            rm.precio_aplicado
        FROM reparacion_mano_obra rm
        INNER JOIN mano_obra mo ON rm.mano_obra_id = mo.id
        WHERE rm.equipo_id = %s
    """, (id,))
    mano_obra_aplicada = cur.fetchall()

    cur.execute("""
        SELECT COALESCE(SUM(precio_aplicado), 0)
        FROM reparacion_mano_obra
        WHERE equipo_id = %s
    """, (id,))
    total_mano_obra = cur.fetchone()[0]

    cur.execute("""
        SELECT id, ruta, fecha
        FROM fotos_reparacion
        WHERE equipo_id=%s AND tipo='antes'
        ORDER BY fecha ASC
    """, (id,))
    fotos_antes = cur.fetchall()

    cur.execute("""
        SELECT id, ruta, fecha
        FROM fotos_reparacion
        WHERE equipo_id=%s AND tipo='despues'
        ORDER BY fecha ASC
    """, (id,))
    fotos_despues = cur.fetchall()

    cur.execute("""
        SELECT id, fecha, diagnostico
        FROM fichas_tecnicas
        WHERE equipo_id=%s
        ORDER BY fecha DESC
    """, (id,))
    notas_tecnicas = cur.fetchall()

    cur.close()

    return render_template(
        "reparaciones/detalle_reparacion.html",
        reparacion=reparacion,
        mano_obra=mano_obra,
        mano_obra_aplicada=mano_obra_aplicada,
        total_mano_obra=total_mano_obra,
        fotos_antes=fotos_antes,
        fotos_despues=fotos_despues,
        notas_tecnicas=notas_tecnicas
    )


@reparacion_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def editar_reparacion(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        tecnico_id = request.form.get("tecnico_id") or None
        estado = request.form["estado"]
        descripcion_estado = request.form["descripcion_estado"]
        falla_declarada = request.form["falla_declarada"]
        fotos_despues = request.files.getlist("fotos_despues[]")

        try:
            cur.execute("""
                UPDATE equipos_reparacion
                SET tecnico_id=%s,
                    estado=%s,
                    descripcion_estado=%s,
                    falla_declarada=%s,
                    fecha_entrega = CASE
                        WHEN %s = 'entregado' THEN NOW()
                        ELSE fecha_entrega
                    END
                WHERE id=%s AND empresa_id=%s
            """, (
                tecnico_id, estado, descripcion_estado,
                falla_declarada,
                estado, id, empresa_id
            ))

            for foto in fotos_despues:
                ruta_foto = guardar_foto(foto, "equipos_despues")
                if ruta_foto:
                    cur.execute("""
                        INSERT INTO fotos_reparacion (equipo_id, tipo, ruta)
                        VALUES (%s, 'despues', %s)
                    """, (id, ruta_foto))

            mysql.connection.commit()
            flash("Reparación actualizada correctamente.", "success")
            return redirect(url_for("reparacion.detalle_reparacion", id=id))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al actualizar reparación: {e}", "danger")

        finally:
            cur.close()

    cur.execute("""
        SELECT
            id, tecnico_id, marca, modelo, nro_serie,
            descripcion_estado, falla_declarada,
            foto_antes, foto_despues, estado
        FROM equipos_reparacion
        WHERE id=%s AND empresa_id=%s
    """, (id, empresa_id))

    reparacion = cur.fetchone()

    cur.execute("""
        SELECT u.id, u.nombre, u.apellido
        FROM usuarios u
        INNER JOIN roles r ON u.rol_id = r.id
        WHERE u.empresa_id = %s
        AND r.nombre = 'Tecnico'
        AND u.activo = 1
        ORDER BY u.apellido, u.nombre
    """, (empresa_id,))
    tecnicos = cur.fetchall()

    if not reparacion:
        cur.close()
        flash("Reparación no encontrada.", "danger")
        return redirect(url_for("reparacion.listar_reparaciones"))

    cur.execute("""
        SELECT ruta FROM fotos_reparacion
        WHERE equipo_id=%s AND tipo='antes'
        ORDER BY fecha ASC
    """, (id,))
    fotos_antes = cur.fetchall()

    cur.execute("""
        SELECT ruta FROM fotos_reparacion
        WHERE equipo_id=%s AND tipo='despues'
        ORDER BY fecha ASC
    """, (id,))
    fotos_despues = cur.fetchall()

    cur.close()

    return render_template(
        "reparaciones/editar_reparacion.html",
        reparacion=reparacion,
        tecnicos=tecnicos,
        fotos_antes=fotos_antes,
        fotos_despues=fotos_despues
    )


@reparacion_bp.route("/<int:id>/agregar-mano-obra", methods=["POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Tecnico")
def agregar_mano_obra(id):
    empresa_id = session["empresa_id"]

    mano_obra_id = request.form["mano_obra_id"]
    precio_aplicado = request.form["precio_aplicado"]

    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            SELECT id
            FROM equipos_reparacion
            WHERE id = %s AND empresa_id = %s
        """, (id, empresa_id))

        reparacion = cur.fetchone()

        if not reparacion:
            flash("Reparación no encontrada.", "danger")
            return redirect(url_for("reparacion.listar_reparaciones"))

        cur.execute("""
            INSERT INTO reparacion_mano_obra (
                equipo_id, mano_obra_id, precio_aplicado
            )
            VALUES (%s, %s, %s)
        """, (id, mano_obra_id, precio_aplicado))

        mysql.connection.commit()
        flash("Mano de obra agregada correctamente.", "success")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al agregar mano de obra: {e}", "danger")

    finally:
        cur.close()

    return redirect(url_for("reparacion.detalle_reparacion", id=id))