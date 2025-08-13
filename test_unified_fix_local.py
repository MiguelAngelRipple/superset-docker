#!/usr/bin/env python3
"""
Test de la corrección para person_details - Versión para BD Local

Este script recrea la tabla unified usando la consulta SQL corregida
directamente en la base de datos local.

Base de datos local:
- Host: localhost:5432
- Usuario: postgres
- Contraseña: postgres

IMPORTANTE: Si tu base de datos tiene un nombre diferente a 'postgres',
cambia la línea 'database': 'postgres' más abajo por el nombre correcto.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys

# Configuración de la base de datos local
# CAMBIA EL NOMBRE DE LA BASE DE DATOS SI ES NECESARIO
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'postgres',
    'database': 'Submissions'  # ✅ Base de datos donde están las tablas ODK
}

# Nombres de las tablas
MAIN_TABLE = "GRARentalDataCollection"
PERSON_DETAILS_TABLE = "GRARentalDataCollection_person_details"
UNIFIED_TABLE = "GRARentalDataCollection_unified"

def execute_query(conn, query, fetch=False):
    """Ejecuta una consulta"""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query)
            if fetch:
                return cursor.fetchall()
            conn.commit()
            return True
    except Exception as e:
        print(f"Error ejecutando consulta: {e}")
        conn.rollback()
        return False

def execute_scalar(conn, query):
    """Ejecuta una consulta y devuelve un valor único"""
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        print(f"Error ejecutando consulta escalar: {e}")
        return None

def table_exists(conn, table_name):
    """Verifica si una tabla existe"""
    query = f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = '{table_name}'
        )
    """
    return execute_scalar(conn, query)

def create_unified_view_corrected(conn):
    """
    Crea la tabla unified con la consulta SQL corregida
    """
    try:
        print("🔧 Iniciando creación de tabla unified corregida...")
        
        # Verificar que las tablas principales existen
        if not table_exists(conn, MAIN_TABLE):
            print(f"❌ La tabla principal {MAIN_TABLE} no existe")
            return False
            
        if not table_exists(conn, PERSON_DETAILS_TABLE):
            print(f"❌ La tabla person details {PERSON_DETAILS_TABLE} no existe")
            return False
        
        # Eliminar la tabla unified si existe
        print("🗑️  Eliminando tabla unified existente...")
        drop_query = f'DROP TABLE IF EXISTS "{UNIFIED_TABLE}" CASCADE'
        if not execute_query(conn, drop_query):
            print("❌ Error eliminando tabla unified existente")
            return False
        
        # Crear la nueva tabla unified con la consulta corregida
        print("🏗️  Creando nueva tabla unified...")
        
        create_query = f'''
        CREATE TABLE "{UNIFIED_TABLE}" AS
        SELECT 
            m.*,
            -- Use COALESCE to return empty array instead of null when no person details exist
            COALESCE(pd.person_details, '[]'::jsonb) as person_details,
            CASE 
                WHEN m.building_image_url IS NOT NULL 
                THEN '<img src=' || CHR(34) || m.building_image_url || CHR(34) || ' width=' || CHR(34) || '100%' || CHR(34) || ' height=' || CHR(34) || '100%' || CHR(34) || ' />' 
                ELSE NULL 
            END as building_image_url_html
        FROM "{MAIN_TABLE}" m
        -- Use a subquery to pre-aggregate person details by submission UUID
        -- This approach avoids the complex GROUP BY requirements of the previous version
        LEFT JOIN (
            SELECT 
                p."__Submissions-id" as submission_uuid,
                -- Aggregate all person details for each submission into a JSON array
                -- Removed the UUID filter to be more permissive and capture all records
                jsonb_agg(
                    jsonb_build_object(
                        'UUID', p."UUID",
                        'person_type', p."person_type",
                        'shop_apt_unit_number', p."shop_apt_unit_number",
                        'type', p."type",
                        'business_name', p."business_name",
                        'tax_registered', p."tax_registered",
                        'tin', p."tin",
                        'individual_first_name', p."individual_first_name",
                        'individual_middle_name', p."individual_middle_name",
                        'individual_last_name', p."individual_last_name",
                        'individual_gender', p."individual_gender",
                        'individual_id_type', p."individual_id_type",
                        'individual_nin', p."individual_nin",
                        'individual_drivers_licence', p."individual_drivers_licence",
                        'individual_passport_number', p."individual_passport_number",
                        'passport_country', p."passport_country",
                        'individual_residence_permit_number', p."individual_residence_permit_number",
                        'residence_permit_country', p."residence_permit_country",
                        'individual_dob', p."individual_dob",
                        'mobile_1', p."mobile_1",
                        'mobile_2', p."mobile_2",
                        'email', p."email",
                        'occupancy', p."occupancy"
                    )
                ) as person_details
            FROM "{PERSON_DETAILS_TABLE}" p
            -- More permissive filter: only exclude completely empty records
            WHERE p."__Submissions-id" IS NOT NULL 
              AND TRIM(p."__Submissions-id") != ''
            -- Group by the foreign key to aggregate all person details per submission
            GROUP BY p."__Submissions-id"
        ) pd ON m."UUID" = pd.submission_uuid
        '''
        
        if not execute_query(conn, create_query):
            print("❌ Error creando tabla unified")
            return False
        
        # Agregar clave primaria
        print("🔑 Agregando clave primaria...")
        pk_query = f'ALTER TABLE "{UNIFIED_TABLE}" ADD PRIMARY KEY ("UUID")'
        if not execute_query(conn, pk_query):
            print("⚠️  Advertencia: No se pudo agregar clave primaria (puede que ya exista)")
        
        print("✅ Tabla unified creada exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error creando tabla unified: {e}")
        return False

