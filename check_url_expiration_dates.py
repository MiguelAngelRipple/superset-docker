#!/usr/bin/env python3
"""
Script para revisar las fechas de vencimiento de las URLs de imágenes 
en la tabla GRARentalDataCollection_unified.

Este script verifica tanto building_image_url_html como address_plus_code_url_html
y muestra las fechas de vencimiento de las URLs de S3.
"""

import re
import sys
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

# Add okd_sync to Python path
sys.path.append('okd_sync')

try:
    from okd_sync.db.sqlalchemy_models import engine
    from okd_sync.config import URL_REFRESH_THRESHOLD_HOURS
    from sqlalchemy.orm import Session
    from sqlalchemy import text
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

def extract_expiration_from_url(url):
    """
    Extrae la fecha de vencimiento de una URL firmada de S3.
    
    Args:
        url (str): URL firmada de S3
        
    Returns:
        datetime: Fecha de vencimiento o None si no se puede extraer
    """
    if not url or 'Expires=' not in url:
        return None
    
    try:
        # Buscar el parámetro Expires en la URL
        expires_match = re.search(r'Expires=(\d+)', url)
        if not expires_match:
            return None
        
        expires_timestamp = int(expires_match.group(1))
        expires_datetime = datetime.fromtimestamp(expires_timestamp)
        return expires_datetime
        
    except Exception as e:
        print(f"Error al extraer fecha de vencimiento de URL: {e}")
        return None

def extract_url_from_html(html_content):
    """
    Extrae la URL de un campo HTML que contiene una etiqueta img.
    
    Args:
        html_content (str): Contenido HTML con etiqueta img
        
    Returns:
        str: URL extraída o None si no se encuentra
    """
    if not html_content:
        return None
    
    # Buscar URL en atributo src de img tag
    src_match = re.search(r'src=["\']([^"\']+)["\']', html_content)
    if src_match:
        return src_match.group(1)
    
    return None

def get_url_status(url, threshold_hours=URL_REFRESH_THRESHOLD_HOURS):
    """
    Determina el estado de una URL basado en su fecha de vencimiento.
    
    Args:
        url (str): URL a verificar
        threshold_hours (int): Horas antes del vencimiento para considerar "próximo a vencer"
        
    Returns:
        tuple: (estado, fecha_vencimiento)
    """
    expiration_date = extract_expiration_from_url(url)
    
    if not expiration_date:
        return "Sin fecha de vencimiento", None
    
    now = datetime.now()
    threshold_datetime = now + timedelta(hours=threshold_hours)
    
    if expiration_date <= now:
        return "VENCIDA", expiration_date
    elif expiration_date <= threshold_datetime:
        return "PRÓXIMA A VENCER", expiration_date
    else:
        return "VÁLIDA", expiration_date

