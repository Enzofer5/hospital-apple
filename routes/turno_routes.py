import calendar
import urllib.parse
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from extensions import mysql
from utils.decorators import login_requerido, roles_requeridos

turno_bp = Blueprint("turno", __name__, url_prefix="/turnos")

MESES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


def link_whatsapp(telefono, mensaje):
    """
    Arma un link wa.me para abrir WhatsApp con el mensaje ya escrito.
    Asume números de Argentina si el teléfono no viene con código de país.
    """
    if not telefono:
        return None

    solo_numeros = "".join(ch for ch in telefono if ch.isdigit())

    if not solo_numeros:
        return None

    if not solo_numeros.startswith("54"):
        solo_numeros = "549" + solo_numeros

    return f"https://wa.me/{solo_numeros}?text={urllib.parse.quote(mensaje)}"


@turno_bp.route("/calendario")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def calendario_turnos():
    empresa_id = session["empresa_id"]

    mes_param = request.args.get("mes")

    if mes_param:
        try:
            anio, mes = map(int, mes_param.split("-"))
        except (ValueError, AttributeError):
            hoy_inicial = date.today()
            anio, mes = hoy_inicial.year, hoy_inicial.month
    else:
        hoy_inicial = date.today()
        anio, mes = hoy_inicial.year, hoy_inicial.month

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT DAY(fecha_turno) AS dia, COUNT(*) AS cantidad
        FROM turnos
        WHERE empresa_id = %s
        AND MONTH(fecha_turno) = %s
        AND YEAR(fecha_turno) = %s
        GROUP BY DAY(fecha_turno)
    """, (empresa_id, mes, anio))
    turnos_por_dia = dict(cur.fetchall())
    cur.close()

    hoy = date.today()

    semanas = []
    for semana in calendar.Calendar(firstweekday=0).monthdayscalendar(anio, mes):
        fila = []
        for dia in semana:
            if dia == 0:
                fila.append(None)
            else:
                fila.append({
                    "numero": dia,
                    "fecha": f"{anio:04d}-{mes:02d}-{dia:02d}",
                    "cantidad": turnos_por_dia.get(dia, 0),
                    "es_hoy": (dia == hoy.day and mes == hoy.month and anio == hoy.year)
                })
        semanas.append(fila)

    mes_anterior = mes - 1
    anio_anterior = anio
    if mes_anterior == 0:
        mes_anterior = 12
        anio_anterior -= 1

    mes_siguiente = mes + 1
    anio_siguiente = anio
    if mes_siguiente == 13:
        mes_siguiente = 1
        anio_siguiente += 1

    return render_template(
        "turnos/calendario.html",
        semanas=semanas,
        anio=anio,
        mes=mes,
        nombre_mes=MESES_ES[mes],
        mes_anterior=f"{anio_anterior}-{mes_anterior:02d}",
        mes_siguiente=f"{anio_siguiente}-{mes_siguiente:02d}"
    )


@turno_bp.route("/", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def listar_turnos():
    empresa_id = session["empresa_id"]

    cliente = request.args.get("cliente", "")
    tecnico_id = request.args.get("tecnico_id", "")
    estado = request.args.get("estado", "")
    fecha_desde = request.args.get("fecha_desde", "")
    fecha_hasta = request.args.get("fecha_hasta", "")
    buscar = request.args.get("buscar", "")

    turnos = []

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
                t.id,
                t.fecha_turno,
                c.nombre,
                c.apellido,
                c.dni,
                c.telefono,
                u.nombre,
                u.apellido,
                t.estado,
                t.observacion,
                e.marca,
                e.modelo
            FROM turnos t
            INNER JOIN clientes c ON t.cliente_id = c.id
            LEFT JOIN usuarios u ON t.tecnico_id = u.id
            LEFT JOIN equipos_reparacion e ON t.equipo_id = e.id
            WHERE t.empresa_id = %s
        """

        params = [empresa_id]

        if cliente:
            query += " AND (c.nombre LIKE %s OR c.apellido LIKE %s OR c.dni LIKE %s)"
            params.extend([f"%{cliente}%", f"%{cliente}%", f"%{cliente}%"])

        if tecnico_id:
            query += " AND t.tecnico_id = %s"
            params.append(tecnico_id)

        if estado:
            query += " AND t.estado = %s"
            params.append(estado)

        if fecha_desde:
            query += " AND DATE(t.fecha_turno) >= %s"
            params.append(fecha_desde)

        if fecha_hasta:
            query += " AND DATE(t.fecha_turno) <= %s"
            params.append(fecha_hasta)

        query += " ORDER BY t.fecha_turno ASC LIMIT 100"

        cur.execute(query, params)
        turnos = cur.fetchall()

    cur.close()

    return render_template(
        "turnos/listar_turnos.html",
        turnos=turnos,
        tecnicos=tecnicos,
        filtros={
            "cliente": cliente,
            "tecnico_id": tecnico_id,
            "estado": estado,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "buscar": buscar
        }
    )


