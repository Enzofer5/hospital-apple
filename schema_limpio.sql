
CREATE DATABASE IF NOT EXISTS hospital_apple;
USE hospital_apple;

-- ---------- SaaS: planes y suscripciones ----------

CREATE TABLE planes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    precio DECIMAL(12,2) NOT NULL,
    duracion_dias INT NOT NULL,
    descripcion TEXT,
    activo TINYINT DEFAULT 1
);

CREATE TABLE empresas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    cuit VARCHAR(30),
    email VARCHAR(120),
    email_password_app VARCHAR(255) NULL,
    logo VARCHAR(255) NULL,
    telefono VARCHAR(30),
    direccion VARCHAR(150),
    estado ENUM('activa','suspendida','vencida') DEFAULT 'activa',
    fecha_alta DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE suscripciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    plan_id INT NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    estado ENUM('activa','vencida','cancelada') DEFAULT 'activa',
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (plan_id) REFERENCES planes(id)
);

CREATE TABLE pagos_suscripcion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    suscripcion_id INT NOT NULL,
    monto DECIMAL(12,2) NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    fecha_pago DATETIME DEFAULT CURRENT_TIMESTAMP,
    metodo_pago VARCHAR(50),
    comprobante VARCHAR(255),
    FOREIGN KEY (suscripcion_id) REFERENCES suscripciones(id)
);

-- ---------- Empresa: sucursales, roles y usuarios ----------

CREATE TABLE sucursales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    direccion VARCHAR(150),
    telefono VARCHAR(30),
    activo TINYINT DEFAULT 1,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO roles (nombre) VALUES
    ('Dueño'), ('Socio'), ('Administracion'), ('Vendedor'),
    ('Recepcionista'), ('Tecnico'), ('Cajero'),
    ('Atención al público'), ('Marketing');

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    sucursal_id INT,
    rol_id INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    dni VARCHAR(30),
    email VARCHAR(120) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    telefono VARCHAR(30),
    sueldo_ars DECIMAL(12,2) DEFAULT 0,
    sueldo_usd DECIMAL(12,2) DEFAULT 0,
    porcentaje_comision DECIMAL(5,2) DEFAULT 0,
    modo_estudiante TINYINT DEFAULT 0,
    activo TINYINT DEFAULT 1,
    fecha_alta DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id),
    FOREIGN KEY (rol_id) REFERENCES roles(id)
);

CREATE TABLE recuperacion_password (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    token VARCHAR(64) NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion DATETIME NOT NULL,
    usado TINYINT(1) DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- ---------- Clientes y proveedores ----------

CREATE TABLE clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    dni VARCHAR(30),
    email VARCHAR(120),
    telefono VARCHAR(30),
    fecha_nacimiento DATE,
    direccion VARCHAR(150),
    localidad VARCHAR(100),
    observaciones TEXT,
    email_confirmado TINYINT DEFAULT 0,
    activo TINYINT DEFAULT 1,
    fecha_alta DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    INDEX idx_clientes_empresa (empresa_id, activo)
);

CREATE TABLE proveedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nombre VARCHAR(120) NOT NULL,
    cuit VARCHAR(30),
    email VARCHAR(120),
    telefono VARCHAR(30),
    direccion VARCHAR(150),
    activo TINYINT DEFAULT 1,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

-- ---------- Catálogo: categorías, productos, mano de obra, stock ----------

CREATE TABLE categorias_producto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    activo TINYINT DEFAULT 1,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

CREATE TABLE cotizacion_dolar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    tipo ENUM('Oficial','Blue','MEP','CCL','Tarjeta') DEFAULT 'Blue',
    valor DECIMAL(12,2) NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

CREATE TABLE productos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    proveedor_id INT,
    categoria_id INT,
    marca VARCHAR(100) NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    descripcion TEXT,
    -- precio_costo_ars / precio_venta_ars quedan sin uso desde la
    -- migración a dólares (el sistema factura solo en USD), pero se
    -- mantienen para no perder el historial de precios en pesos.
    precio_costo_ars DECIMAL(12,2) DEFAULT 0,
    precio_venta_ars DECIMAL(12,2) DEFAULT 0,
    precio_costo_usd DECIMAL(12,2) DEFAULT 0,
    precio_venta_usd DECIMAL(12,2) DEFAULT 0,
    foto VARCHAR(255),
    activo TINYINT DEFAULT 1,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id),
    FOREIGN KEY (categoria_id) REFERENCES categorias_producto(id),
    INDEX idx_productos_empresa (empresa_id, activo)
);