def check_url_expiration_status():
    """
    Revisa el estado de vencimiento de todas las URLs en la tabla unificada.
    """
    print("=" * 80)
    print("DIAGNÓSTICO DE FECHAS DE VENCIMIENTO DE URLs DE IMÁGENES")
    print("=" * 80)
    print(f"Umbral de renovación configurado: {URL_REFRESH_THRESHOLD_HOURS} horas antes del vencimiento")
    print(f"Fecha actual: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    session = Session(engine)
    
    try:
        # Consulta para obtener registros con URLs de imágenes
        query = text("""
            SELECT 
                "UUID",
                building_image_url,
                building_image_url_html,
                address_plus_code_url,
                address_plus_code_url_html,
                survey_date
            FROM "GRARentalDataCollection_unified"
            WHERE 
                (building_image_url_html IS NOT NULL AND building_image_url_html != '') 
                OR 
                (address_plus_code_url_html IS NOT NULL AND address_plus_code_url_html != '')
            ORDER BY survey_date DESC
            LIMIT 50
        """)
        
        result = session.execute(query)
        records = result.fetchall()
        
        if not records:
            print("No se encontraron registros con URLs de imágenes.")
            return
        
        print(f"Analizando {len(records)} registros más recientes...")
        print()
        
        # Estadísticas
        building_stats = {"VÁLIDA": 0, "PRÓXIMA A VENCER": 0, "VENCIDA": 0, "Sin fecha de vencimiento": 0}
        address_stats = {"VÁLIDA": 0, "PRÓXIMA A VENCER": 0, "VENCIDA": 0, "Sin fecha de vencimiento": 0}
        
        print("ESTADO DETALLADO DE URLs:")
        print("-" * 80)
        
        for record in records:
            uuid = record[0]
            building_url = record[1]
            building_html = record[2]
            address_url = record[3]
            address_html = record[4]
            survey_date = record[5]
            
            print(f"\nUUID: {uuid}")
            print(f"Fecha de encuesta: {survey_date}")
            
            # Analizar building_image_url_html
            if building_html:
                url_from_html = extract_url_from_html(building_html)
                if url_from_html:
                    status, exp_date = get_url_status(url_from_html)
                    building_stats[status] += 1
                    exp_str = exp_date.strftime('%Y-%m-%d %H:%M:%S') if exp_date else "N/A"
                    print(f"  📷 Building Image: {status} (Vence: {exp_str})")
                else:
                    print(f"  📷 Building Image: No se pudo extraer URL del HTML")
            else:
                print(f"  📷 Building Image: No disponible")
            
            # Analizar address_plus_code_url_html
            if address_html:
                url_from_html = extract_url_from_html(address_html)
                if url_from_html:
                    status, exp_date = get_url_status(url_from_html)
                    address_stats[status] += 1
                    exp_str = exp_date.strftime('%Y-%m-%d %H:%M:%S') if exp_date else "N/A"
                    print(f"  🗺️  Address Plus Code: {status} (Vence: {exp_str})")
                else:
                    print(f"  🗺️  Address Plus Code: No se pudo extraer URL del HTML")
            else:
                print(f"  🗺️  Address Plus Code: No disponible")
        
        # Mostrar resumen estadístico
        print("\n" + "=" * 80)
        print("RESUMEN ESTADÍSTICO")
        print("=" * 80)
        
        print("\n📷 BUILDING IMAGE URLs:")
        total_building = sum(building_stats.values())
        if total_building > 0:
            for status, count in building_stats.items():
                percentage = (count / total_building) * 100
                print(f"  {status}: {count} ({percentage:.1f}%)")
        else:
            print("  No se encontraron URLs de building images")
        
        print("\n🗺️ ADDRESS PLUS CODE URLs:")
        total_address = sum(address_stats.values())
        if total_address > 0:
            for status, count in address_stats.items():
                percentage = (count / total_address) * 100
                print(f"  {status}: {count} ({percentage:.1f}%)")
        else:
            print("  No se encontraron URLs de address plus code")
        
        # Alertas importantes
        print("\n" + "⚠️ " * 20)
        print("ALERTAS IMPORTANTES:")
        
        if building_stats["VENCIDA"] > 0:
            print(f"🔴 {building_stats['VENCIDA']} building image URLs están VENCIDAS")
        
        if address_stats["VENCIDA"] > 0:
            print(f"🔴 {address_stats['VENCIDA']} address plus code URLs están VENCIDAS")
        
        if building_stats["PRÓXIMA A VENCER"] > 0:
            print(f"🟡 {building_stats['PRÓXIMA A VENCER']} building image URLs están próximas a vencer")
        
        if address_stats["PRÓXIMA A VENCER"] > 0:
            print(f"🟡 {address_stats['PRÓXIMA A VENCER']} address plus code URLs están próximas a vencer")
        
        total_problems = (building_stats["VENCIDA"] + building_stats["PRÓXIMA A VENCER"] + 
                         address_stats["VENCIDA"] + address_stats["PRÓXIMA A VENCER"])
        
        if total_problems == 0:
            print("✅ Todas las URLs están en buen estado")
        
        print("⚠️ " * 20)
        
    except Exception as e:
        print(f"Error al ejecutar el diagnóstico: {e}")
        
    finally:
        session.close()

if __name__ == "__main__":
    check_url_expiration_status()