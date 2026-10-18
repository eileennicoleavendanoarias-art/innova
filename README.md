# INNOVA — Tienda Web & Panel de Administración

Sistema de comercio electrónico y gestión privada para **INNOVA**, desarrollado con tecnologías nativas, persistencia en base de datos relacional SQLite, panel de control administrativo, sincronización en tiempo real y seguridad reforzada.

---

##  Inicio Rápido

### 1. Iniciar el Servidor Web
Haz doble clic sobre el archivo `start.bat` o ejecuta en tu terminal:

```bash
python server.py
```
*(Si utilizas el entorno de JetBrains u otra ruta personalizada de Python, `start.bat` lo detectará de forma automática).*

Una vez iniciado:
- **Tienda Pública:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Panel Administrativo:** [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)

---

### 2. Crear o Gestionar el Usuario Administrador
Por razones de seguridad, las contraseñas nunca se almacenan en texto plano ni se publican en el repositorio. Para crear o actualizar un administrador de forma segura:

Haz doble clic en `create_admin.bat` o ejecuta:

```bash
# Modo interactivo (solicita usuario, correo y contraseña oculta):
python create_admin.py

# O especificando parámetros directamente:
python create_admin.py --username admin --email admin@innova.com --password "TuContraseñaSegura123!"

# O generando una contraseña aleatoria de alta entropía:
python create_admin.py --username admin --generate-password
```

---

##  Resumen de Implementación

### Fase 1 & 2: Corrección Visual del Logo
- Se analizó el origen del punto en el logo. El punto provenía de un elemento tipográfico `<span class="wordmark-dot">.</span>` colocado directamente en el marcado HTML junto al imagotipo y la marca.
- Se eliminó `<span class="wordmark-dot">.</span>` tanto en el encabezado (`header`) como en el pie de página (`footer`), y se limpió la regla no utilizada en `styles.css`.
- El isotipo del perro (`assets/innova-mark.png`) se conservó al 100% en sus trazados geométricos, proporciones, resolución y transparencia sin alteraciones.

### Fase 3: Panel Privado de Administración (`/admin`)
- Interfaz moderna, limpia y responsive con navegación lateral intuitiva y diseño oscuro alineado a la estética de lujo de INNOVA.
- Sistema de autenticación con sesiones seguras basadas en cookies `HttpOnly; SameSite=Strict; Path=/`.
- Hash criptográfico de contraseñas mediante **PBKDF2-HMAC-SHA256** con 600.000 iteraciones y sal aleatoria de 16 bytes.
- Protección activa contra fuerza bruta (bloqueo automático tras 5 intentos fallidos en 15 minutos con código HTTP 429).
- Dashboard analítico con métricas en tiempo real:
  - Total de productos
  - Productos activos
  - Productos agotados
  - Productos con stock bajo
  - Promociones activas hoy
  - Tabla de últimos productos añadidos
  - Tabla de últimos movimientos de inventario

### Fase 4: Gestión de Productos
- Operaciones completas **CRUD** (Crear, Consultar, Modificar, Eliminar con ventana de confirmación).
- Búsqueda en tiempo real por nombre, SKU o descripción.
- Filtros por categoría, estado (`activo`, `inactivo`, `borrador`) y ordenación (destacados, precio menor/mayor, stock, alfabético).
- Formulario de edición con:
  - Nombre, SKU, categoría, descripciones corta y detallada.
  - Precio normal y precio promocional opcional (con cálculo y visualización automática del porcentaje de descuento y advertencia si el promocional supera el normal).
  - Cantidad de existencias.
  - Lista dinámica de especificaciones técnicas.
  - Gestor de fotografías: subida de archivos locales (PNG, JPG, WebP, GIF) con almacenamiento persistente en `/uploads/`, asignación de fotografía principal y previsualización.

### Fase 5: Control de Inventario y Stock
- Vista dedicada de existencias con filtros por estado: Todos, Con Stock, Stock Bajo y Agotados.
- Controles de ajuste rápido (`-1`, `+1`, `+5`, `Agotar`).
- Modal de ajuste detallado con opciones para:
  - Sumar unidades (recepción de mercancía)
  - Restar unidades (merma, devolución)
  - Establecer cantidad exacta (conteo físico)
  - Registro de motivo obligatorio.
