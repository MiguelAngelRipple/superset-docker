#!/usr/bin/env python3
"""
Exploración de la estructura real de las tablas

Este script se conecta a la BD local y analiza la estructura real
de las tablas para encontrar la relación correcta entre ellas.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys
import re

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
            return True
    except Exception as e:
        print(f"Error ejecutando consulta: {e}")
        return None if fetch else False

def main():
    """
    Función principal de exploración
    """
    print("=" * 70)
    print("EXPLORACIÓN: Estructura Real de las Tablas")
    print("=" * 70)
    
    try:
        # Conectar a la base de datos
        conn = psycopg2.connect(**DB_CONFIG)
        print("✓ Conexión establecida exitosamente")
        
        # 1. Explorar estructura de tabla principal
        print(f"\n1. ESTRUCTURA DE {MAIN_TABLE}:")
        print("-" * 50)
        
        main_sample_query = f'''
            SELECT "UUID", "__id", "__system"
            FROM "{MAIN_TABLE}" 
            LIMIT 5
        '''
        main_samples = execute_query(conn, main_sample_query, fetch=True)
        
        if main_samples:
            print("Muestras de registros principales:")
            for sample in main_samples:
                print(f"  UUID: {sample['UUID']}")
                print(f"  __id: {sample['__id']}")
                print(f"  __system: {sample.get('__system', 'N/A')}")
                print()
        
        # 2. Explorar estructura de tabla person_details
        print(f"\n2. ESTRUCTURA DE {PERSON_DETAILS_TABLE}:")
        print("-" * 50)
        
        person_sample_query = f'''
            SELECT 
                "UUID", 
                "__id", 
                "__Submissions-id",
                "individual_first_name",
                "business_name"
            FROM "{PERSON_DETAILS_TABLE}" 
            LIMIT 5
        '''
        person_samples = execute_query(conn, person_sample_query, fetch=True)
        
        if person_samples:
            print("Muestras de registros person_details:")
            for sample in person_samples:
                print(f"  UUID: {sample['UUID']}")
                print(f"  __id: {sample['__id']}")
                print(f"  __Submissions-id: {sample['__Submissions-id']}")
                print(f"  Nombre: {sample['individual_first_name'] or 'N/A'}")
                print(f"  Empresa: {sample['business_name'] or 'N/A'}")
                print()
        
        # 3. Analizar patrones de UUID
        print("\n3. ANÁLISIS DE PATRONES DE UUID:")
        print("-" * 50)
        
        # Obtener algunos UUIDs para analizar patrones
        main_uuids_query = f'SELECT "UUID" FROM "{MAIN_TABLE}" LIMIT 10'
        main_uuids = execute_query(conn, main_uuids_query, fetch=True)
        
        person_uuids_query = f'SELECT "UUID" FROM "{PERSON_DETAILS_TABLE}" LIMIT 10'
        person_uuids = execute_query(conn, person_uuids_query, fetch=True)
        
        if main_uuids and person_uuids:
            print("UUIDs principales:")
            main_uuid_list = [row['UUID'] for row in main_uuids]
            for uuid in main_uuid_list[:3]:
                print(f"  {uuid}")
            
            print("\nUUIDs person_details:")
            person_uuid_list = [row['UUID'] for row in person_uuids]
            for uuid in person_uuid_list[:3]:
                print(f"  {uuid}")
            
            # Analizar si hay relación entre UUIDs
            print("\n🔍 ANÁLISIS DE RELACIÓN:")
            matches_found = 0
            potential_relationships = []
            
            for main_uuid in main_uuid_list:
                for person_uuid in person_uuid_list:
                    # Verificar si el UUID de person_details contiene el UUID principal
                    if main_uuid in person_uuid:
                        matches_found += 1
                        potential_relationships.append((main_uuid, person_uuid))
                        print(f"✅ MATCH encontrado:")
                        print(f"   Principal: {main_uuid}")
                        print(f"   Person:    {person_uuid}")
                        print()
            
            if matches_found == 0:
                print("❌ No se encontraron relaciones directas en los UUIDs")
                
                # Intentar otras estrategias
                print("\n🔍 INTENTANDO OTRAS ESTRATEGIAS:")
                
                # Estrategia 1: Extraer prefijo de UUID de person_details
                print("Estrategia 1: Extraer prefijo de UUID de person_details")
                for person_uuid in person_uuid_list[:3]:
                    # Intentar extraer la parte antes del último '_'
                    if '_' in person_uuid:
                        prefix = person_uuid.rsplit('_', 1)[0]
                        print(f"  Person UUID: {person_uuid}")
                        print(f"  Prefijo:     {prefix}")
                        
                        # Verificar si este prefijo coincide con algún UUID principal
                        if prefix in main_uuid_list:
                            print(f"  ✅ MATCH: {prefix} está en main table")
                        else:
                            print(f"  ❌ No match directo")
                        print()
        
        # 4. Probar estrategia de relación
        print("\n4. PROBANDO ESTRATEGIA DE RELACIÓN:")
        print("-" * 50)
        
        # Probar si podemos relacionar usando SUBSTRING o SPLIT
        test_relation_query = f'''
            SELECT 
                m."UUID" as main_uuid,
                p."UUID" as person_uuid,
                p."individual_first_name",
                p."business_name",
                CASE 
                    WHEN p."UUID" LIKE m."UUID" || '%' THEN 'DIRECT_MATCH'
                    WHEN SPLIT_PART(p."UUID", '_', 1) = m."UUID" THEN 'PREFIX_MATCH'
                    ELSE 'NO_MATCH'
                END as match_type
            FROM "{MAIN_TABLE}" m
            CROSS JOIN "{PERSON_DETAILS_TABLE}" p
            WHERE p."UUID" LIKE m."UUID" || '%'
               OR SPLIT_PART(p."UUID", '_', 1) = m."UUID"
            LIMIT 10
        '''
        
        test_results = execute_query(conn, test_relation_query, fetch=True)
        
        if test_results:
            print("✅ RELACIONES ENCONTRADAS:")
            for result in test_results:
                print(f"  Main UUID: {result['main_uuid']}")
                print(f"  Person UUID: {result['person_uuid']}")
                print(f"  Match Type: {result['match_type']}")
                print(f"  Nombre: {result['individual_first_name'] or 'N/A'}")
                print(f"  Empresa: {result['business_name'] or 'N/A'}")
                print()
        else:
            print("❌ No se encontraron relaciones con las estrategias probadas")
        
        # 5. Contar registros totales
        print("\n5. ESTADÍSTICAS FINALES:")
        print("-" * 50)
        
        main_count_query = f'SELECT COUNT(*) FROM "{MAIN_TABLE}"'
        main_count = execute_query(conn, main_count_query, fetch=True)[0]['count']
        
        person_count_query = f'SELECT COUNT(*) FROM "{PERSON_DETAILS_TABLE}"'
        person_count = execute_query(conn, person_count_query, fetch=True)[0]['count']
        
        print(f"Total registros en {MAIN_TABLE}: {main_count}")
        print(f"Total registros en {PERSON_DETAILS_TABLE}: {person_count}")
        
        # Contar relaciones exitosas
        if test_results:
            relation_count_query = f'''
                SELECT COUNT(*) as total_relations
                FROM "{MAIN_TABLE}" m
                INNER JOIN "{PERSON_DETAILS_TABLE}" p 
                    ON (p."UUID" LIKE m."UUID" || '%' 
                        OR SPLIT_PART(p."UUID", '_', 1) = m."UUID")
            '''
            relation_count = execute_query(conn, relation_count_query, fetch=True)
            if relation_count:
                print(f"Relaciones encontradas: {relation_count[0]['total_relations']}")
        
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"✗ Error de conexión a PostgreSQL: {e}")
        return False
        
    except Exception as e:
        print(f"✗ Error ejecutando exploración: {e}")
        return False

if __name__ == "__main__":
    print("Explorando estructura real de las tablas...")
    
    # Verificar si psycopg2 está disponible
    try:
        import psycopg2
    except ImportError:
        print("❌ Error: psycopg2 no está instalado.")
        print("Instálalo con: pip install psycopg2-binary")
        sys.exit(1)
    
    success = main()
    
    if not success:
        print("\n❌ La exploración falló. Verifica la configuración de la base de datos.")
        sys.exit(1)
    else:
        print("\n✅ Exploración completada. Revisa los resultados arriba.")
        sys.exit(0) 