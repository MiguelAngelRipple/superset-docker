#!/usr/bin/env python3
"""
Diagnóstico del problema con person_details

Este script verifica los datos en las tablas main y person_details
para entender por qué la relación no está funcionando.
"""

import sys
import os

# Add the okd_sync directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'okd_sync'))

def main():
    """
    Función principal de diagnóstico
    """
    print("=" * 70)
    print("DIAGNÓSTICO: Person Details Relationship")
    print("=" * 70)
    
    try:
        from db.connection import Session, engine
        from db.sqlalchemy_models import MAIN_TABLE, PERSON_DETAILS_TABLE
        from sqlalchemy import text
        
        with Session(engine) as session:
            
            # 1. Verificar si las tablas existen y cuántos registros tienen
            print("\n1. VERIFICACIÓN DE TABLAS:")
            print("-" * 40)
            
            # Main table
            try:
                main_count_query = f'SELECT COUNT(*) FROM "{MAIN_TABLE}"'
                main_count = session.execute(text(main_count_query)).scalar()
                print(f"✓ Tabla principal ({MAIN_TABLE}): {main_count} registros")
            except Exception as e:
                print(f"✗ Error accediendo tabla principal: {e}")
                return False
                
            # Person details table  
            try:
                person_count_query = f'SELECT COUNT(*) FROM "{PERSON_DETAILS_TABLE}"'
                person_count = session.execute(text(person_count_query)).scalar()
                print(f"✓ Tabla person details ({PERSON_DETAILS_TABLE}): {person_count} registros")
            except Exception as e:
                print(f"✗ Error accediendo tabla person details: {e}")
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
            main_uuids = session.execute(text(main_uuid_query)).fetchall()
            print(f"Muestras de UUIDs en tabla principal:")
            for uuid_row in main_uuids:
                print(f"  - {uuid_row[0]}")
            
            # Submissions IDs from person details table
            person_submission_ids_query = f'''
                SELECT DISTINCT "__Submissions-id" 
                FROM "{PERSON_DETAILS_TABLE}" 
                WHERE "__Submissions-id" IS NOT NULL 
                LIMIT 5
            '''
            person_submission_ids = session.execute(text(person_submission_ids_query)).fetchall()
            print(f"\nMuestras de __Submissions-id en tabla person details:")
            for sub_id_row in person_submission_ids:
                print(f"  - {sub_id_row[0]}")
            
            # 3. Verificar coincidencias entre las tablas
            print("\n3. VERIFICACIÓN DE RELACIONES:")
            print("-" * 40)
            
            # Count matching UUIDs
            matching_query = f'''
                SELECT COUNT(DISTINCT m."UUID") 
                FROM "{MAIN_TABLE}" m
                INNER JOIN "{PERSON_DETAILS_TABLE}" p ON m."UUID" = p."__Submissions-id"
            '''
            matching_count = session.execute(text(matching_query)).scalar()
            print(f"Registros de main table que tienen person details: {matching_count}")
            
            # Count person details that match main table
            matching_persons_query = f'''
                SELECT COUNT(*) 
                FROM "{PERSON_DETAILS_TABLE}" p
                INNER JOIN "{MAIN_TABLE}" m ON p."__Submissions-id" = m."UUID"
            '''
            matching_persons_count = session.execute(text(matching_persons_query)).scalar()
            print(f"Registros de person details que tienen match en main: {matching_persons_count}")
            
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
                WHERE "individual_first_name" IS NOT NULL 
                   OR "business_name" IS NOT NULL
                LIMIT 3
            '''
            sample_persons = session.execute(text(sample_person_query)).fetchall()
            
            if sample_persons:
                print("Muestra de registros con datos:")
                for person in sample_persons:
                    print(f"  UUID: {person[0]}")
                    print(f"  Submission ID: {person[1]}")
                    print(f"  Nombre: {person[2]} {person[3] or ''}")
                    print(f"  Empresa: {person[4] or 'N/A'}")
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
                WHERE p."UUID" IS NOT NULL
                GROUP BY p."__Submissions-id"
                LIMIT 3
            '''
            
            aggregation_results = session.execute(text(test_aggregation_query)).fetchall()
            
            if aggregation_results:
                print("Resultados de agregación:")
                for result in aggregation_results:
                    print(f"  Submission UUID: {result[0]}")
                    print(f"  Personas count: {result[1]}")
                    print(f"  Datos: {result[2]}")
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
                WHERE table_name = '{MAIN_TABLE.lower()}' 
                AND column_name = 'UUID'
            '''
            
            person_submission_type_query = f'''
                SELECT data_type, character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = '{PERSON_DETAILS_TABLE.lower().replace("_", "")}' 
                AND column_name = '__Submissions-id'
            '''
            
            try:
                main_type = session.execute(text(main_uuid_type_query)).fetchone()
                if main_type:
                    print(f"Tipo de UUID en main table: {main_type[0]} ({main_type[1] or 'sin límite'})")
                
                person_type = session.execute(text(person_submission_type_query)).fetchone()
                if person_type:
                    print(f"Tipo de __Submissions-id en person details: {person_type[0]} ({person_type[1] or 'sin límite'})")
            except Exception as e:
                print(f"No se pudo verificar tipos de datos: {e}")
            
            # Summary
            print("\n" + "=" * 70)
            print("RESUMEN DEL DIAGNÓSTICO:")
            print("=" * 70)
            
            if main_count == 0:
                print("❌ PROBLEMA: No hay datos en la tabla principal")
            elif person_count == 0:
                print("❌ PROBLEMA: No hay datos en la tabla person_details")
            elif matching_count == 0:
                print("❌ PROBLEMA: No hay coincidencias entre las tablas")
                print("   Esto indica un problema con la relación UUID <-> __Submissions-id")
            elif matching_persons_count == 0:
                print("❌ PROBLEMA: Los person_details no tienen UUIDs válidos")
            else:
                print(f"✅ Las tablas tienen datos y {matching_count} registros coinciden")
                if len(sample_persons) == 0:
                    print("⚠️  Pero los person_details parecen estar vacíos (sin nombres/empresas)")
                else:
                    print("✅ Los person_details contienen datos válidos")
            
            return True
        
    except ImportError as e:
        print(f"✗ Error de importación: {e}")
        print("Asegúrate de ejecutar desde el directorio raíz del proyecto")
        return False
        
    except Exception as e:
        print(f"✗ Error ejecutando diagnóstico: {e}")
        return False

if __name__ == "__main__":
    print("Ejecutando diagnóstico de person_details...")
    success = main()
    
    if not success:
        print("\n❌ El diagnóstico falló. Verifica la configuración de la base de datos.")
        sys.exit(1)
    else:
        print("\n✅ Diagnóstico completado. Revisa los resultados arriba.")
        sys.exit(0) 