@turno_bp.route("/crear", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista")
def crear_turno():
    empresa_id = session["empresa_id"]
    sucursal_id = session["sucursal_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        tecnico_id = request.form.get("tecnico_id") or None
        equipo_id = request.form.get("equipo_id") or None
        fecha_turno = request.form["fecha_turno"]
        estado = request.form["estado"]
        observacion = request.form["observacion"]

        try:
            cur.execute("""
                INSERT INTO turnos (
                    empresa_id,
                    sucursal_id,
                    cliente_id,
                    tecnico_id,
                    equipo_id,
                    fecha_turno,
                    estado,
                    observacion,
                    recordatorio_1_dia,
                    recordatorio_2_horas
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
            """, (
                empresa_id,
                sucursal_id,
                cliente_id,
                tecnico_id,
                equipo_id,
                fecha_turno,
                estado,
                observacion
            ))

            mysql.connection.commit()
            flash("Turno creado correctamente.", "success")
            return redirect(url_for("turno.listar_turnos"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear turno: {e}", "danger")

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
            SELECT 
                e.id,
                c.nombre,
                c.apellido,
                e.marca,
                e.modelo,
                e.nro_serie
            FROM equipos_reparacion e
            INNER JOIN clientes c ON e.cliente_id = c.id
            WHERE e.empresa_id = %s
            AND e.estado != 'entregado'
            ORDER BY e.fecha_ingreso DESC
            LIMIT 100
        """, (empresa_id,))
        equipos = cur.fetchall()

        cur.close()

        return render_template(
            "turnos/crear_turno.html",
            clientes=clientes,
            tecnicos=tecnicos,
            equipos=equipos
        )


@turno_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def editar_turno(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    if request.method == "POST":
        tecnico_id = request.form.get("tecnico_id") or None
        equipo_id = request.form.get("equipo_id") or None
        fecha_turno = request.form["fecha_turno"]
        estado = request.form["estado"]
        observacion = request.form["observacion"]

        try:
            cur.execute("""
                UPDATE turnos
                SET tecnico_id=%s,
                    equipo_id=%s,
                    fecha_turno=%s,
                    estado=%s,
                    observacion=%s
                WHERE id=%s AND empresa_id=%s
            """, (
                tecnico_id,
                equipo_id,
                fecha_turno,
                estado,
                observacion,
                id,
                empresa_id
            ))

            mysql.connection.commit()
            flash("Turno actualizado correctamente.", "success")
            return redirect(url_for("turno.listar_turnos"))

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al actualizar turno: {e}", "danger")

        finally:
            cur.close()

    cur.execute("""
        SELECT 
            id,
            cliente_id,
            tecnico_id,
            equipo_id,
            fecha_turno,
            estado,
            observacion
        FROM turnos
        WHERE id=%s AND empresa_id=%s
    """, (id, empresa_id))

    turno = cur.fetchone()

    if not turno:
        cur.close()
        flash("Turno no encontrado.", "danger")
        return redirect(url_for("turno.listar_turnos"))

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
        SELECT 
            e.id,
            c.nombre,
            c.apellido,
            e.marca,
            e.modelo,
            e.nro_serie
        FROM equipos_reparacion e
        INNER JOIN clientes c ON e.cliente_id = c.id
        WHERE e.empresa_id = %s
        AND e.estado != 'entregado'
        ORDER BY e.fecha_ingreso DESC
        LIMIT 100
    """, (empresa_id,))
    equipos = cur.fetchall()

    cur.close()

    return render_template(
        "turnos/editar_turno.html",
        turno=turno,
        clientes=clientes,
        tecnicos=tecnicos,
        equipos=equipos
    )


@turno_bp.route("/eliminar/<int:id>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista")
def eliminar_turno(id):
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            DELETE FROM turnos
            WHERE id = %s AND empresa_id = %s
        """, (id, empresa_id))

        mysql.connection.commit()
        flash("Turno eliminado correctamente.", "success")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al eliminar turno: {e}", "danger")

    finally:
        cur.close()

    return redirect(url_for("turno.listar_turnos"))

@turno_bp.route("/recordatorios", methods=["GET"])
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista")
def recordatorios_turnos():
    empresa_id = session["empresa_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT
            t.id,
            t.fecha_turno,
            c.nombre,
            c.apellido,
            c.telefono,
            c.email,
            u.nombre,
            u.apellido,
            t.estado,
            t.recordatorio_1_dia,
            t.recordatorio_2_horas,
            t.observacion,
            eq.marca,
            eq.modelo
        FROM turnos t
        INNER JOIN clientes c ON t.cliente_id = c.id
        LEFT JOIN usuarios u ON t.tecnico_id = u.id
        LEFT JOIN equipos_reparacion eq ON t.equipo_id = eq.id
        WHERE t.empresa_id = %s
        AND t.estado IN ('pendiente', 'confirmado')
        AND (
            (
                t.fecha_turno BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 1 DAY)
                AND t.recordatorio_1_dia = 0
            )
            OR
            (
                t.fecha_turno BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 2 HOUR)
                AND t.recordatorio_2_horas = 0
            )
        )
        ORDER BY t.fecha_turno ASC
    """, (empresa_id,))

    filas = cur.fetchall()
    cur.close()

    turnos = []

    for f in filas:
        nombre_cliente = f[2]
        fecha_txt = f[1].strftime("%d/%m/%Y a las %H:%M") if f[1] else ""
        equipo_txt = f" de tu {f[12]} {f[13]}" if f[12] else ""

        mensaje_1_dia = (
            f"Hola {nombre_cliente}! Te recordamos que tenés un turno el {fecha_txt} "
            f"para la reparación{equipo_txt} en Apple Hospital. Cualquier duda, escribinos por acá. ¡Gracias!"
        )

        mensaje_2_horas = (
            f"Hola {nombre_cliente}! Tu turno para la reparación{equipo_txt} es hoy {fecha_txt}. "
            f"¿Vas a poder asistir? Respondé por acá para confirmarnos. ¡Gracias!"
        )

        turnos.append({
            "id": f[0],
            "fecha_turno": f[1],
            "cliente": f"{f[2]} {f[3]}",
            "telefono": f[4],
            "email": f[5],
            "tecnico": f"{f[6] or 'Sin'} {f[7] or 'asignar'}",
            "estado": f[8],
            "recordatorio_1_dia": f[9],
            "recordatorio_2_horas": f[10],
            "observacion": f[11],
            "wa_link_1_dia": link_whatsapp(f[4], mensaje_1_dia),
            "wa_link_2_horas": link_whatsapp(f[4], mensaje_2_horas),
        })

    return render_template(
        "turnos/recordatorios_turnos.html",
        turnos=turnos
    )


@turno_bp.route("/recordatorios/marcar/<int:id>/<tipo>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista")
def marcar_recordatorio(id, tipo):
    empresa_id = session["empresa_id"]

    if tipo not in ["1_dia", "2_horas"]:
        flash("Tipo de recordatorio inválido.", "danger")
        return redirect(url_for("turno.recordatorios_turnos"))

    campo = "recordatorio_1_dia" if tipo == "1_dia" else "recordatorio_2_horas"

    cur = mysql.connection.cursor()

    cur.execute(f"""
        UPDATE turnos
        SET {campo} = 1
        WHERE id = %s AND empresa_id = %s
    """, (id, empresa_id))

    mysql.connection.commit()
    cur.close()

    flash("Recordatorio marcado como enviado.", "success")
    return redirect(url_for("turno.recordatorios_turnos"))

@turno_bp.route("/cambiar-estado/<int:id>/<estado>")
@login_requerido
@roles_requeridos("Dueño", "Socio", "Recepcionista", "Tecnico")
def cambiar_estado_turno(id, estado):
    empresa_id = session["empresa_id"]

    estados_validos = ["pendiente", "confirmado", "cancelado", "asistio", "no_asistio"]

    if estado not in estados_validos:
        flash("Estado inválido.", "danger")
        return redirect(url_for("turno.listar_turnos"))

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE turnos
        SET estado = %s
        WHERE id = %s AND empresa_id = %s
    """, (estado, id, empresa_id))

    mysql.connection.commit()
    cur.close()

    flash("Estado del turno actualizado correctamente.", "success")
    return redirect(url_for("turno.listar_turnos", buscar="1"))