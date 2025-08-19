# Implementación del Campo address_plus_code_url

## Resumen de la Implementación

Se ha añadido exitosamente el nuevo campo `property_location-address_plus_code_image` al sistema, siguiendo el patrón existente de `building_image_url`.

## Cambios Realizados

### 1. Modelos de Base de Datos (`okd_sync/db/sqlalchemy_models.py`)

- **MainSubmission**: Añadido campo `address_plus_code_url` (String)
- **UnifiedView**: Añadidos campos:
  - `address_plus_code_url` (String)
  - `address_plus_code_url_html` (String)

### 2. Parser ODK (`okd_sync/odk/parser.py`)

- **Nueva función**: `extract_address_plus_code(submission)`
  - Extrae el campo `address_plus_code_image` del objeto `property_location`
  - Maneja JSON strings y objetos dict
  - Incluye búsqueda alternativa en campos de nivel superior
- **Actualización**: Añadido `property_location` a la lista de campos JSON a procesar

### 3. Procesamiento S3 (`okd_sync/storage/s3.py`)

- **Nueva función**: `extract_address_plus_code(submission)` 
  - Duplica la lógica del parser para S3
- **Actualización**: `process_single_submission()`
  - Procesa tanto `building_image` como `address_plus_code`
  - Estructura de datos mejorada para manejar múltiples imágenes
  - Compatibilidad con formato anterior
- **Actualización**: Asignación de URLs mejorada con contadores separados

### 4. Vista Unificada (`okd_sync/db/sqlalchemy_operations.py`)

- **Actualización**: `create_unified_view()`
  - Añadido generación HTML para `address_plus_code_url_html`
  - Mismo formato HTML responsivo que `building_image_url_html`
  - Aplicado tanto en consulta simple como en consulta con person_details

## Flujo de Datos

```
ODK Central → property_location.address_plus_code_image → Parser → S3 Upload → Database → Unified View
```

## Nombres de Campos

- **Campo origen ODK**: `property_location-address_plus_code_image`
- **Campo en JSON**: `property_location.address_plus_code_image`
- **Campo URL en DB**: `address_plus_code_url`
- **Campo HTML en DB**: `address_plus_code_url_html`

## Compatibilidad

- ✅ Retrocompatible con datos existentes
- ✅ No afecta el procesamiento de `building_image`
- ✅ Mantiene la estructura de la vista unificada
- ✅ Funciona con el patrón de refresh de URLs existente

## Próximos Pasos

1. **Ejecutar migración de base de datos** (si es necesario)
2. **Probar con datos reales** del formulario ODK
3. **Verificar en Superset** que los nuevos campos aparecen correctamente
4. **Actualizar documentación** del sistema si es necesario

## Prueba Simple

```python
# Simular un submission con address_plus_code_image
test_submission = {
    'UUID': 'test-123',
    'property_location': {
        'address_plus_code_image': 'test_image.jpg'
    }
}

# Debería extraer 'test_image.jpg'
result = extract_address_plus_code(test_submission)
print(f"Extracted: {result}")
```

## Logging

El sistema ahora registra:
- `"Uploaded address_plus_code to S3 with signed URL: {s3_url}"`
- `"Updated {address_plus_code_count} submissions with address plus code URLs"`
- `"No address_plus_code found for submission {submission_id}"` (debug)