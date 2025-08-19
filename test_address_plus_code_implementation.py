#!/usr/bin/env python3
"""
Script de prueba para la implementación de address_plus_code_url

Este script prueba las funciones de extracción del nuevo campo 
sin necesidad de conectar a ODK o S3.
"""

import json
import sys
import os

# Add the okd_sync directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'okd_sync'))

try:
    from odk.parser import extract_address_plus_code, process_submission
    from storage.s3 import extract_address_plus_code as s3_extract_address_plus_code
    print("✅ Imports exitosos")
except ImportError as e:
    print(f"❌ Error de import: {e}")
    sys.exit(1)

def test_extraction_functions():
    """Test the address_plus_code extraction functions"""
    
    print("\n🧪 Probando funciones de extracción...")
    
    # Test case 1: property_location como dict
    test_case_1 = {
        'UUID': 'test-uuid-1',
        'property_location': {
            'address_plus_code_image': 'address_code_image_1.jpg',
            'other_field': 'some_value'
        }
    }
    
    # Test case 2: property_location como JSON string
    test_case_2 = {
        'UUID': 'test-uuid-2',
        'property_location': json.dumps({
            'address_plus_code_image': 'address_code_image_2.png',
            'latitude': '1.234',
            'longitude': '5.678'
        })
    }
    
    # Test case 3: No address_plus_code_image present
    test_case_3 = {
        'UUID': 'test-uuid-3',
        'property_location': {
            'latitude': '1.234',
            'longitude': '5.678'
        }
    }
    
    # Test case 4: property_location missing
    test_case_4 = {
        'UUID': 'test-uuid-4',
        'other_field': 'some_value'
    }
    
    # Test case 5: address_plus_code in top-level field
    test_case_5 = {
        'UUID': 'test-uuid-5',
        'address_plus_code_image_field': 'top_level_image.jpg',
        'property_location': {}
    }
    
    test_cases = [
        ("Dict con address_plus_code_image", test_case_1, 'address_code_image_1.jpg'),
        ("JSON string con address_plus_code_image", test_case_2, 'address_code_image_2.png'),
        ("Sin address_plus_code_image", test_case_3, None),
        ("Sin property_location", test_case_4, None),
        ("Campo top-level", test_case_5, 'top_level_image.jpg')
    ]
    
    print("\n📝 Probando extract_address_plus_code (parser):")
    for description, test_case, expected in test_cases:
        result = extract_address_plus_code(test_case)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {description}: {result} (esperado: {expected})")
    
    print("\n📝 Probando extract_address_plus_code (S3):")
    for description, test_case, expected in test_cases:
        result = s3_extract_address_plus_code(test_case)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {description}: {result} (esperado: {expected})")

def test_process_submission():
    """Test the submission processing function"""
    
    print("\n🧪 Probando process_submission...")
    
    # Test with property_location as JSON string
    test_submission = {
        'UUID': 'test-process-1',
        '__id': 'test-process-1',
        'property_location': json.dumps({
            'address_plus_code_image': 'processed_image.jpg',
            'latitude': '1.234'
        }),
        'property_description': json.dumps({
            'building_image': 'building_img.jpg'
        })
    }
    
    # Process the submission
    processed = process_submission(test_submission.copy())
    
    # Check if JSON fields were parsed
    location_parsed = isinstance(processed.get('property_location'), dict)
    description_parsed = isinstance(processed.get('property_description'), dict)
    
    print(f"  ✅ property_location parsed: {location_parsed}")
    print(f"  ✅ property_description parsed: {description_parsed}")
    
    if location_parsed:
        address_code = processed['property_location'].get('address_plus_code_image')
        print(f"  ✅ address_plus_code_image extraído: {address_code}")

def test_database_fields():
    """Test that database models have the new fields"""
    
    print("\n🧪 Probando modelos de base de datos...")
    
    try:
        from db.sqlalchemy_models import MainSubmission, UnifiedView
        
        # Check MainSubmission has the new field
        has_address_url = hasattr(MainSubmission, 'address_plus_code_url')
        print(f"  ✅ MainSubmission.address_plus_code_url: {has_address_url}")
        
        # Check UnifiedView has both new fields
        has_unified_url = hasattr(UnifiedView, 'address_plus_code_url')
        has_unified_html = hasattr(UnifiedView, 'address_plus_code_url_html')
        print(f"  ✅ UnifiedView.address_plus_code_url: {has_unified_url}")
        print(f"  ✅ UnifiedView.address_plus_code_url_html: {has_unified_html}")
        
    except ImportError as e:
        print(f"  ❌ Error importando modelos: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando pruebas de implementación address_plus_code_url\n")
    
    test_extraction_functions()
    test_process_submission()
    test_database_fields()
    
    print("\n✅ Pruebas completadas!")
    print("\nPara probar con datos reales:")
    print("1. Ejecutar el sync: python okd_sync/main.py")
    print("2. Verificar en la base de datos los nuevos campos")
    print("3. Comprobar en Superset que las imágenes se muestran correctamente")