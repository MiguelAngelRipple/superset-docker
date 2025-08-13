#!/usr/bin/env python3
"""
Test script for the unified table person_details fix

This script helps verify that the fix for null person_details in the unified table
is working correctly. It recreates the unified table and runs verification checks.

Usage:
    python test_unified_fix.py
"""

import sys
import os

# Add the okd_sync directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'okd_sync'))

def main():
    """
    Main test function
    """
    print("=" * 60)
    print("Testing Unified Table Person Details Fix")
    print("=" * 60)
    
    try:
        # Import the test functions
        from db.sqlalchemy_operations import test_unified_table_creation, verify_unified_table
        
        print("\n1. Running unified table creation test...")
        test_success = test_unified_table_creation()
        
        if test_success:
            print("✓ Test PASSED - The unified table was created successfully!")
            print("✓ Person details are no longer null - fix is working!")
        else:
            print("✗ Test FAILED - There are still issues with the unified table")
            print("  Check the logs for more details")
            
        print("\n2. Running verification check...")
        verification_result = verify_unified_table()
        
        if 'error' in verification_result:
            print(f"✗ Verification failed: {verification_result['error']}")
            return False
            
        # Display detailed results
        print("\nDetailed Results:")
        print(f"  - Table exists: {verification_result['table_exists']}")
        print(f"  - Total records: {verification_result['total_records']}")
        print(f"  - Records with person details: {verification_result['records_with_person_details']}")
        print(f"  - Records with null person details: {verification_result['records_with_null_person_details']}")
        print(f"  - Records with empty array person details: {verification_result['records_with_empty_array_person_details']}")
        
        # Check the fix
        null_count = verification_result['records_with_null_person_details']
        if null_count == 0:
            print("\n✓ SUCCESS: No records have null person_details!")
            print("  The fix is working correctly.")
        else:
            print(f"\n✗ ISSUE: {null_count} records still have null person_details")
            print("  The fix may not be working as expected.")
            
        if verification_result['sample_person_details']:
            print(f"\nSample person details structure:")
            print(f"  {verification_result['sample_person_details']}")
            
        return null_count == 0
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Make sure you're running this from the project root directory")
        print("and that the okd_sync module is properly set up")
        return False
        
    except Exception as e:
        print(f"✗ Error running test: {e}")
        return False

if __name__ == "__main__":
    print("Testing the fix for null person_details in unified table...")
    
    success = main()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL TESTS PASSED! The fix is working correctly.")
        print("   Person details should now be properly populated in Superset.")
    else:
        print("❌ Some tests failed. Please check the issues above.")
        print("   You may need to investigate further or contact support.")
    print("=" * 60)
    
    sys.exit(0 if success else 1) 