- **Prevención de stock negativo:** el servidor rechaza cualquier operación que lleve el stock por debajo de 0.
- **Auditoría completa:** Cada ajuste genera un registro inmutable en `stock_movements` con stock anterior, nuevo, diferencia, motivo, usuario responsable y marca de tiempo.
- Cuando el stock llega a 0, el producto se marca automáticamente como **Agotado** y se deshabilita para compra disponible.

### Fase 6: Módulo de Promociones y Descuentos
- Creación y edición de campañas de descuento por:
  - Porcentaje (`%`)
  - Monto fijo en pesos (`$ COP`)
- Alcance configurable:
  - Global (todos los productos de la tienda)
  - Por categoría específica
  - Por producto específico
- Programación de fecha y hora de inicio y fin (`starts_at`, `ends_at`).
- Detección automática en servidor de promociones vigentes, programadas y vencidas.
- Las promociones vencidas dejan de aplicarse automáticamente sin intervención manual.

### Fase 7: Sincronización con la Tienda Pública
- `app.js` consulta directamente los endpoints `/api/products` y `/api/settings` de forma reactiva.
- Precios con descuento muestran el precio original tachado y la etiqueta de ahorro (ej. `-20%`).
- Los productos agotados muestran la insignia "Agotado" en la tarjeta y en la ventana modal de detalles.
- Botón de WhatsApp sincronizado dinámicamente: incluye el nombre del producto, referencia y precio vigente en el mensaje predeterminado.
- **Tolerancia a fallos:** Si el backend no está activo o la página se abre como archivo estático local, la tienda pública utiliza como respaldo automático `catalog-data.js` para nunca romperse.

### Fase 8: Categorías
- Creación, modificación y visualización de categorías con conteo de productos vinculados.
- Protección relacional: el sistema impide eliminar categorías que contengan productos asociados para evitar registros huérfanos.

### Fase 9: Configuración General
- Nombre comercial y eslogan de la tienda.
- Enlace directo comercial de WhatsApp y teléfono visible.
- Correo de contacto.
- Código y símbolo de moneda (predeterminado: COP / `$`).
- Umbral configurable de inventario bajo (predeterminado: 5 unidades).
- Mensaje o aviso de la tienda.

### Fase 10: Base de Datos Relacional y Persistencia
- Motor: **SQLite 3** en modo WAL (*Write-Ahead Logging*) con soporte de claves foráneas e índices optimizados.
- Ubicación del archivo de base de datos: `data/innova.db`.
- Migración y sembrado inicial automático desde `catalog-data.js` para conservar todos los productos demo previos sin pérdida de datos.

### Fase 12: Seguridad Web
- Consultas SQL 100% parametrizadas (inmune a inyección SQL).
- Almacenamiento seguro de contraseñas con sal y PBKDF2 (inmune a rainbow tables).
- Validación de archivos subidos por firma de bytes (Magic Bytes) impidiendo ejecución de scripts.
- Asignación de nombres UUID aleatorios para archivos en `/uploads/` previniendo ataques de Path Traversal (`../`).
- Cabeceras de seguridad activas en todas las respuestas HTTP (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`).

---

## 🧪 Pruebas Automatizadas

El proyecto incluye una suite completa de pruebas unitarias y de integración en `tests/test_innova.py`.

Para ejecutar las pruebas:
```bash
python tests/test_innova.py
```

### Casos evaluados:
1. `test_logo_dot_eliminated_from_html_and_css`: Verifica ausencia total del punto en header y footer.
2. `test_password_hashing_security`: Comprueba unicidad de sales y verificación de contraseñas.
3. `test_database_tables_and_seeds`: Comprueba persistencia de tablas y productos iniciales.
4. `test_auth_flow_login_me_logout`: Evalúa el ciclo completo de autenticación y sesiones.
5. `test_auth_brute_force_rate_limit`: Comprueba el bloqueo HTTP 429 tras 5 intentos fallidos.
6. `test_product_crud_and_validation`: Evalúa validaciones de precio, inventario, creación, edición y borrado.
7. `test_inventory_adjustments_and_movements`: Comprueba ajustes de stock, prevención de valores negativos y auditoría.
8. `test_promotions_and_pricing_rules`: Evalúa descuentos porcentuales, fijos y caducidad temporal.
9. `test_category_deletion_protection`: Verifica protección relacional en categorías con productos.
10. `test_file_upload_security`: Evalúa validación de firmas de archivo, rechazo de texto/scripts y subida de PNGs válidos.

