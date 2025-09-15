#!/usr/bin/env python3
"""
Sync monitoring script that shows the benefits of database-based tracking
"""
import logging
from datetime import datetime
from utils.db_sync_manager import db_sync_manager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

def show_sync_dashboard():
    """Display a comprehensive sync dashboard"""
    print("=" * 80)
    print("🔄 ODK SYNC MONITORING DASHBOARD")
    print("=" * 80)
    
    try:
        stats = db_sync_manager.get_sync_statistics()
        
        # Service info
        service_info = stats.get('service_info', {})
        if service_info:
            print(f"📊 Service Instance: {service_info.get('service_instance', 'Unknown')}")
            print(f"📊 Current Time: {service_info.get('current_time', 'Unknown')}")
            print(f"📊 Sync Interval: {service_info.get('sync_interval', 'Unknown')} seconds")
            print()
        
        # Status for each sync type
        print("📈 SYNC TYPE STATUS:")
        print("-" * 80)
        
        sync_types = ['main_submissions', 'person_details', 'image_processing', 'url_refresh']
        
        for sync_type in sync_types:
            status = stats.get(sync_type, {})
            if status:
                last_sync = status.get('last_sync_timestamp', 'Never')
                if last_sync != 'Never':
                    try:
                        # Parse and format timestamp
                        dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                        last_sync = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                    except:
                        pass
                
                status_emoji = "✅" if status.get('last_sync_status') == 'success' else "❌"
                success_count = status.get('successful_syncs', 0)
                failed_count = status.get('failed_syncs', 0)
                last_processed = status.get('last_records_processed', 0)
                
                print(f"{status_emoji} {sync_type.upper().replace('_', ' ')}")
                print(f"   Last Sync: {last_sync}")
                print(f"   Status: {status.get('last_sync_status', 'Unknown')}")
                print(f"   Success/Failed: {success_count}/{failed_count}")
                print(f"   Last Processed: {last_processed} records")
                
                if status.get('last_error_message'):
                    print(f"   ⚠️  Last Error: {status['last_error_message'][:100]}...")
                print()
        
        # Recent activity
        recent_history = stats.get('recent_history', [])
        if recent_history:
            print("📋 RECENT SYNC ACTIVITY (Last 10):")
            print("-" * 80)
            
            for i, history in enumerate(recent_history[:10], 1):
                timestamp = history.get('timestamp', '')
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp = dt.strftime('%H:%M:%S')
                except:
                    pass
                
                status_emoji = "✅" if history.get('status') == 'success' else "❌" if history.get('status') == 'error' else "🔄"
                sync_type = history.get('sync_type', '').replace('_', ' ').title()
                records = history.get('records_processed', 0) or 0
                duration = history.get('duration_seconds', 0) or 0
                
                print(f"{i:2d}. {status_emoji} {timestamp} | {sync_type:<20} | {records:4d} records | {duration:2d}s")
        
        # Performance metrics
        print()
        print("📊 PERFORMANCE METRICS:")
        print("-" * 80)
        
        total_successful = sum(s.get('successful_syncs', 0) for s in stats.values() if isinstance(s, dict))
        total_failed = sum(s.get('failed_syncs', 0) for s in stats.values() if isinstance(s, dict))
        success_rate = (total_successful / (total_successful + total_failed) * 100) if (total_successful + total_failed) > 0 else 0
        
        print(f"✅ Total Successful Syncs: {total_successful}")
        print(f"❌ Total Failed Syncs: {total_failed}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        # Calculate average processing times from recent history
        recent_durations = [h.get('duration_seconds', 0) for h in recent_history[:10] if h.get('duration_seconds')]
        if recent_durations:
            avg_duration = sum(recent_durations) / len(recent_durations)
            print(f"⏱️  Average Sync Duration: {avg_duration:.1f} seconds")
        
    except Exception as e:
        print(f"❌ Error getting sync statistics: {e}")
    
    print("=" * 80)

if __name__ == "__main__":
    show_sync_dashboard()