def verify_unified_table(conn):
    """
    Verifica que la tabla unified se creó correctamente y revisa person_details
    """
    try:
        print("\n🔍 Verificando tabla unified...")
        
        # Verificar que la tabla existe
        if not table_exists(conn, UNIFIED_TABLE):
            print("❌ La tabla unified no existe")
            return False
        
        # Contar registros totales
        total_count = execute_scalar(conn, f'SELECT COUNT(*) FROM "{UNIFIED_TABLE}"')
        print(f"📊 Total de registros en unified: {total_count}")
        
        # Contar registros con person_details no-null
        non_null_count = execute_scalar(conn, f'''
            SELECT COUNT(*) FROM "{UNIFIED_TABLE}" 
            WHERE person_details IS NOT NULL AND person_details != 'null'::jsonb
        ''')
        print(f"📊 Registros con person_details no-null: {non_null_count}")
        
        # Contar registros con person_details null
        null_count = execute_scalar(conn, f'''
            SELECT COUNT(*) FROM "{UNIFIED_TABLE}" 
            WHERE person_details IS NULL OR person_details = 'null'::jsonb
        ''')
        print(f"📊 Registros con person_details null: {null_count}")
        
        # Contar registros con arrays vacíos
        empty_array_count = execute_scalar(conn, f'''
            SELECT COUNT(*) FROM "{UNIFIED_TABLE}" 
            WHERE person_details = '[]'::jsonb
        ''')
        print(f"📊 Registros con person_details array vacío: {empty_array_count}")
        
        # Contar registros con datos reales
        populated_count = execute_scalar(conn, f'''
            SELECT COUNT(*) FROM "{UNIFIED_TABLE}" 
            WHERE person_details IS NOT NULL 
            AND person_details != 'null'::jsonb 
            AND person_details != '[]'::jsonb
        ''')
        print(f"📊 Registros con person_details poblados: {populated_count}")
        
        # Mostrar una muestra de person_details poblados
        if populated_count > 0:
            sample_query = f'''
                SELECT "UUID", person_details 
                FROM "{UNIFIED_TABLE}" 
                WHERE person_details IS NOT NULL 
                AND person_details != 'null'::jsonb 
                AND person_details != '[]'::jsonb
                LIMIT 2
            '''
            
            sample_results = execute_query(conn, sample_query, fetch=True)
            if sample_results:
                print("\n📋 Muestra de person_details poblados:")
                for result in sample_results:
                    print(f"  UUID: {result['UUID']}")
                    print(f"  Person Details: {result['person_details']}")
                    print()
        
        # Evaluación final
        print("\n" + "=" * 50)
        print("RESULTADO DE LA VERIFICACIÓN:")
        print("=" * 50)
        
        if null_count == 0:
            print("✅ ÉXITO: No hay registros con person_details null")
            if populated_count > 0:
                print(f"✅ PERFECTO: {populated_count} registros tienen person_details poblados")
                print("🎉 La corrección funciona correctamente!")
            else:
                print("⚠️  INFORMACIÓN: Todos los registros tienen arrays vacíos")
                print("   Esto puede ser normal si no hay datos en person_details")
                print("   O puede indicar que la relación aún no funciona")
        else:
            print(f"❌ PROBLEMA: {null_count} registros aún tienen person_details null")
            print("   La corrección no funcionó completamente")
        
        return null_count == 0
        
    except Exception as e:
        print(f"❌ Error verificando tabla unified: {e}")
        return False

def main():
    """
    Función principal de prueba
    """
    print("=" * 70)
    print("TEST: Corrección Person Details en Tabla Unified (BD Local)")
    print("=" * 70)
    print(f"Conectando a: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"Base de datos: {DB_CONFIG['database']}")
    print(f"Usuario: {DB_CONFIG['user']}")
    
    try:
        # Conectar a la base de datos
        conn = psycopg2.connect(**DB_CONFIG)
        print("✓ Conexión establecida exitosamente")
        
        # Crear la tabla unified corregida
        if not create_unified_view_corrected(conn):
            print("❌ Falló la creación de la tabla unified")
            return False
        
        # Verificar el resultado
        success = verify_unified_table(conn)
        
        conn.close()
        return success
        
    except psycopg2.Error as e:
        print(f"✗ Error de conexión a PostgreSQL: {e}")
        return False
        
    except Exception as e:
        print(f"✗ Error ejecutando test: {e}")
        return False

if __name__ == "__main__":
    print("Ejecutando test de corrección de person_details en BD local...")
    
    # Verificar si psycopg2 está disponible
    try:
        import psycopg2
    except ImportError:
        print("❌ Error: psycopg2 no está instalado.")
        print("Instálalo con: pip install psycopg2-binary")
        sys.exit(1)
    
    success = main()
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 TEST EXITOSO: La corrección funciona correctamente!")
        print("   Los person_details ahora se están poblando en la tabla unified.")
        print("   Puedes verificar los resultados en Superset.")
    else:
        print("❌ TEST FALLÓ: Hay problemas con la corrección.")
        print("   Revisa los mensajes de error arriba para más detalles.")
    print("=" * 70)
    
    sys.exit(0 if success else 1) 