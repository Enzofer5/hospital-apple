import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from flask import current_app


def generar_pdf_factura(factura, detalles):
    carpeta = os.path.join(current_app.root_path, "static", "pdfs", "facturas")
    os.makedirs(carpeta, exist_ok=True)

    nombre_archivo = f"factura_{factura[1]}.pdf".replace("/", "-")
    ruta_completa = os.path.join(carpeta, nombre_archivo)

    c = canvas.Canvas(ruta_completa, pagesize=A4)
    ancho, alto = A4

    y = alto - 50

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "Hospital Apple")
    y -= 30

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Factura: {factura[1]}")
    y -= 20
    c.drawString(50, y, f"Tipo: {factura[2]}")
    y -= 20
    c.drawString(50, y, f"Concepto: {factura[3]}")
    y -= 20
    c.drawString(50, y, f"Fecha: {factura[8]}")
    y -= 35

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, "Cliente")
    y -= 20

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Nombre: {factura[9]} {factura[10]}")
    y -= 20
    c.drawString(50, y, f"DNI: {factura[11]}")
    y -= 20
    c.drawString(50, y, f"Email: {factura[12]}")
    y -= 20
    c.drawString(50, y, f"Teléfono: {factura[13]}")
    y -= 35

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, "Detalle")
    y -= 25

    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Descripción")
    c.drawString(300, y, "Cant.")
    c.drawString(360, y, "Precio")
    c.drawString(450, y, "Subtotal")
    y -= 15

    c.setFont("Helvetica", 10)

    for d in detalles:
        if y < 80:
            c.showPage()
            y = alto - 50

        descripcion = str(d[0])[:35]
        c.drawString(50, y, descripcion)
        c.drawString(300, y, str(d[1]))
        c.drawString(360, y, f"${d[2]}")
        c.drawString(450, y, f"${d[3]}")
        y -= 18

    y -= 25

    c.setFont("Helvetica-Bold", 12)
    c.drawString(360, y, f"Subtotal: ${factura[4]}")
    y -= 20
    c.drawString(360, y, f"Descuento: ${factura[5]}")
    y -= 20
    c.drawString(360, y, f"Total: ${factura[6]}")

    c.save()

    return f"pdfs/facturas/{nombre_archivo}"