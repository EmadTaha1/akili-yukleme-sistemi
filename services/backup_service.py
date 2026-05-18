"""
====================================================================
Database Backup Service
====================================================================
Responsibilities:
1. Automated database backups (Online SQLite backup)
2. Compressing subject trainer models and datasets
3. Managing rolling rotation for storage safety
4. Database recovery from designated backups
"""

import os
import shutil
import zipfile
import sqlite3
from datetime import datetime
import threading
import time

try:
    from services.logger_service import get_logger
    logger = get_logger("system")
except ImportError:
    import logging
    logger = logging.getLogger("system")


def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_backup_dir():
    """Returns the backup directory path, creating it if necessary."""
    backup_dir = os.path.join(get_base_dir(), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


# ==================== Configuration ====================
MAX_BACKUPS = 10           # Keep only the last 10 backups
AUTO_BACKUP_INTERVAL = 24  # Trigger backup every 24 hours


def create_database_backup():
    """
    Creates a timestamped backup of the SQLite database.
    Uses SQLite's online backup API to ensure safety while the DB is open.
    """
    try:
        base_dir = get_base_dir()
        db_path = os.path.join(base_dir, "database", "attendance_system.db")
        
        if not os.path.exists(db_path):
            logger.warning("Veritabanı dosyası bulunamadı")
            return False, "Database not found"
        
        backup_dir = get_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"db_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # SQLite Online Backup API (thread-safe, concurrent safe)
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(backup_path)
        with dest:
            source.backup(dest)
        source.close()
        dest.close()
        
        size_mb = os.path.getsize(backup_path) / (1024*1024)
        logger.info(f"✅ Yedekleme başarılı: {backup_filename} ({size_mb:.2f} MB)")
        
        return True, backup_path
    except Exception as e:
        logger.error(f"Yedekleme başarısız oldu: {e}")
        return False, str(e)


def create_full_backup(include_dataset=False):
    """
    Creates a full ZIP backup containing:
    - The SQLite database
    - Trained AI models (.pkl)
    - Student face datasets (optional)
    """
    try:
        base_dir = get_base_dir()
        backup_dir = get_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"full_backup_{timestamp}.zip"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # 1. Database
            db_path = os.path.join(base_dir, "database", "attendance_system.db")
            if os.path.exists(db_path):
                zf.write(db_path, "database/attendance_system.db")
            
            # 2. Trained models
            models_dir = os.path.join(base_dir, "models")
            if os.path.exists(models_dir):
                for root, dirs, files in os.walk(models_dir):
                    for file in files:
                        if file.endswith('.pkl') or file.endswith('.yml'):
                            file_path = os.path.join(root, file)
                            arc_name = os.path.relpath(file_path, base_dir)
                            zf.write(file_path, arc_name)
            
            # 3. Student Datasets (Optional)
            if include_dataset:
                dataset_dir = os.path.join(base_dir, "dataset")
                if os.path.exists(dataset_dir):
                    for file in os.listdir(dataset_dir):
                        if file.endswith('.jpg'):
                            file_path = os.path.join(dataset_dir, file)
                            zf.write(file_path, f"dataset/{file}")
        
        size_mb = os.path.getsize(backup_path) / (1024*1024)
        logger.info(f"✅ Tam yedekleme başarılı: {backup_filename} ({size_mb:.2f} MB)")
        
        return True, backup_path
    except Exception as e:
        logger.error(f"Tam yedekleme başarısız oldu: {e}")
        return False, str(e)


def cleanup_old_backups(max_backups=MAX_BACKUPS):
    """Deletes old backups, keeping only the latest N files."""
    try:
        backup_dir = get_backup_dir()
        all_backups = []
        
        for filename in os.listdir(backup_dir):
            if filename.startswith('db_backup_') or filename.startswith('full_backup_'):
                file_path = os.path.join(backup_dir, filename)
                mtime = os.path.getmtime(file_path)
                all_backups.append((mtime, file_path, filename))
        
        # Sort by timestamp (newest first)
        all_backups.sort(reverse=True)
        
        # Remove old ones beyond the threshold limit
        if len(all_backups) > max_backups:
            to_delete = all_backups[max_backups:]
            for _, path, name in to_delete:
                try:
                    os.remove(path)
                    logger.info(f"🗑️ Eski yedek silindi: {name}")
                except Exception as e:
                    logger.warning(f"Silme başarısız {name}: {e}")
        
        return True, len(all_backups)
    except Exception as e:
        logger.error(f"Yedek temizleme başarısız oldu: {e}")
        return False, str(e)


def list_backups():
    """Returns a list of all available backup files."""
    backup_dir = get_backup_dir()
    backups = []
    
    for filename in sorted(os.listdir(backup_dir), reverse=True):
        if filename.startswith('db_backup_') or filename.startswith('full_backup_'):
            file_path = os.path.join(backup_dir, filename)
            stat = os.stat(file_path)
            backups.append({
                'filename': filename,
                'path': file_path,
                'size_mb': stat.st_size / (1024*1024),
                'created': datetime.fromtimestamp(stat.st_mtime),
                'type': 'full' if 'full_' in filename else 'db'
            })
    
    return backups


def restore_database_backup(backup_path):
    """
    Restores the SQLite database from a backup file.
    WARNING: Overwrites the active live database!
    """
    try:
        if not os.path.exists(backup_path):
            return False, "Yedek dosyası mevcut değil"
        
        base_dir = get_base_dir()
        db_path = os.path.join(base_dir, "database", "attendance_system.db")
        
        # Safely copy a copy of the current active database before overwriting
        if os.path.exists(db_path):
            pre_restore_backup = db_path + ".before_restore"
            shutil.copy(db_path, pre_restore_backup)
            logger.info(f"Mevcut veritabanı şuraya yedeklendi: {pre_restore_backup}")
        
        # Restore
        shutil.copy(backup_path, db_path)
        logger.info(f"✅ Geri yüklendi: {os.path.basename(backup_path)}")
        
        return True, "Başarıyla geri yüklendi"
    except Exception as e:
        logger.error(f"Geri yükleme başarısız oldu: {e}")
        return False, str(e)


# ==================== Auto Backup Scheduler ====================

class AutoBackupScheduler:
    """
    Automated background database yedeği alma scheduler.
    Runs every X hours in a daemon thread.
    """
    def __init__(self, interval_hours=AUTO_BACKUP_INTERVAL):
        self.interval_seconds = interval_hours * 3600
        self.running = False
        self.thread = None
    
    def _run(self):
        logger.info(f"📅 Otomatik yedekleme aktif (Her {self.interval_seconds/3600:.0f} saatte bir)")
        
        # First initial backup upon start
        create_database_backup()
        cleanup_old_backups()
        
        while self.running:
            time.sleep(60)  # Check interval
            
            backups = list_backups()
            if backups:
                last_backup = backups[0]
                time_since = (datetime.now() - last_backup['created']).total_seconds()
                if time_since >= self.interval_seconds:
                    create_database_backup()
                    cleanup_old_backups()
            else:
                create_database_backup()
    
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
    
    def stop(self):
        self.running = False


# Quick verification
if __name__ == "__main__":
    print("Yedekleme servisi test ediliyor...")
    
    success, result = create_database_backup()
    print(f"DB Backup: {'✅' if success else '❌'} - {result}")
    
    backups = list_backups()
    print(f"\nMevcut yedekler: {len(backups)}")
    for b in backups[:5]:
        print(f"  • {b['filename']} ({b['size_mb']:.2f} MB)")