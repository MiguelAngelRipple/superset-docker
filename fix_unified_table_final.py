#!/usr/bin/env python3
"""
FIX FINAL: Corrección definitiva para person_details

Este script aplica la corrección final usando la estrategia DIRECT_MATCH
confirmada que relaciona las tablas usando: p.UUID LIKE m.UUID || '%'
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys

# Configuración de la base de datos local
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': 'postgres',
    'database': 'Submissions'
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

def create_unified_table_final(conn):
    """
    Crea la tabla unified usando la estrategia DIRECT_MATCH confirmada
    """
    try:
        print("🔧 Creando tabla unified con estrategia DIRECT_MATCH...")
        
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
        
        # Crear la nueva tabla unified con la estrategia confirmada
        print("🏗️  Creando nueva tabla unified con DIRECT_MATCH...")
        
        # ESTA ES LA CONSULTA CORREGIDA FINAL usando la estrategia que funciona
        create_query = f'''
        CREATE TABLE "{UNIFIED_TABLE}" AS
        SELECT 
            m.*,
            -- Usar COALESCE para devolver array vacío en lugar de null
            COALESCE(pd.person_details, '[]'::jsonb) as person_details,
            -- Generar HTML para imágenes
            CASE 
                WHEN m.building_image_url IS NOT NULL 
                THEN '<img src=' || CHR(34) || m.building_image_url || CHR(34) || ' width=' || CHR(34) || '100%' || CHR(34) || ' height=' || CHR(34) || '100%' || CHR(34) || ' />' 
                ELSE NULL 
            END as building_image_url_html
        FROM "{MAIN_TABLE}" m
        -- SUBCONSULTA que agrega person_details usando la estrategia DIRECT_MATCH
        LEFT JOIN (
            SELECT 
                -- Extraer el UUID principal del UUID de person_details
                SPLIT_PART(p."UUID", '_', 1) as main_uuid,
                -- Agregar todos los person_details para cada submission
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
            -- Solo procesar registros que tienen UUID válido
            WHERE p."UUID" IS NOT NULL 
              AND p."UUID" != ''
            -- Agrupar por el UUID principal extraído
            GROUP BY SPLIT_PART(p."UUID", '_', 1)
        ) pd ON m."UUID" = pd.main_uuid
        '''
        
        if not execute_query(conn, create_query):
            print("❌ Error creando tabla unified")
            return False
        
        # Agregar clave primaria
        print("🔑 Agregando clave primaria...")
        pk_query = f'ALTER TABLE "{UNIFIED_TABLE}" ADD PRIMARY KEY ("UUID")'
        if not execute_query(conn, pk_query):
            print("⚠️  Advertencia: No se pudo agregar clave primaria")
        
        print("✅ Tabla unified creada exitosamente con DIRECT_MATCH!")
        return True
        
    except Exception as e:
        print(f"❌ Error creando tabla unified: {e}")
        return False

def verify_final_result(conn):
    """
    Verificación final de los resultados
    """
    try:
        print("\n🔍 VERIFICACIÓN FINAL DE RESULTADOS:")
        print("-" * 50)
        
        # Contar registros totales
        total_count = execute_scalar(conn, f'SELECT COUNT(*) FROM "{UNIFIED_TABLE}"')
        print(f"📊 Total de registros en unified: {total_count}")
        
        # Contar registros con person_details null
        null_count = execute_scalar(conn, f'''
            SELECT COUNT(*) FROM "{UNIFIED_TABLE}" 
            WHERE person_details IS NULL
        ''')
        print(f"📊 Registros con person_details NULL: {null_count}")
        
        # Contar registros con arrays vacíos
        empty_array_count = execute_scalar(conn, f'''
            SELECT COUNT(*) FROM "{UNIFIED_TABLE}" 
            WHERE person_details = '[]'::jsonb
        ''')
        print(f"📊 Registros con person_details array vacío: {empty_array_count}")
        
        # Contar registros con datos poblados
        populated_count = execute_scalar(conn, f'''
            SELECT COUNT(*) FROM "{UNIFIED_TABLE}" 
            WHERE person_details IS NOT NULL 
            AND person_details != '[]'::jsonb
        ''')
        print(f"📊 Registros con person_details POBLADOS: {populated_count}")
        
        # Mostrar muestras de datos poblados
        if populated_count > 0:
            print("\n📋 MUESTRAS DE PERSON_DETAILS POBLADOS:")
            sample_query = f'''
                SELECT 
                    "UUID", 
                    jsonb_array_length(person_details) as person_count,
                    person_details
                FROM "{UNIFIED_TABLE}" 
                WHERE person_details IS NOT NULL 
                AND person_details != '[]'::jsonb
                ORDER BY jsonb_array_length(person_details) DESC
                LIMIT 3
            '''
            
            samples = execute_query(conn, sample_query, fetch=True)
            if samples:
                for i, sample in enumerate(samples, 1):
                    print(f"\n  Muestra {i}:")
                    print(f"    UUID: {sample['UUID']}")
                    print(f"    Personas: {sample['person_count']}")
                    print(f"    Datos: {str(sample['person_details'])[:200]}...")
        
        # Evaluación final
        print("\n" + "=" * 60)
        print("🎯 EVALUACIÓN FINAL:")
        print("=" * 60)
        
        if null_count == 0:
            print("✅ PERFECTO: No hay registros con person_details NULL")
            if populated_count > 0:
                print(f"🎉 ÉXITO TOTAL: {populated_count} registros tienen person_details poblados")
                print(f"📈 Ratio de éxito: {populated_count}/{total_count} = {(populated_count/total_count)*100:.1f}%")
                print("🔥 ¡La corrección funciona perfectamente!")
                return True
            else:
                print("⚠️  Todos los registros tienen arrays vacíos")
                print("   Esto podría indicar un problema en la lógica de agregación")
                return False
        else:
            print(f"❌ PROBLEMA: {null_count} registros aún tienen person_details NULL")
            return False
        
    except Exception as e:
        print(f"❌ Error verificando resultados: {e}")
        return False

def main():
    """
    Función principal
    """
    print("=" * 70)
    print("🚀 FIX FINAL: Person Details con Estrategia DIRECT_MATCH")
    print("=" * 70)
    print(f"Conectando a: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"Base de datos: {DB_CONFIG['database']}")
    
    try:
        # Conectar a la base de datos
        conn = psycopg2.connect(**DB_CONFIG)
        print("✓ Conexión establecida exitosamente")
        
        # Aplicar la corrección final
        if not create_unified_table_final(conn):
            print("❌ Falló la creación de la tabla unified")
            return False
        
        # Verificar el resultado final
        success = verify_final_result(conn)
        
        conn.close()
        return success
        
    except psycopg2.Error as e:
        print(f"✗ Error de conexión a PostgreSQL: {e}")
        return False
        
    except Exception as e:
        print(f"✗ Error ejecutando fix final: {e}")
        return False

if __name__ == "__main__":
    print("Aplicando FIX FINAL para person_details...")
    
    # Verificar dependencias
    try:
        import psycopg2
    except ImportError:
        print("❌ Error: psycopg2 no está instalado.")
        print("Instálalo con: pip install psycopg2-binary")
        sys.exit(1)
    
    success = main()
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 ¡FIX EXITOSO! Person_details ahora están poblados correctamente")
        print("   ✅ No más valores NULL")
        print("   ✅ Arrays JSON con datos reales de personas")
        print("   ✅ Superset debería mostrar los datos correctamente")
        print("\n🚀 PRÓXIMOS PASOS:")
        print("   1. Verifica los datos en Superset")
        print("   2. La tabla unified ahora tiene person_details poblados")
        print("   3. Puedes crear visualizaciones con esta información")
    else:
        print("❌ El fix falló. Revisa los errores arriba.")
        print("   Si necesitas ayuda, comparte los mensajes de error.")
    print("=" * 70)
    
    sys.exit(0 if success else 1) 