CREATE TABLE stock (
    id INT AUTO_INCREMENT PRIMARY KEY,
    producto_id INT NOT NULL,
    sucursal_id INT NOT NULL,
    cantidad INT NOT NULL DEFAULT 0,
    UNIQUE (producto_id, sucursal_id),
    FOREIGN KEY (producto_id) REFERENCES productos(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id),
    INDEX idx_stock_producto_sucursal (producto_id, sucursal_id)
);

CREATE TABLE movimientos_stock (
    id INT AUTO_INCREMENT PRIMARY KEY,
    producto_id INT NOT NULL,
    sucursal_id INT NOT NULL,
    usuario_id INT,
    tipo ENUM('ingreso','venta','plan_canje','ajuste','reparacion') NOT NULL,
    cantidad INT NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    observacion TEXT,
    FOREIGN KEY (producto_id) REFERENCES productos(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE medios_cobro (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nombre VARCHAR(80) NOT NULL,
    activo TINYINT DEFAULT 1,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

CREATE TABLE mano_obra (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nombre VARCHAR(120) NOT NULL,
    descripcion TEXT,
    -- precio_ars: mismo caso que en productos, queda dormant.
    precio_ars DECIMAL(12,2) DEFAULT 0,
    precio_usd DECIMAL(12,2) DEFAULT 0,
    tiempo_estimado VARCHAR(50),
    activo TINYINT DEFAULT 1,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

-- ---------- Ventas ----------

CREATE TABLE ventas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    sucursal_id INT NOT NULL,
    cliente_id INT NOT NULL,
    vendedor_id INT NOT NULL,
    tipo_venta ENUM('directa','plan_canje') NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    cotizacion_dolar DECIMAL(12,2),
    subtotal DECIMAL(12,2) DEFAULT 0,
    descuento DECIMAL(12,2) DEFAULT 0,
    total DECIMAL(12,2) NOT NULL,
    estado ENUM('pendiente','pagada','cancelada') DEFAULT 'pendiente',
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    observacion TEXT,
    token_firma VARCHAR(255),
    firma_cliente VARCHAR(255),
    firma_estado ENUM('pendiente','firmado') DEFAULT 'pendiente',
    fecha_firma DATETIME,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (vendedor_id) REFERENCES usuarios(id),
    INDEX idx_ventas_empresa_fecha (empresa_id, fecha),
    INDEX idx_ventas_sucursal_fecha (sucursal_id, fecha)
);

CREATE TABLE detalle_venta (
    id INT AUTO_INCREMENT PRIMARY KEY,
    venta_id INT NOT NULL,
    producto_id INT NOT NULL,
    cantidad INT NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    precio_unitario DECIMAL(12,2) NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

CREATE TABLE plan_canje (
    id INT AUTO_INCREMENT PRIMARY KEY,
    venta_id INT NOT NULL,
    marca_entrega VARCHAR(100) NOT NULL,
    modelo_entrega VARCHAR(100) NOT NULL,
    nro_serie_entrega VARCHAR(100),
    estado_equipo TEXT,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    valor_tomado DECIMAL(12,2) NOT NULL,
    importe_abona_cliente DECIMAL(12,2) NOT NULL,
    foto_equipo VARCHAR(255),
    FOREIGN KEY (venta_id) REFERENCES ventas(id)
);

-- ---------- Reparaciones ----------

CREATE TABLE equipos_reparacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    sucursal_id INT NOT NULL,
    cliente_id INT NOT NULL,
    tecnico_id INT,
    marca VARCHAR(100) NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    nro_serie VARCHAR(100),
    descripcion_estado TEXT,
    falla_declarada TEXT,
    foto_antes VARCHAR(255),
    foto_despues VARCHAR(255),
    estado ENUM('pendiente','realizado','para_entregar','entregado') DEFAULT 'pendiente',
    fecha_ingreso DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_entrega DATETIME,
    token_firma VARCHAR(255),
    firma_cliente VARCHAR(255),
    firma_estado ENUM('pendiente','firmado') DEFAULT 'pendiente',
    fecha_firma DATETIME,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (tecnico_id) REFERENCES usuarios(id),
    INDEX idx_reparaciones_estado (empresa_id, estado),
    INDEX idx_reparaciones_tecnico (tecnico_id, estado)
);

CREATE TABLE fotos_reparacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipo_id INT NOT NULL,
    tipo ENUM('antes','despues') NOT NULL,
    ruta VARCHAR(255) NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id)
);

CREATE TABLE reparacion_mano_obra (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipo_id INT NOT NULL,
    mano_obra_id INT NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    precio_aplicado DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id),
    FOREIGN KEY (mano_obra_id) REFERENCES mano_obra(id)
);

