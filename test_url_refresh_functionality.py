#!/usr/bin/env python3
"""
Script de prueba para verificar la funcionalidad actualizada de renovación de URLs.

Este script permite probar las funciones modificadas para manejar tanto 
building_image_url como address_plus_code_url.
"""

import sys
import os
from datetime import datetime

# Add okd_sync to Python path
sys.path.append('okd_sync')

try:
    from okd_sync.storage.s3 import refresh_expired_urls, update_unified_html_after_refresh
    from okd_sync.db.sqlalchemy_models import engine
    from okd_sync.config import URL_REFRESH_THRESHOLD_HOURS, ENABLE_URL_REFRESH
    from sqlalchemy.orm import Session
    from sqlalchemy import text
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

def test_configuration():
    """
    Verifica la configuración actual del sistema de renovación de URLs.
    """
    print("=" * 60)
    print("CONFIGURACIÓN DEL SISTEMA DE RENOVACIÓN DE URLs")
    print("=" * 60)
    print(f"Renovación automática activada: {ENABLE_URL_REFRESH}")
    print(f"Umbral de renovación: {URL_REFRESH_THRESHOLD_HOURS} horas antes del vencimiento")
    print(f"Fecha/hora actual: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def test_database_connection():
    """
    Verifica que la conexión a la base de datos funcione correctamente.
    """
    print("=" * 60)
    print("PRUEBA DE CONEXIÓN A BASE DE DATOS")
    print("=" * 60)
    
    try:
        session = Session(engine)
        
        # Consulta simple para verificar conexión
        query = text("""
            SELECT COUNT(*) as total_records,
                   SUM(CASE WHEN building_image_url IS NOT NULL AND building_image_url != '' THEN 1 ELSE 0 END) as building_urls,
                   SUM(CASE WHEN address_plus_code_url IS NOT NULL AND address_plus_code_url != '' THEN 1 ELSE 0 END) as address_urls
            FROM "GRARentalDataCollection"
        """)
        
        result = session.execute(query)
        row = result.fetchone()
        
        print("✅ Conexión a base de datos exitosa")
        print(f"📊 Total de registros: {row[0]}")
        print(f"🏠 Registros con building_image_url: {row[1]}")
        print(f"🗺️  Registros con address_plus_code_url: {row[2]}")
        print()
        
        session.close()
        return True
        
    except Exception as e:
        print(f"❌ Error de conexión a base de datos: {e}")
        print()
        return False

def test_url_refresh_function():
    """
    Prueba la función de renovación de URLs sin hacer cambios reales.
    """
    print("=" * 60)
    print("PRUEBA DE FUNCIÓN DE RENOVACIÓN DE URLs")
    print("=" * 60)
    
    if not ENABLE_URL_REFRESH:
        print("⚠️  La renovación automática está desactivada en la configuración")
        print("   Para activarla, establece ENABLE_URL_REFRESH=true en el archivo .env")
        print()
        return False
    
    try:
        print("🔍 Ejecutando análisis de URLs que necesitan renovación...")
        
        # Ejecutar la función de renovación
        # Esta función ahora maneja tanto building_image_url como address_plus_code_url
        refreshed_count = refresh_expired_urls(max_workers=3)
        
        if refreshed_count > 0:
            print(f"✅ Se renovaron {refreshed_count} URLs exitosamente")
            print("🔄 Actualizando campos HTML en tabla unificada...")
            
            # Actualizar campos HTML después de la renovación
            update_unified_html_after_refresh()
            print("✅ Campos HTML actualizados exitosamente")
        else:
            print("ℹ️  No se encontraron URLs que necesiten renovación en este momento")
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ Error durante la prueba de renovación de URLs: {e}")
        print()
        return False

def test_unified_table_fields():
    """
    Verifica que los campos HTML en la tabla unificada estén funcionando correctamente.
    """
    print("=" * 60)
    print("VERIFICACIÓN DE CAMPOS HTML EN TABLA UNIFICADA")
    print("=" * 60)
    
    try:
        session = Session(engine)
        
        # Consulta para verificar campos HTML
        query = text("""
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN building_image_url_html IS NOT NULL AND building_image_url_html != '' THEN 1 ELSE 0 END) as building_html_count,
                SUM(CASE WHEN address_plus_code_url_html IS NOT NULL AND address_plus_code_url_html != '' THEN 1 ELSE 0 END) as address_html_count,
                SUM(CASE WHEN building_image_url IS NOT NULL AND building_image_url != '' THEN 1 ELSE 0 END) as building_url_count,
                SUM(CASE WHEN address_plus_code_url IS NOT NULL AND address_plus_code_url != '' THEN 1 ELSE 0 END) as address_url_count
            FROM "GRARentalDataCollection_unified"
        """)
        
        result = session.execute(query)
        row = result.fetchone()
        
        print("📊 ESTADÍSTICAS DE TABLA UNIFICADA:")
        print(f"   Total de registros: {row[0]}")
        print(f"   Building URLs: {row[3]} | Building HTML: {row[1]}")
        print(f"   Address URLs: {row[4]} | Address HTML: {row[2]}")
        
        # Verificar consistencia
        building_consistent = row[1] == row[3]  # HTML count == URL count
        address_consistent = row[2] == row[4]   # HTML count == URL count
        
        if building_consistent and address_consistent:
            print("✅ Consistencia entre URLs y campos HTML: CORRECTA")
        else:
            print("⚠️  Posible inconsistencia detectada:")
            if not building_consistent:
                print(f"   Building: {row[3]} URLs vs {row[1]} HTMLs")
            if not address_consistent:
                print(f"   Address: {row[4]} URLs vs {row[2]} HTMLs")
        
        session.close()
        print()
        return building_consistent and address_consistent
        
    except Exception as e:
        print(f"❌ Error verificando tabla unificada: {e}")
        print()
        return False

def run_comprehensive_test():
    """
    Ejecuta todas las pruebas de funcionalidad.
    """
    print("🚀 INICIANDO PRUEBAS DE FUNCIONALIDAD ACTUALIZADA")
    print("=" * 80)
    print()
    
    # Lista de pruebas a ejecutar
    tests = [
        ("Configuración del sistema", test_configuration),
        ("Conexión a base de datos", test_database_connection),
        ("Función de renovación de URLs", test_url_refresh_function),
        ("Campos HTML en tabla unificada", test_unified_table_fields)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"🔧 Ejecutando: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Error en {test_name}: {e}")
            results.append((test_name, False))
        print()
    
    # Resumen final
    print("=" * 80)
    print("📋 RESUMEN DE PRUEBAS")
    print("=" * 80)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ EXITOSA" if result else "❌ FALLIDA"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 TODAS LAS PRUEBAS PASARON EXITOSAMENTE")
        print("   La funcionalidad actualizada está funcionando correctamente.")
    else:
        print("⚠️  ALGUNAS PRUEBAS FALLARON")
        print("   Revisa los detalles arriba para identificar los problemas.")
    
    print("=" * 80)

if __name__ == "__main__":
    run_comprehensive_test()