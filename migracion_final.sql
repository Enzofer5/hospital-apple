-- ============================================================
-- Apple Hospital — Script único de migración final
-- Es seguro correrlo aunque ya hayas ejecutado algunas partes
-- antes: usa IF NOT EXISTS en todo, así que lo que ya existe
-- se salta solo y no rompe nada.
--
-- Requiere MySQL 8.0.29+ o MariaDB 10.0.2+ (soportan
-- "ADD COLUMN IF NOT EXISTS"). Si tu servidor es más viejo y
-- te tira error de sintaxis en alguna línea, avisame la versión
-- y te paso el equivalente sin esa cláusula.
--
-- HACÉ UN BACKUP DE LA BASE ANTES DE CORRER ESTO.
-- ============================================================

-- 1) Email propio de la empresa para enviar recordatorios/firmas/recuperación
ALTER TABLE empresas
    ADD COLUMN IF NOT EXISTS email_password_app VARCHAR(255) NULL;

-- 1b) Logo propio de cada empresa (marca blanca)
ALTER TABLE empresas
    ADD COLUMN IF NOT EXISTS logo VARCHAR(255) NULL;

-- 2) Recuperación de contraseña
CREATE TABLE IF NOT EXISTS recuperacion_password (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    token VARCHAR(64) NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion DATETIME NOT NULL,
    usado TINYINT(1) DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- 3) Fotos antes/después de la reparación
CREATE TABLE IF NOT EXISTS fotos_reparacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipo_id INT NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    ruta VARCHAR(255) NOT NULL,
    fecha_subida DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipo_id) REFERENCES equipos_reparacion(id)
);

-- 4) Servicios del negocio (luz, agua, gas, alquiler, etc.)
CREATE TABLE IF NOT EXISTS servicios_empresa (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    monto DECIMAL(10,2) DEFAULT 0,
    fecha_vencimiento DATE NOT NULL,
    estado VARCHAR(20) DEFAULT 'pendiente',
    observacion TEXT,
    fecha_pago DATETIME NULL,
    foto_factura VARCHAR(255) NULL,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

-- por si la tabla ya existía de una versión anterior sin estas columnas
ALTER TABLE servicios_empresa
    ADD COLUMN IF NOT EXISTS fecha_pago DATETIME NULL,
    ADD COLUMN IF NOT EXISTS foto_factura VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS es_recurrente TINYINT(1) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS dia_vencimiento TINYINT NULL;

-- 5) Modo estudiante (empleados)
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS modo_estudiante TINYINT(1) DEFAULT 0;

-- 6) Sueldo en dólares (por si quedó algún ambiente sin esta columna)
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS sueldo_usd DECIMAL(10,2) DEFAULT 0;

-- 7) Precios de productos en dólares
ALTER TABLE productos
    ADD COLUMN IF NOT EXISTS precio_costo_usd DECIMAL(10,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS precio_venta_usd DECIMAL(10,2) DEFAULT 0;

-- 8) Precio de mano de obra en dólares
ALTER TABLE mano_obra
    ADD COLUMN IF NOT EXISTS precio_usd DECIMAL(10,2) DEFAULT 0;

-- 9) Metas mensuales del negocio (Configuración)
CREATE TABLE IF NOT EXISTS metas_empresa (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    concepto VARCHAR(100) NOT NULL,
    monto DECIMAL(12,2) DEFAULT 0,
    UNIQUE KEY uq_empresa_concepto (empresa_id, concepto),
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

-- 10) Objetivos (bonos por cumplimiento)
CREATE TABLE IF NOT EXISTS objetivos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    usuario_id INT NULL,
    rol_id INT NULL,
    titulo VARCHAR(150) NOT NULL,
    descripcion TEXT,
    monto_bonus DECIMAL(10,2) DEFAULT 0,
    mes INT NOT NULL,
    anio INT NOT NULL,
    estado VARCHAR(20) DEFAULT 'pendiente',
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (rol_id) REFERENCES roles(id)
);

-- 11) Ayudas económicas (estudiantes)
CREATE TABLE IF NOT EXISTS ayudas_economicas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    usuario_id INT NOT NULL,
    monto DECIMAL(10,2) DEFAULT 0,
    moneda VARCHAR(3) DEFAULT 'USD',
    motivo VARCHAR(255),
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- ============================================================
-- FIN. Después de correr esto, reiniciá el servidor Flask.
-- ============================================================