CREATE TABLE reparacion_repuestos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipo_id INT NOT NULL,
    producto_id INT NOT NULL,
    cantidad INT NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    precio_unitario DECIMAL(12,2) NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

CREATE TABLE fichas_tecnicas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipo_id INT NOT NULL,
    tecnico_id INT,
    diagnostico TEXT,
    notas_tecnicas TEXT,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    costo_mano_obra DECIMAL(12,2) DEFAULT 0,
    costo_repuestos DECIMAL(12,2) DEFAULT 0,
    total DECIMAL(12,2) DEFAULT 0,
    pdf_generado VARCHAR(255),
    enviado_email TINYINT DEFAULT 0,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id),
    FOREIGN KEY (tecnico_id) REFERENCES usuarios(id)
);

CREATE TABLE fotos_ficha_tecnica (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ficha_id INT NOT NULL,
    ruta VARCHAR(255) NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ficha_id) REFERENCES fichas_tecnicas(id)
);

CREATE TABLE solicitudes_firma (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    cliente_id INT NOT NULL,
    venta_id INT,
    equipo_id INT,
    tipo ENUM('venta','reparacion') NOT NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    estado ENUM('pendiente','firmado','vencido') DEFAULT 'pendiente',
    firma_imagen VARCHAR(255),
    fecha_envio DATETIME,
    fecha_firma DATETIME,
    fecha_vencimiento DATETIME,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id),
    INDEX idx_firmas_token (token)
);

-- ---------- Pagos, compras y facturación ----------

CREATE TABLE pagos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    venta_id INT,
    equipo_id INT,
    medio_cobro_id INT NOT NULL,
    cajero_id INT,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    cotizacion_dolar DECIMAL(12,2),
    monto DECIMAL(12,2) NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    observacion TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id),
    FOREIGN KEY (medio_cobro_id) REFERENCES medios_cobro(id),
    FOREIGN KEY (cajero_id) REFERENCES usuarios(id),
    INDEX idx_pagos_empresa_fecha (empresa_id, fecha)
);

CREATE TABLE compras (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    sucursal_id INT NOT NULL,
    proveedor_id INT NOT NULL,
    usuario_id INT NOT NULL,
    numero_factura VARCHAR(80),
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    cotizacion_dolar DECIMAL(12,2),
    total DECIMAL(12,2) NOT NULL DEFAULT 0,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    observacion TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id),
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    INDEX idx_compras_empresa_fecha (empresa_id, fecha)
);

CREATE TABLE detalle_compra (
    id INT AUTO_INCREMENT PRIMARY KEY,
    compra_id INT NOT NULL,
    producto_id INT NOT NULL,
    cantidad INT NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    precio_costo DECIMAL(12,2) NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (compra_id) REFERENCES compras(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);

CREATE TABLE facturas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    sucursal_id INT NOT NULL,
    cliente_id INT NOT NULL,
    venta_id INT,
    equipo_id INT,
    numero VARCHAR(50) NOT NULL,
    tipo ENUM('A','B','C','X') DEFAULT 'X',
    concepto ENUM('venta','reparacion','mixta') NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    cotizacion_dolar DECIMAL(12,2),
    subtotal DECIMAL(12,2) DEFAULT 0,
    descuento DECIMAL(12,2) DEFAULT 0,
    total DECIMAL(12,2) NOT NULL,
    estado ENUM('emitida','anulada') DEFAULT 'emitida',
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    pdf VARCHAR(255),
    enviado_email TINYINT DEFAULT 0,
    cae VARCHAR(50),
    cae_vencimiento DATE,
    qr_afip TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id),
    INDEX idx_facturas_empresa_fecha (empresa_id, fecha)
);

CREATE TABLE detalle_factura (
    id INT AUTO_INCREMENT PRIMARY KEY,
    factura_id INT NOT NULL,
    producto_id INT,
    mano_obra_id INT,
    descripcion VARCHAR(255) NOT NULL,
    cantidad INT DEFAULT 1,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    precio_unitario DECIMAL(12,2) NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (factura_id) REFERENCES facturas(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id),
    FOREIGN KEY (mano_obra_id) REFERENCES mano_obra(id)
);

