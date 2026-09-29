# 📱 Apple Hospital — Sistema de gestión para servicio técnico

Sistema web para talleres de reparación de celulares y tiendas de tecnología. Centraliza reparaciones, ventas, stock, facturación y equipo de trabajo en una sola aplicación, con soporte **multi-empresa / marca blanca** (cada negocio ve su propio nombre y logo).

## ✨ Funcionalidades

- **Reparaciones**: ingreso de equipos, estados, fichas técnicas con fotos y envío por email al cliente.
- **Firma digital**: el cliente firma la conformidad de una reparación o venta desde un link.
- **Ventas y facturación**: facturas de venta y de reparación con generación de **PDF**.
- **Stock y productos**: control de inventario, compras y proveedores.
- **Clientes, turnos y servicios**: agenda de turnos y catálogo de servicios / mano de obra.
- **Equipo**: empleados, roles y permisos, objetivos y comisiones.
- **Reportes y dashboard** con los indicadores del negocio.

## 🛠️ Tecnologías

- **Backend:** Python · Flask (blueprints, arquitectura rutas → servicios → modelos)
- **Base de datos:** MySQL (Flask-MySQLdb)
- **PDF:** ReportLab
- **Frontend:** HTML5 · Jinja2 · CSS

## 📂 Estructura

```
appy.py          # punto de entrada (create_app)
config.py        # configuración por variables de entorno
models/          # acceso a datos
routes/          # blueprints por módulo
services/        # lógica de negocio (stock, comisiones, PDF, email)
utils/           # decoradores, permisos, validadores
templates/       # vistas Jinja2
schema_limpio.sql
```

## 🚀 Cómo correrlo

```bash
python -m venv venv
venv\Scripts\activate        # en Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
```

1. Creá la base en MySQL importando `schema_limpio.sql`.
2. Definí las variables de entorno según `.env.example` (`MYSQL_PASSWORD`, `SECRET_KEY`, etc.).
3. Ejecutá `python appy.py` y entrá a http://127.0.0.1:5000

## 👤 Autor

**Enzo Fernández** — desarrollador web Python / Flask.
