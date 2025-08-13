#!/usr/bin/env python3
"""
Diagnóstico del problema con person_details - Versión para BD Local

Este script verifica los datos en las tablas main y person_details
para entender por qué la relación no está funcionando.

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

def execute_query(conn, query):
    """Ejecuta una consulta y devuelve los resultados"""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except Exception as e:
        print(f"Error ejecutando consulta: {e}")
        return None

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

def main():
    """
    Función principal de diagnóstico
    """
    print("=" * 70)
    print("DIAGNÓSTICO: Person Details Relationship (BD Local)")
    print("=" * 70)
    print(f"Conectando a: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"Base de datos: {DB_CONFIG['database']}")
    print(f"Usuario: {DB_CONFIG['user']}")
    
    try:
        # Conectar a la base de datos
        conn = psycopg2.connect(**DB_CONFIG)
        print("✓ Conexión establecida exitosamente")
        
        # 1. Verificar si las tablas existen y cuántos registros tienen
        print("\n1. VERIFICACIÓN DE TABLAS:")
        print("-" * 40)
        
        # Main table
        main_count_query = f'SELECT COUNT(*) FROM "{MAIN_TABLE}"'
        main_count = execute_scalar(conn, main_count_query)
        
        if main_count is not None:
            print(f"✓ Tabla principal ({MAIN_TABLE}): {main_count} registros")
        else:
            print(f"✗ Error accediendo tabla principal o tabla no existe")
            return False
            
        # Person details table  
        person_count_query = f'SELECT COUNT(*) FROM "{PERSON_DETAILS_TABLE}"'
        person_count = execute_scalar(conn, person_count_query)
        
        if person_count is not None:
            print(f"✓ Tabla person details ({PERSON_DETAILS_TABLE}): {person_count} registros")
        else:
            print(f"✗ Error accediendo tabla person details o tabla no existe")
            return False
        
        # 2. Verificar la estructura de UUIDs en ambas tablas
        print("\n2. VERIFICACIÓN DE UUIDs:")
        print("-" * 40)
        
        # UUIDs from main table
        main_uuid_query = f'''
            SELECT "UUID" 
            FROM "{MAIN_TABLE}" 
            WHERE "UUID" IS NOT NULL 
            LIMIT 5
        '''
        main_uuids = execute_query(conn, main_uuid_query)
        
        print(f"Muestras de UUIDs en tabla principal:")
        if main_uuids:
            for uuid_row in main_uuids:
                print(f"  - {uuid_row['UUID']}")
        else:
            print("  (No se encontraron UUIDs)")
        
        # Submissions IDs from person details table
        person_submission_ids_query = f'''
            SELECT DISTINCT "__Submissions-id" 
            FROM "{PERSON_DETAILS_TABLE}" 
            WHERE "__Submissions-id" IS NOT NULL 
            LIMIT 5
        '''
        person_submission_ids = execute_query(conn, person_submission_ids_query)
        
        print(f"\nMuestras de __Submissions-id en tabla person details:")
        if person_submission_ids:
            for sub_id_row in person_submission_ids:
                print(f"  - {sub_id_row['__Submissions-id']}")
        else:
            print("  (No se encontraron __Submissions-id)")
        
        # 3. Verificar coincidencias entre las tablas
        print("\n3. VERIFICACIÓN DE RELACIONES:")
        print("-" * 40)
        
        # Count matching UUIDs
        matching_query = f'''
            SELECT COUNT(DISTINCT m."UUID") 
            FROM "{MAIN_TABLE}" m
            INNER JOIN "{PERSON_DETAILS_TABLE}" p ON m."UUID" = p."__Submissions-id"
        '''
        matching_count = execute_scalar(conn, matching_query)
        print(f"Registros de main table que tienen person details: {matching_count or 0}")
        
        # Count person details that match main table
        matching_persons_query = f'''
            SELECT COUNT(*) 
            FROM "{PERSON_DETAILS_TABLE}" p
            INNER JOIN "{MAIN_TABLE}" m ON p."__Submissions-id" = m."UUID"
        '''
        matching_persons_count = execute_scalar(conn, matching_persons_query)
        print(f"Registros de person details que tienen match en main: {matching_persons_count or 0}")
        
        # 4. Verificar datos específicos de person details
        print("\n4. VERIFICACIÓN DE DATOS EN PERSON DETAILS:")
        print("-" * 40)
        
        # Sample person details with all relevant fields
        sample_person_query = f'''
            SELECT 
                "UUID",
                "__Submissions-id",
                "individual_first_name",
                "individual_last_name",
                "business_name"
            FROM "{PERSON_DETAILS_TABLE}" 
            WHERE ("individual_first_name" IS NOT NULL AND "individual_first_name" != '')
               OR ("business_name" IS NOT NULL AND "business_name" != '')
            LIMIT 3
        '''
        sample_persons = execute_query(conn, sample_person_query)
        
        if sample_persons:
            print("Muestra de registros con datos:")
            for person in sample_persons:
                print(f"  UUID: {person['UUID']}")
                print(f"  Submission ID: {person['__Submissions-id']}")
                print(f"  Nombre: {person['individual_first_name'] or ''} {person['individual_last_name'] or ''}")
                print(f"  Empresa: {person['business_name'] or 'N/A'}")
                print()
        else:
            print("⚠️  No se encontraron registros con nombres o empresas")
        
        # 5. Probar la consulta de agregación directamente
        print("\n5. PRUEBA DE CONSULTA DE AGREGACIÓN:")
        print("-" * 40)
        
        test_aggregation_query = f'''
            SELECT 
                p."__Submissions-id" as submission_uuid,
                COUNT(*) as person_count,
                jsonb_agg(
                    jsonb_build_object(
                        'UUID', p."UUID",
                        'individual_first_name', p."individual_first_name",
                        'individual_last_name', p."individual_last_name",
                        'business_name', p."business_name"
                    )
                ) as aggregated_data
            FROM "{PERSON_DETAILS_TABLE}" p
            WHERE p."__Submissions-id" IS NOT NULL 
              AND TRIM(p."__Submissions-id") != ''
            GROUP BY p."__Submissions-id"
            LIMIT 3
        '''
        
        aggregation_results = execute_query(conn, test_aggregation_query)
        
        if aggregation_results:
            print("Resultados de agregación:")
            for result in aggregation_results:
                print(f"  Submission UUID: {result['submission_uuid']}")
                print(f"  Personas count: {result['person_count']}")
                print(f"  Datos: {result['aggregated_data']}")
                print()
        else:
            print("⚠️  No se encontraron resultados en la agregación")
        
        # 6. Verificar tipos de datos de los campos de relación
        print("\n6. VERIFICACIÓN DE TIPOS DE DATOS:")
        print("-" * 40)
        
        # Check data types
        main_uuid_type_query = f'''
            SELECT data_type, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name = '{MAIN_TABLE}' 
            AND column_name = 'UUID'
        '''
        
        person_submission_type_query = f'''
            SELECT data_type, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name = '{PERSON_DETAILS_TABLE}' 
            AND column_name = '__Submissions-id'
        '''
        
        main_type_result = execute_query(conn, main_uuid_type_query)
        if main_type_result:
            main_type = main_type_result[0]
            print(f"Tipo de UUID en main table: {main_type['data_type']} ({main_type['character_maximum_length'] or 'sin límite'})")
        
        person_type_result = execute_query(conn, person_submission_type_query)
        if person_type_result:
            person_type = person_type_result[0]
            print(f"Tipo de __Submissions-id en person details: {person_type['data_type']} ({person_type['character_maximum_length'] or 'sin límite'})")
        
        # Summary
        print("\n" + "=" * 70)
        print("RESUMEN DEL DIAGNÓSTICO:")
        print("=" * 70)
        
        if main_count == 0:
            print("❌ PROBLEMA: No hay datos en la tabla principal")
        elif person_count == 0:
            print("❌ PROBLEMA: No hay datos en la tabla person_details")
        elif (matching_count or 0) == 0:
            print("❌ PROBLEMA: No hay coincidencias entre las tablas")
            print("   Esto indica un problema con la relación UUID <-> __Submissions-id")
        elif (matching_persons_count or 0) == 0:
            print("❌ PROBLEMA: Los person_details no tienen UUIDs válidos")
        else:
            print(f"✅ Las tablas tienen datos y {matching_count} registros coinciden")
            if not sample_persons:
                print("⚠️  Pero los person_details parecen estar vacíos (sin nombres/empresas)")
            else:
                print("✅ Los person_details contienen datos válidos")
        
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"✗ Error de conexión a PostgreSQL: {e}")
        return False
        
    except Exception as e:
        print(f"✗ Error ejecutando diagnóstico: {e}")
        return False

if __name__ == "__main__":
    print("Ejecutando diagnóstico de person_details en BD local...")
    
    # Verificar si psycopg2 está disponible
    try:
        import psycopg2
    except ImportError:
        print("❌ Error: psycopg2 no está instalado.")
        print("Instálalo con: pip install psycopg2-binary")
        sys.exit(1)
    
    success = main()
    
    if not success:
        print("\n❌ El diagnóstico falló. Verifica la configuración de la base de datos.")
        sys.exit(1)
    else:
        print("\n✅ Diagnóstico completado. Revisa los resultados arriba.")
        sys.exit(0) 