CREATE TABLE cotizaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    sucursal_id INT NOT NULL,
    cliente_id INT NOT NULL,
    usuario_id INT NOT NULL,
    venta_id INT,
    equipo_id INT,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    cotizacion_dolar DECIMAL(12,2),
    total DECIMAL(12,2) NOT NULL,
    estado ENUM('pendiente','aprobada','rechazada','vencida') DEFAULT 'pendiente',
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_vencimiento DATE,
    observacion TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id)
);

CREATE TABLE detalle_cotizacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cotizacion_id INT NOT NULL,
    producto_id INT,
    mano_obra_id INT,
    descripcion VARCHAR(255),
    cantidad INT DEFAULT 1,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    precio_unitario DECIMAL(12,2) NOT NULL,
    subtotal DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id),
    FOREIGN KEY (producto_id) REFERENCES productos(id),
    FOREIGN KEY (mano_obra_id) REFERENCES mano_obra(id)
);

-- ---------- Agenda ----------

CREATE TABLE turnos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    sucursal_id INT NOT NULL,
    cliente_id INT NOT NULL,
    tecnico_id INT,
    equipo_id INT,
    fecha_turno DATETIME NOT NULL,
    estado ENUM('pendiente','confirmado','cancelado','asistio','no_asistio') DEFAULT 'pendiente',
    recordatorio_1_dia TINYINT DEFAULT 0,
    recordatorio_2_horas TINYINT DEFAULT 0,
    observacion TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (tecnico_id) REFERENCES usuarios(id),
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id),
    INDEX idx_turnos_fecha (empresa_id, fecha_turno)
);

-- ---------- Gastos del negocio: servicios recurrentes y gastos fijos ----------

CREATE TABLE servicios_empresa (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    monto DECIMAL(12,2) NULL,
    fecha_vencimiento DATE NOT NULL,
    estado ENUM('pendiente','pagado') NOT NULL DEFAULT 'pendiente',
    observacion VARCHAR(255) NULL,
    fecha_pago DATETIME NULL,
    foto_factura VARCHAR(255) NULL,
    es_recurrente TINYINT(1) DEFAULT 0,
    dia_vencimiento TINYINT NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

CREATE TABLE gastos_fijos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    sucursal_id INT,
    concepto VARCHAR(120) NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    monto DECIMAL(12,2) NOT NULL,
    fecha DATE NOT NULL,
    observacion TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (sucursal_id) REFERENCES sucursales(id)
);

-- ---------- RRHH: metas, objetivos, comisiones, ayudas, sueldos ----------

CREATE TABLE metas_empresa (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    concepto VARCHAR(100) NOT NULL,
    monto DECIMAL(12,2) NOT NULL DEFAULT 0,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    UNIQUE KEY uq_empresa_concepto (empresa_id, concepto)
);

CREATE TABLE objetivos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    usuario_id INT NULL,
    rol_id INT NULL,
    titulo VARCHAR(150) NOT NULL,
    descripcion TEXT,
    monto_bonus DECIMAL(12,2) NOT NULL DEFAULT 0,
    mes INT NOT NULL,
    anio INT NOT NULL,
    estado ENUM('pendiente','cumplido') DEFAULT 'pendiente',
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_cumplido DATETIME NULL,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (rol_id) REFERENCES roles(id)
);

CREATE TABLE comisiones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    venta_id INT,
    equipo_id INT,
    tipo ENUM('venta','reparacion') NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    porcentaje DECIMAL(5,2) NOT NULL,
    monto DECIMAL(12,2) NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    estado ENUM('pendiente','pagada') DEFAULT 'pendiente',
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (venta_id) REFERENCES ventas(id),
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id)
);

CREATE TABLE pagos_empleados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    monto DECIMAL(12,2) NOT NULL,
    tipo ENUM('sueldo','comision','adelanto') NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    observacion TEXT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE ayudas_economicas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    usuario_id INT NOT NULL,
    monto DECIMAL(12,2) NOT NULL,
    moneda ENUM('ARS','USD') DEFAULT 'ARS',
    motivo VARCHAR(255),
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- ---------- Auditoría ----------

CREATE TABLE auditoria (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT,
    usuario_id INT,
    accion VARCHAR(120) NOT NULL,
    tabla_afectada VARCHAR(80),
    registro_id INT,
    detalle TEXT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- ============================================================
-- FIN. 43 tablas, mismos nombres y columnas que tu base actual
-- (menos usuarios.token_recuperacion/token_expiracion, sin uso),
-- ya con todo lo que antes eran ALTER TABLE incorporado de fábrica.
-- ============================================================
