#!/usr/bin/env python3
"""
Kernel-Add - Integrated Package Manager + Mini Kernel
Menggunakan mirror:
1. https://mirror.nevacloud.com/applications/termux/termux-main
2. https://mirror.twds.com.tw/ubuntu/
3. https://mirror.jeonnam.school/rocky-linux/
4. https://mirror.alpinelinux.org/alpine/
5. https://mirror.archlinux.tw/ArchLinux/
"""
import os
import sys
import json
import pickle
import hashlib
import urllib.request
import urllib.error
import tarfile
import lzma
import gzip
import shutil
import subprocess
import time
import platform
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import tempfile

# Import driver system
try:
    from KernelDriver import DriverManager
    DRIVERS_AVAILABLE = True
except ImportError:
    DRIVERS_AVAILABLE = False
    print("⚠️  KernelDriver.py not found - driver features disabled")

# ===== DATABASE MANAGER =====

class DatabaseManager:
    """SQLite Database Manager untuk kernel"""
    
    def __init__(self, db_path: str):
        """Initialize SQLite database"""
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.cursor()
            
            # Table for installed packages
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS packages (
                    name TEXT PRIMARY KEY,
                    version TEXT,
                    size INTEGER,
                    filename TEXT,
                    installed_time REAL,
                    auto_installed INTEGER DEFAULT 0,
                    simulated INTEGER DEFAULT 0
                )
            ''')
            
            # Table for dependencies
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dependencies (
                    package TEXT,
                    depends_on TEXT,
                    FOREIGN KEY (package) REFERENCES packages(name),
                    PRIMARY KEY (package, depends_on)
                )
            ''')
            
            # Table for metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Hidden filesystem table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hidden_files (
                    path TEXT PRIMARY KEY,
                    content BLOB,
                    size INTEGER,
                    created_time REAL,
                    modified_time REAL,
                    permissions TEXT DEFAULT 'rw-r--r--'
                )
            ''')
            
            self.conn.commit()
            
        except sqlite3.Error as e:
            print(f"⚠️  Database initialization error: {e}")
    
    def get_package(self, name: str) -> Optional[Dict]:
        """Get package info"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM packages WHERE name = ?', (name,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except sqlite3.Error as e:
            print(f"⚠️  Error getting package: {e}")
            return None
    
    def add_package(self, name: str, version: str, size: int, filename: str, 
                    auto_installed: bool = False, simulated: bool = False):
        """Add package to database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO packages 
                (name, version, size, filename, installed_time, auto_installed, simulated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, version, size, filename, time.time(), 
                  1 if auto_installed else 0, 1 if simulated else 0))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"⚠️  Error adding package: {e}")
            return False
    
    def remove_package(self, name: str):
        """Remove package from database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM packages WHERE name = ?', (name,))
            cursor.execute('DELETE FROM dependencies WHERE package = ? OR depends_on = ?', 
                          (name, name))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"⚠️  Error removing package: {e}")
            return False
    
    def get_all_packages(self) -> List[Dict]:
        """Get all installed packages"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM packages ORDER BY name')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"⚠️  Error getting packages: {e}")
            return []
    
    def add_dependency(self, package: str, depends_on: str):
        """Add dependency relationship"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO dependencies (package, depends_on)
                VALUES (?, ?)
            ''', (package, depends_on))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"⚠️  Error adding dependency: {e}")
            return False
    
    def get_orphaned_packages(self) -> List[str]:
        """Find orphaned packages (auto-installed but no longer needed)"""
        try:
            cursor = self.conn.cursor()
            # Get all auto-installed packages
            cursor.execute('SELECT name FROM packages WHERE auto_installed = 1')
            auto_installed = [row[0] for row in cursor.fetchall()]
            
            # Get all manually installed packages
            cursor.execute('SELECT name FROM packages WHERE auto_installed = 0')
            manually_installed = [row[0] for row in cursor.fetchall()]
            
            # Get all dependencies of manually installed packages
            needed = set()
            for pkg in manually_installed:
                cursor.execute('''
                    SELECT depends_on FROM dependencies WHERE package = ?
                ''', (pkg,))
                needed.update([row[0] for row in cursor.fetchall()])
            
            # Orphaned = auto-installed but not needed
            orphaned = [pkg for pkg in auto_installed if pkg not in needed]
            return orphaned
            
        except sqlite3.Error as e:
            print(f"⚠️  Error finding orphaned packages: {e}")
            return []
    
    # Hidden filesystem operations
    def write_hidden_file(self, path: str, content: bytes):
        """Write to hidden filesystem"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO hidden_files 
                (path, content, size, created_time, modified_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (path, content, len(content), time.time(), time.time()))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"⚠️  Error writing hidden file: {e}")
            return False
    
    def read_hidden_file(self, path: str) -> Optional[bytes]:
        """Read from hidden filesystem"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT content FROM hidden_files WHERE path = ?', (path,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None
        except sqlite3.Error as e:
            print(f"⚠️  Error reading hidden file: {e}")
            return None
    
    def list_hidden_files(self) -> List[Dict]:
        """List all hidden files"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT path, size, modified_time FROM hidden_files ORDER BY path')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"⚠️  Error listing hidden files: {e}")
            return []
    
    def delete_hidden_file(self, path: str):
        """Delete hidden file"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM hidden_files WHERE path = ?', (path,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"⚠️  Error deleting hidden file: {e}")
            return False
    
    def set_metadata(self, key: str, value: str):
        """Set metadata value"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO metadata (key, value)
                VALUES (?, ?)
            ''', (key, value))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"⚠️  Error setting metadata: {e}")
            return False
    
    def get_metadata(self, key: str) -> Optional[str]:
        """Get metadata value"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT value FROM metadata WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None
        except sqlite3.Error as e:
            print(f"⚠️  Error getting metadata: {e}")
            return None
    
    def repair(self) -> bool:
        """Repair corrupted database"""
        print("🔧 Starting database repair...")
        
        try:
            # Close current connection
            if self.conn:
                self.conn.close()
            
            # Backup corrupted database
            backup_path = f"{self.db_path}.backup.{int(time.time())}"
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, backup_path)
                print(f"📋 Backup created: {backup_path}")
            
            # Try to recover data using sqlite3 recovery
            temp_db = f"{self.db_path}.temp"
            
            # Attempt recovery by dumping and recreating
            try:
                # Open corrupted database
                old_conn = sqlite3.connect(self.db_path)
                old_cursor = old_conn.cursor()
                
                # Create new database
                new_conn = sqlite3.connect(temp_db)
                
                # Dump schema and data
                for line in old_conn.iterdump():
                    try:
                        new_conn.execute(line)
                    except sqlite3.Error:
                        continue
                
                new_conn.commit()
                new_conn.close()
                old_conn.close()
                
                # Replace old database with repaired one
                if os.path.exists(temp_db):
                    os.replace(temp_db, self.db_path)
                    print("✅ Database repaired successfully")
                
            except sqlite3.Error as e:
                print(f"⚠️  Partial recovery: {e}")
                # If recovery fails, recreate from scratch
                if os.path.exists(temp_db):
                    os.remove(temp_db)
                os.remove(self.db_path)
                print("🔄 Creating fresh database...")
            
            # Reinitialize database
            self._init_database()
            print("✅ Database reinitialized")
            return True
            
        except Exception as e:
            print(f"❌ Repair failed: {e}")
            return False
    
    def check_package_exists(self, name: str) -> bool:
        """Check if package exists"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT name FROM packages WHERE name = ?', (name,))
            return cursor.fetchone() is not None
        except sqlite3.Error:
            return False
    
    def remove_package_safe(self, name: str) -> bool:
        """Safely remove package (no error if not exists)"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM packages WHERE name = ?', (name,))
            cursor.execute('DELETE FROM dependencies WHERE package = ? OR depends_on = ?', 
                          (name, name))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"⚠️  Error removing package: {e}")
            return False
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# ===== PACKAGE MANAGER =====

class AddPackageManager:
    """Package Manager dengan mirror custom"""
    
    MIRRORS = [
        "https://mirror.nevacloud.com/applications/termux/termux-main/",
        "https://mirror.twds.com.tw/ubuntu/",
        "https://mirror.jeonnam.school/rocky-linux/",
        "https://mirror.alpinelinux.org/alpine/",
        "https://mirror.archlinux.tw/ArchLinux/"
    ]
    
    def __init__(self, prefix: str = None):
        """Inisialisasi package manager"""
        self.arch = self._detect_architecture()
        
        if prefix is None:
            self.prefix = str(Path.home() / '.kernel-add')
        else:
            self.prefix = prefix
        
        self._create_directories()
        
        # Use SQLite database instead of JSON
        db_path = f"{self.prefix}/var/lib/add/.kernel.db"  # Hidden database
        self.db_manager = DatabaseManager(db_path)
        
        self.index_file = f"{self.prefix}/var/cache/add/index.json"
        
        # Initialize metadata
        if not self.db_manager.get_metadata('version'):
            self.db_manager.set_metadata('version', '1.0.0')
            self.db_manager.set_metadata('architecture', self.arch)
            for i, mirror in enumerate(self.MIRRORS):
                self.db_manager.set_metadata(f'mirror_{i}', mirror)
        
        self.packages_index = {}
        self.mirror_idx = 0
        self.current_mirror = self.MIRRORS[0]
    
    def _detect_architecture(self) -> str:
        """Deteksi architecture sistem"""
        machine = platform.machine().lower()
        arch_map = {
            'aarch64': 'aarch64',
            'armv8l': 'aarch64',
            'armv7l': 'arm',
            'i686': 'i686',
            'x86_64': 'x86_64',
            'amd64': 'amd64'
        }
        return arch_map.get(machine, 'aarch64')
    
    def _create_directories(self):
        """Buat struktur direktori"""
        dirs = [
            f"{self.prefix}/bin",
            f"{self.prefix}/lib",
            f"{self.prefix}/include",
            f"{self.prefix}/share",
            f"{self.prefix}/var/lib/add",
            f"{self.prefix}/var/cache/add",
            f"{self.prefix}/tmp",
            f"{self.prefix}/kernel"
        ]
        
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def update(self) -> bool:
        """Update package list dari mirror"""
        print("🔄 Updating package list from mirrors...")
        
        # Try Alpine mirror first (most reliable for our use case)
        print("📦 Fetching from Alpine Linux mirror...")
        alpine_url = "https://dl-cdn.alpinelinux.org/alpine/v3.19/main/x86_64/APKINDEX.tar.gz"
        packages_local = f"{self.prefix}/var/cache/add/APKINDEX.tar.gz"
        
        if self._download_direct(alpine_url, packages_local):
            if self._parse_apkindex(packages_local):
                print(f"✅ Package list updated from Alpine Linux")
                return True
        
        # Fallback to dummy if Alpine fails
        print("⚠️  Alpine mirror failed, using fallback dummy index")
        self._create_dummy_index()
        return True
    
    def _download_direct(self, url: str, dest: str) -> bool:
        """Download file directly (without mirror rotation)"""
        try:
            print(f"   Downloading {url}...")
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'kernel-add/1.0'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get('content-length', 0))
                
                with open(dest, 'wb') as f:
                    downloaded = 0
                    chunk_size = 8192
                    
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            bar_length = 30
                            filled = int(bar_length * downloaded // total_size)
                            bar = '█' * filled + '░' * (bar_length - filled)
                            print(f"\r   [{bar}] {percent:.1f}%", end='', flush=True)
                    
                    print()  # New line after progress
            
            return True
            
        except Exception as e:
            print(f"\r   ❌ Download failed: {e}")
            return False
    
    def _parse_apkindex(self, apkindex_path: str) -> bool:
        """Parse Alpine APKINDEX.tar.gz file"""
        try:
            import tarfile
            
            print(f"   Parsing APKINDEX...")
            packages = {}
            
            # Extract APKINDEX from tar.gz
            with tarfile.open(apkindex_path, 'r:gz') as tar:
                # APKINDEX file is usually named just "APKINDEX"
                for member in tar.getmembers():
                    if 'APKINDEX' in member.name and member.isfile():
                        f = tar.extractfile(member)
                        if f:
                            content = f.read().decode('utf-8', errors='ignore')
                            packages = self._parse_apkindex_content(content)
                            break
            
            if packages:
                self.packages_index = packages
                
                # Save to JSON cache
                with open(self.index_file, 'w') as f:
                    json.dump(packages, f, indent=2)
                
                print(f"   ✅ Parsed {len(packages)} packages from Alpine")
                return True
            
            return False
            
        except Exception as e:
            print(f"   ⚠️  Error parsing APKINDEX: {e}")
            return False
    
    def _parse_apkindex_content(self, content: str) -> Dict:
        """Parse APKINDEX content into package dict"""
        packages = {}
        current_pkg = {}
        
        for line in content.split('\n'):
            line = line.strip()
            
            if line == '':
                # Empty line = end of package entry
                if current_pkg and 'P' in current_pkg:
                    pkg_name = current_pkg['P']
                    
                    # Convert to our format
                    packages[pkg_name] = {
                        'Package': pkg_name,
                        'Version': current_pkg.get('V', 'unknown'),
                        'Architecture': current_pkg.get('A', 'x86_64'),
                        'Description': current_pkg.get('T', 'No description'),
                        'Size': int(current_pkg.get('S', 0)),
                        'Filename': f"{pkg_name}-{current_pkg.get('V', '0')}.apk",
                        'License': current_pkg.get('L', 'unknown'),
                        'URL': current_pkg.get('U', ''),
                        'Depends': current_pkg.get('D', '')
                    }
                
                current_pkg = {}
            
            elif ':' in line:
                key, value = line.split(':', 1)
                current_pkg[key] = value.strip()
        
        return packages
    
    def _parse_packages(self, packages_path: str) -> bool:
        """Parse Packages file"""
        try:
            packages = {}
            current_pkg = {}
            
            with open(packages_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.rstrip('\n')
                    
                    if line == '':
                        if current_pkg:
                            pkg_name = current_pkg.get('Package')
                            if pkg_name:
                                packages[pkg_name] = current_pkg
                            current_pkg = {}
                    elif ': ' in line:
                        key, value = line.split(': ', 1)
                        current_pkg[key] = value
            
            if packages:
                self.packages_index = packages
                
                with open(self.index_file, 'w') as f:
                    json.dump(packages, f, indent=2)
                
                print(f"✅ Package list updated: {len(packages)} packages")
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️  Error parsing packages: {e}")
            return False
    
    def _create_dummy_index(self):
        """Buat dummy package index untuk testing"""
        dummy_packages = {
            'python3': {
                'Package': 'python3',
                'Version': '3.11.6',
                'Architecture': self.arch,
                'Description': 'Python programming language interpreter',
                'Size': '15000000',
                'Filename': f'python3-3.11.6-{self.arch}.apk'
            },
            'curl': {
                'Package': 'curl',
                'Version': '8.5.0',
                'Architecture': self.arch,
                'Description': 'Command line tool for transferring data with URLs',
                'Size': '500000',
                'Filename': f'curl-8.5.0-{self.arch}.apk'
            },
            'git': {
                'Package': 'git',
                'Version': '2.43.0',
                'Architecture': self.arch,
                'Description': 'Fast, scalable, distributed revision control system',
                'Size': '8000000',
                'Filename': f'git-2.43.0-{self.arch}.apk'
            },
            'vim': {
                'Package': 'vim',
                'Version': '9.0.2121',
                'Architecture': self.arch,
                'Description': 'Vi IMproved - enhanced vi editor',
                'Size': '3500000',
                'Filename': f'vim-9.0.2121-{self.arch}.apk'
            },
            'nodejs': {
                'Package': 'nodejs',
                'Version': '20.10.0',
                'Architecture': self.arch,
                'Description': 'JavaScript runtime built on Chrome V8 engine',
                'Size': '12000000',
                'Filename': f'nodejs-20.10.0-{self.arch}.apk'
            },
            'nginx': {
                'Package': 'nginx',
                'Version': '1.24.0',
                'Architecture': self.arch,
                'Description': 'HTTP and reverse proxy server',
                'Size': '1200000',
                'Filename': f'nginx-1.24.0-{self.arch}.apk'
            },
            'docker': {
                'Package': 'docker',
                'Version': '24.0.7',
                'Architecture': self.arch,
                'Description': 'Pack, ship and run any application as a container',
                'Size': '25000000',
                'Filename': f'docker-24.0.7-{self.arch}.apk'
            },
            'postgresql': {
                'Package': 'postgresql',
                'Version': '16.1',
                'Architecture': self.arch,
                'Description': 'Sophisticated object-relational DBMS',
                'Size': '18000000',
                'Filename': f'postgresql-16.1-{self.arch}.apk'
            },
            'redis': {
                'Package': 'redis',
                'Version': '7.2.3',
                'Architecture': self.arch,
                'Description': 'Advanced key-value store',
                'Size': '2500000',
                'Filename': f'redis-7.2.3-{self.arch}.apk'
            },
            'gcc': {
                'Package': 'gcc',
                'Version': '13.2.0',
                'Architecture': self.arch,
                'Description': 'GNU Compiler Collection',
                'Size': '45000000',
                'Filename': f'gcc-13.2.0-{self.arch}.apk'
            },
            'bash': {
                'Package': 'bash',
                'Version': '5.2.21',
                'Architecture': self.arch,
                'Description': 'GNU Bourne Again shell',
                'Size': '1800000',
                'Filename': f'bash-5.2.21-{self.arch}.apk'
            },
            'openssh': {
                'Package': 'openssh',
                'Version': '9.6',
                'Architecture': self.arch,
                'Description': 'OpenSSH remote login client and server',
                'Size': '2200000',
                'Filename': f'openssh-9.6-{self.arch}.apk'
            }
        }
        
        self.packages_index = dummy_packages
        
        with open(self.index_file, 'w') as f:
            json.dump(dummy_packages, f, indent=2)
        
        print(f"📦 Fallback index created with {len(dummy_packages)} packages")
        print(f"💡 Run 'update' again to fetch from real Alpine mirror")
    
    def search(self, query: str) -> List[Dict]:
        """Search packages"""
        if not self.packages_index:
            if os.path.exists(self.index_file):
                try:
                    with open(self.index_file, 'r') as f:
                        self.packages_index = json.load(f)
                except:
                    return []
        
        results = []
        query_lower = query.lower()
        
        for pkg_name, pkg_info in self.packages_index.items():
            if (query_lower in pkg_name.lower() or 
                query_lower in pkg_info.get('Description', '').lower()):
                
                # Check if installed using SQLite
                installed = self.db_manager.get_package(pkg_name) is not None
                
                results.append({
                    'name': pkg_name,
                    'version': pkg_info.get('Version', 'unknown'),
                    'description': pkg_info.get('Description', 'No description'),
                    'size': int(pkg_info.get('Size', 0)),
                    'installed': installed,
                    'status': '✓' if installed else ' '
                })
        
        return sorted(results, key=lambda x: x['name'])
    
    def install(self, package_name: str, simulate: bool = False) -> bool:
        """Install package (or simulate)"""
        print(f"📦 Installing {package_name}...")
        
        # Check if already installed using SQLite
        if self.db_manager.get_package(package_name):
            print(f"⚠️  {package_name} is already installed")
            return True
        
        pkg_info = self._get_package_info(package_name)
        if not pkg_info:
            print(f"❌ Package {package_name} not found")
            results = self.search(package_name)
            if results:
                print("Did you mean:")
                for i, pkg in enumerate(results[:5], 1):
                    print(f"  {i}. {pkg['name']} - {pkg['description'][:50]}...")
            return False
        
        if simulate:
            print(f"✅ [SIMULATED] {package_name} would be installed")
            print(f"   Version: {pkg_info.get('Version')}")
            print(f"   Size: {int(pkg_info.get('Size', 0)):,} bytes")
        else:
            # Simulate installation
            print(f"📥 Downloading {package_name}...")
            time.sleep(0.5)
            print(f"📂 Extracting package...")
            time.sleep(0.3)
            print(f"⚙️  Configuring {package_name}...")
            time.sleep(0.2)
        
        # Add to SQLite database
        self.db_manager.add_package(
            name=package_name,
            version=pkg_info.get('Version', 'unknown'),
            size=int(pkg_info.get('Size', 0)),
            filename=pkg_info.get('Filename', ''),
            auto_installed=False,
            simulated=simulate
        )
        
        # Add dependencies
        depends = pkg_info.get('Depends', '')
        if depends:
            for dep in depends.split(', '):
                dep_clean = dep.split('(')[0].strip()
                if dep_clean:
                    self.db_manager.add_dependency(package_name, dep_clean)
        
        # Update metadata
        self.db_manager.set_metadata('last_update', str(time.time()))
        
        print(f"✅ {package_name} installed successfully!")
        return True
    
    def remove(self, package_name: str) -> bool:
        """Remove package"""
        if not self.db_manager.get_package(package_name):
            print(f"❌ {package_name} is not installed")
            return False
        
        print(f"🗑️  Removing {package_name}...")
        
        # Remove using SQLite
        self.db_manager.remove_package(package_name)
        
        print(f"✅ {package_name} removed")
        return True
    
    def autoremove(self) -> bool:
        """Remove orphaned dependencies (packages installed as deps but no longer needed)"""
        
        # Get orphaned packages from database
        orphaned = self.db_manager.get_orphaned_packages()
        
        if not orphaned:
            print("✅ No orphaned packages to remove")
            return True
        
        print(f"🗑️  Found {len(orphaned)} orphaned package(s):")
        total_size = 0
        for pkg_name in orphaned:
            pkg = self.db_manager.get_package(pkg_name)
            if pkg:
                size = pkg.get('size', 0)
                total_size += size
                print(f"   - {pkg_name} ({size:,} bytes)")
        
        print(f"\n💾 Total space to be freed: {total_size:,} bytes")
        
        confirm = input("Proceed? [Y/n]: ").strip().lower()
        if confirm and confirm != 'y':
            print("❌ Autoremove cancelled")
            return False
        
        # Remove orphaned packages
        for pkg in orphaned:
            print(f"🗑️  Removing {pkg}...")
            self.db_manager.remove_package(pkg)
        
        print(f"✅ Removed {len(orphaned)} orphaned package(s)")
        return True
    
    def list_installed(self) -> List[Dict]:
        """List installed packages"""
        packages = self.db_manager.get_all_packages()
        installed = []
        for pkg in packages:
            installed.append({
                'name': pkg['name'],
                'version': pkg.get('version', 'unknown'),
                'size': pkg.get('size', 0),
                'installed': time.ctime(pkg.get('installed_time', 0))
            })
        
        return sorted(installed, key=lambda x: x['name'])
    
    def info(self, package_name: str):
        """Show package info"""
        pkg_info = self._get_package_info(package_name)
        if not pkg_info:
            print(f"❌ Package {package_name} not found")
            return
        
        print(f"\n📦 Package: {package_name}")
        print(f"   Version: {pkg_info.get('Version', 'unknown')}")
        print(f"   Architecture: {pkg_info.get('Architecture', 'all')}")
        print(f"   Size: {int(pkg_info.get('Size', 0)):,} bytes")
        print(f"   Description: {pkg_info.get('Description', 'No description')}")
        
        # Check installation status from SQLite
        if self.db_manager.get_package(package_name):
            print(f"   Status: ✅ Installed")
        else:
            print(f"   Status: Not installed")
    
    def mirror_list(self):
        """List available mirrors"""
        print("\n🌐 Available mirrors:")
        for i, mirror in enumerate(self.MIRRORS):
            status = "✓" if i == self.mirror_idx else " "
            print(f"  {status} {i+1}. {mirror}")
    
    def mirror_set(self, index: int) -> bool:
        """Set active mirror"""
        if 0 <= index < len(self.MIRRORS):
            self.mirror_idx = index
            self.current_mirror = self.MIRRORS[index]
            print(f"✅ Mirror set to: {self.current_mirror}")
            return True
        else:
            print("❌ Invalid mirror index")
            return False
    
    def clean(self):
        """Clean cache"""
        cache_dir = f"{self.prefix}/var/cache/add"
        tmp_dir = f"{self.prefix}/tmp"
        
        for dir_path in [cache_dir, tmp_dir]:
            if os.path.exists(dir_path):
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    try:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                    except:
                        pass
        
        print("🧹 Cache cleaned")
    
    def _get_package_info(self, package_name: str) -> Optional[Dict]:
        """Get package info"""
        if not self.packages_index:
            if os.path.exists(self.index_file):
                try:
                    with open(self.index_file, 'r') as f:
                        self.packages_index = json.load(f)
                except:
                    return None
        
        return self.packages_index.get(package_name)
    
    def _download(self, url: str, dest: str) -> bool:
        """Download file with retry"""
        try:
            for i in range(len(self.MIRRORS)):
                try:
                    mirror = self.MIRRORS[(self.mirror_idx + i) % len(self.MIRRORS)]
                    full_url = mirror + url if not url.startswith('http') else url
                    
                    req = urllib.request.Request(
                        full_url,
                        headers={'User-Agent': 'kernel-add/1.0'}
                    )
                    
                    with urllib.request.urlopen(req, timeout=10) as response:
                        total_size = int(response.headers.get('content-length', 0))
                        
                        with open(dest, 'wb') as f:
                            downloaded = 0
                            chunk_size = 8192
                            
                            while True:
                                chunk = response.read(chunk_size)
                                if not chunk:
                                    break
                                
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    bar_length = 30
                                    filled = int(bar_length * downloaded // total_size)
                                    bar = '█' * filled + '░' * (bar_length - filled)
                                    print(f"\r[{bar}] {percent:.1f}%", end='', flush=True)
                            
                            print()
                    
                    self.mirror_idx = (self.mirror_idx + i) % len(self.MIRRORS)
                    self.current_mirror = self.MIRRORS[self.mirror_idx]
                    return True
                    
                except Exception as e:
                    continue
            
            return False
            
        except Exception as e:
            return False


# ===== MINI KERNEL =====

class MiniKernel:
    """Mini Kernel untuk testing"""
    
    def __init__(self, name="kernel-add"):
        self.name = name
        self.version = "1.0.0"
        
        self.state = {
            'boot_time': time.time(),
            'processes': {},
            'memory': {},
            'devices': {},
            'modules': {},
            'files': {},
            'logs': [],
            'packages': {}  # Track installed packages
        }
        
        self.syscalls = {
            'read': self.sys_read,
            'write': self.sys_write,
            'exec': self.sys_exec,
            'kill': self.sys_kill,
            'mem_alloc': self.sys_mem_alloc,
            'mem_free': self.sys_mem_free,
            'log': self.sys_log,
            'mount': self.sys_mount,
            'unmount': self.sys_unmount,
            'pkg_install': self.sys_pkg_install,
            'pkg_remove': self.sys_pkg_remove,
            'pkg_list': self.sys_pkg_list
        }
        
        self._log(f"Kernel {name} v{self.version} initialized")
    
    def _log(self, message):
        """Internal logging"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        self.state['logs'].append(log_entry)
        print(f"🔵 {log_entry}")
    
    # ===== SYSTEM CALLS =====
    
    def sys_read(self, filepath):
        """Syscall: read file"""
        if filepath not in self.state['files']:
            return f"ERROR: File {filepath} not found"
        
        self._log(f"READ: {filepath}")
        return self.state['files'][filepath]['data']
    
    def sys_write(self, filepath, data):
        """Syscall: write file"""
        if filepath not in self.state['files']:
            self.state['files'][filepath] = {
                'created': time.time(),
                'modified': time.time(),
                'data': data,
                'size': len(str(data))
            }
            self._log(f"CREATE: {filepath}")
        else:
            self.state['files'][filepath]['data'] = data
            self.state['files'][filepath]['modified'] = time.time()
            self.state['files'][filepath]['size'] = len(str(data))
            self._log(f"WRITE: {filepath}")
        
        return f"Written {len(str(data))} bytes to {filepath}"
    
    def sys_exec(self, pid, name, command):
        """Syscall: execute process"""
        if pid in self.state['processes']:
            return f"ERROR: PID {pid} already exists"
        
        self.state['processes'][pid] = {
            'pid': pid,
            'name': name,
            'command': command,
            'state': 'running',
            'started': time.time(),
            'cpu_time': 0
        }
        
        self._log(f"EXEC: Process {name} (PID {pid})")
        return f"Process {name} started with PID {pid}"
    
    def sys_kill(self, pid):
        """Syscall: kill process"""
        if pid not in self.state['processes']:
            return f"ERROR: PID {pid} not found"
        
        proc = self.state['processes'][pid]
        proc['state'] = 'terminated'
        proc['ended'] = time.time()
        
        self._log(f"KILL: Process {proc['name']} (PID {pid})")
        return f"Process {pid} terminated"
    
    def sys_mem_alloc(self, size, label="unnamed"):
        """Syscall: allocate memory"""
        addr = f"0x{len(self.state['memory']):08x}"
        
        self.state['memory'][addr] = {
            'size': size,
            'label': label,
            'allocated': time.time(),
            'data': bytearray(size)
        }
        
        self._log(f"MALLOC: {size} bytes at {addr} ({label})")
        return addr
    
    def sys_mem_free(self, addr):
        """Syscall: free memory"""
        if addr not in self.state['memory']:
            return f"ERROR: Invalid memory address {addr}"
        
        mem = self.state['memory'].pop(addr)
        self._log(f"FREE: {mem['size']} bytes at {addr} ({mem['label']})")
        return f"Freed {mem['size']} bytes"
    
    def sys_log(self, message):
        """Syscall: user logging"""
        self._log(f"USER: {message}")
        return "OK"
    
    def sys_mount(self, device, mountpoint):
        """Syscall: mount device"""
        dev_id = f"dev_{len(self.state['devices'])}"
        
        self.state['devices'][dev_id] = {
            'device': device,
            'mountpoint': mountpoint,
            'mounted': time.time(),
            'status': 'online'
        }
        
        self._log(f"MOUNT: {device} on {mountpoint}")
        return f"Device {device} mounted on {mountpoint}"
    
    def sys_unmount(self, mountpoint):
        """Syscall: unmount device"""
        for dev_id, dev in self.state['devices'].items():
            if dev['mountpoint'] == mountpoint:
                dev['status'] = 'unmounted'
                dev['unmounted'] = time.time()
                self._log(f"UNMOUNT: {mountpoint}")
                return f"Device unmounted from {mountpoint}"
        
        return f"ERROR: No device mounted on {mountpoint}"
    
    def sys_pkg_install(self, package_name, pm):
        """Syscall: install package via package manager"""
        self._log(f"PKG_INSTALL: {package_name}")
        result = pm.install(package_name, simulate=True)
        
        if result:
            self.state['packages'][package_name] = {
                'installed': time.time(),
                'via': 'kernel-syscall'
            }
        
        return result
    
    def sys_pkg_remove(self, package_name, pm):
        """Syscall: remove package"""
        self._log(f"PKG_REMOVE: {package_name}")
        result = pm.remove(package_name)
        
        if result:
            self.state['packages'].pop(package_name, None)
        
        return result
    
    def sys_pkg_list(self, pm):
        """Syscall: list packages"""
        installed = pm.list_installed()
        result = f"📦 Installed packages ({len(installed)}):\n"
        for pkg in installed:
            size_mb = pkg['size'] / 1024 / 1024
            result += f"  {pkg['name']:<20} {pkg['version']:<15} {size_mb:.1f} MB\n"
        return result
    
    # ===== KERNEL OPERATIONS =====
    
    def syscall(self, name, *args):
        """Execute system call"""
        if name not in self.syscalls:
            self._log(f"ERROR: Unknown syscall '{name}'")
            return f"ERROR: Syscall '{name}' not found"
        
        try:
            return self.syscalls[name](*args)
        except Exception as e:
            self._log(f"ERROR: Syscall {name} failed: {e}")
            return f"ERROR: {e}"
    
    def status(self):
        """Show kernel status"""
        uptime = time.time() - self.state['boot_time']
        
        print("\n" + "="*70)
        print(f"KERNEL STATUS - {self.name} v{self.version}")
        print("="*70)
        print(f"Uptime: {uptime:.1f} seconds")
        print(f"Processes: {len(self.state['processes'])}")
        print(f"Memory blocks: {len(self.state['memory'])}")
        print(f"Devices: {len(self.state['devices'])}")
        print(f"Files: {len(self.state['files'])}")
        print(f"Packages: {len(self.state['packages'])}")
        print(f"Log entries: {len(self.state['logs'])}")
        print("="*70)
    
    def save(self, filepath=None):
        """Save kernel state"""
        if filepath is None:
            filepath = os.path.expanduser("~/.kernel-add/kernel/state.pkl")
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        save_data = {
            'name': self.name,
            'version': self.version,
            'state': self.state,
            'saved_at': time.time()
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(save_data, f)
        
        print(f"💾 Kernel saved to {filepath}")
    
    def load(self, filepath=None):
        """Load kernel state"""
        if filepath is None:
            filepath = os.path.expanduser("~/.kernel-add/kernel/state.pkl")
        
        if not os.path.exists(filepath):
            print(f"❌ File {filepath} not found")
            return False
        
        try:
            with open(filepath, 'rb') as f:
                save_data = pickle.load(f)
            
            self.name = save_data['name']
            self.version = save_data['version']
            self.state = save_data['state']
            
            saved_at = datetime.fromtimestamp(save_data['saved_at']).strftime("%Y-%m-%d %H:%M:%S")
            print(f"📂 Kernel loaded from {filepath} (saved: {saved_at})")
            return True
            
        except Exception as e:
            print(f"❌ Load failed: {e}")
            return False


# ===== VIRTUAL CONTAINER ENGINE =====

class ContainerEngine:
    """Virtual Container Engine - Docker-like container management"""
    
    def __init__(self, db_manager: DatabaseManager, prefix: str):
        """Initialize container engine"""
        self.db_manager = db_manager
        self.prefix = prefix
        self.containers_dir = f"{prefix}/containers"
        self.images_dir = f"{prefix}/images"
        
        Path(self.containers_dir).mkdir(parents=True, exist_ok=True)
        Path(self.images_dir).mkdir(parents=True, exist_ok=True)
        
        self._init_container_tables()
        
        # Virtual network
        self.network = {
            'bridge0': {
                'subnet': '172.17.0.0/16',
                'gateway': '172.17.0.1',
                'containers': {}
            }
        }
    
    def _init_container_tables(self):
        """Initialize container tables in database"""
        try:
            cursor = self.db_manager.conn.cursor()
            
            # Container images table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    tag TEXT DEFAULT 'latest',
                    size INTEGER,
                    created_time REAL,
                    base_image TEXT,
                    layers TEXT
                )
            ''')
            
            # Containers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS containers (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    image_id TEXT,
                    status TEXT DEFAULT 'created',
                    created_time REAL,
                    started_time REAL,
                    pid INTEGER,
                    ip_address TEXT,
                    ports TEXT,
                    volumes TEXT,
                    env_vars TEXT,
                    command TEXT,
                    FOREIGN KEY (image_id) REFERENCES images(id)
                )
            ''')
            
            # Container volumes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS volumes (
                    name TEXT PRIMARY KEY,
                    mountpoint TEXT,
                    size INTEGER,
                    created_time REAL
                )
            ''')
            
            self.db_manager.conn.commit()
            
        except sqlite3.Error as e:
            print(f"⚠️  Container tables init error: {e}")
    
    def _generate_id(self, prefix='') -> str:
        """Generate unique container/image ID"""
        import random
        import string
        chars = string.ascii_lowercase + string.digits
        return prefix + ''.join(random.choice(chars) for _ in range(12))
    
    def create_image(self, name: str, tag: str = 'latest', base_image: str = None) -> str:
        """Create container image"""
        try:
            # Check if image already exists
            cursor = self.db_manager.conn.cursor()
            cursor.execute('SELECT id FROM images WHERE name = ? AND tag = ?', (name, tag))
            existing = cursor.fetchone()
            
            if existing:
                print(f"⚠️  Image already exists: {name}:{tag}")
                print(f"   Image ID: {existing[0]}")
                return existing[0]
            
            # Generate unique ID
            image_id = self._generate_id('img_')
            
            # Ensure ID is unique
            while True:
                cursor.execute('SELECT id FROM images WHERE id = ?', (image_id,))
                if not cursor.fetchone():
                    break
                image_id = self._generate_id('img_')
            
            # Simulate image layers
            layers = json.dumps(['layer_base', 'layer_app', 'layer_config'])
            
            cursor.execute('''
                INSERT INTO images (id, name, tag, size, created_time, base_image, layers)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (image_id, name, tag, 100000000, time.time(), base_image, layers))
            
            self.db_manager.conn.commit()
            
            print(f"✅ Image created: {name}:{tag}")
            print(f"   Image ID: {image_id}")
            return image_id
            
        except sqlite3.Error as e:
            print(f"❌ Failed to create image: {e}")
            print(f"   Details: name={name}, tag={tag}")
            import traceback
            traceback.print_exc()
            return None
    
    def list_images(self) -> List[Dict]:
        """List all images"""
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute('SELECT * FROM images ORDER BY created_time DESC')
            images = []
            for row in cursor.fetchall():
                try:
                    images.append(dict(row))
                except Exception as e:
                    print(f"⚠️  Skipping corrupted image entry: {e}")
                    continue
            return images
        except sqlite3.Error as e:
            print(f"⚠️  Error listing images: {e}")
            print(f"💡 Try: dbfix")
            return []
    
    def create_container(self, name: str, image: str, command: str = '/bin/sh',
                        ports: List[str] = None, volumes: List[str] = None,
                        env: Dict[str, str] = None) -> str:
        """Create container from image"""
        try:
            # Find image
            cursor = self.db_manager.conn.cursor()
            cursor.execute('SELECT id FROM images WHERE name = ? OR id = ?', (image, image))
            img = cursor.fetchone()
            
            if not img:
                print(f"❌ Image not found: {image}")
                print(f"💡 Create an image first with: cimage create {image}")
                return None
            
            image_id = img[0]
            
            # Check if container name already exists
            cursor.execute('SELECT id FROM containers WHERE name = ?', (name,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"❌ Container name already exists: {name}")
                print(f"   Use a different name or remove existing container with: crm {name} -f")
                return None
            
            # Generate unique container ID
            container_id = self._generate_id('ctr_')
            
            # Ensure ID is unique
            while True:
                cursor.execute('SELECT id FROM containers WHERE id = ?', (container_id,))
                if not cursor.fetchone():
                    break
                container_id = self._generate_id('ctr_')
            
            # Allocate IP address
            ip_addr = f"172.17.0.{len(self.network['bridge0']['containers']) + 2}"
            
            # Serialize ports, volumes, env
            ports_str = json.dumps(ports or [])
            volumes_str = json.dumps(volumes or [])
            env_str = json.dumps(env or {})
            
            cursor.execute('''
                INSERT INTO containers 
                (id, name, image_id, status, created_time, ip_address, ports, volumes, env_vars, command)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (container_id, name, image_id, 'created', time.time(), 
                  ip_addr, ports_str, volumes_str, env_str, command))
            
            self.db_manager.conn.commit()
            
            print(f"✅ Container created: {name}")
            print(f"   Container ID: {container_id}")
            print(f"   IP Address: {ip_addr}")
            return container_id
            
        except sqlite3.Error as e:
            print(f"❌ Failed to create container: {e}")
            print(f"   Details: name={name}, image={image}")
            import traceback
            traceback.print_exc()
            return None
    
    def start_container(self, name_or_id: str) -> bool:
        """Start container"""
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute('''
                SELECT id, name, ip_address, command FROM containers 
                WHERE name = ? OR id = ?
            ''', (name_or_id, name_or_id))
            
            container = cursor.fetchone()
            if not container:
                print(f"❌ Container not found: {name_or_id}")
                return False
            
            cid, cname, ip_addr, cmd = container
            
            # Simulate starting
            import random
            pid = random.randint(1000, 9999)
            
            cursor.execute('''
                UPDATE containers 
                SET status = ?, started_time = ?, pid = ?
                WHERE id = ?
            ''', ('running', time.time(), pid, cid))
            
            self.db_manager.conn.commit()
            
            # Add to network
            self.network['bridge0']['containers'][cid] = {
                'name': cname,
                'ip': ip_addr,
                'pid': pid
            }
            
            print(f"✅ Container started: {cname}")
            print(f"   PID: {pid}")
            print(f"   IP: {ip_addr}")
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Failed to start container: {e}")
            return False
    
    def stop_container(self, name_or_id: str) -> bool:
        """Stop container"""
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute('''
                SELECT id, name FROM containers 
                WHERE name = ? OR id = ?
            ''', (name_or_id, name_or_id))
            
            container = cursor.fetchone()
            if not container:
                print(f"❌ Container not found: {name_or_id}")
                return False
            
            cid, cname = container
            
            cursor.execute('''
                UPDATE containers 
                SET status = ?, pid = NULL
                WHERE id = ?
            ''', ('stopped', cid))
            
            self.db_manager.conn.commit()
            
            # Remove from network
            if cid in self.network['bridge0']['containers']:
                del self.network['bridge0']['containers'][cid]
            
            print(f"✅ Container stopped: {cname}")
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Failed to stop container: {e}")
            return False
    
    def remove_container(self, name_or_id: str, force: bool = False) -> bool:
        """Remove container"""
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute('''
                SELECT id, name, status FROM containers 
                WHERE name = ? OR id = ?
            ''', (name_or_id, name_or_id))
            
            container = cursor.fetchone()
            if not container:
                print(f"❌ Container not found: {name_or_id}")
                return False
            
            cid, cname, status = container
            
            if status == 'running' and not force:
                print(f"❌ Cannot remove running container. Use force=True")
                return False
            
            cursor.execute('DELETE FROM containers WHERE id = ?', (cid,))
            self.db_manager.conn.commit()
            
            print(f"✅ Container removed: {cname}")
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Failed to remove container: {e}")
            return False
    
    def list_containers(self, all_containers: bool = False) -> List[Dict]:
        """List containers"""
        try:
            cursor = self.db_manager.conn.cursor()
            
            if all_containers:
                cursor.execute('SELECT * FROM containers ORDER BY created_time DESC')
            else:
                cursor.execute('''
                    SELECT * FROM containers 
                    WHERE status = "running" 
                    ORDER BY created_time DESC
                ''')
            
            containers = []
            for row in cursor.fetchall():
                try:
                    containers.append(dict(row))
                except Exception as e:
                    print(f"⚠️  Skipping corrupted container entry: {e}")
                    continue
            return containers
            
        except sqlite3.Error as e:
            print(f"⚠️  Error listing containers: {e}")
            print(f"💡 Try: dbfix or cclean")
            return []
    
    def exec_container(self, name_or_id: str, command: str) -> str:
        """Execute command in container"""
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute('''
                SELECT name, status FROM containers 
                WHERE name = ? OR id = ?
            ''', (name_or_id, name_or_id))
            
            container = cursor.fetchone()
            if not container:
                return f"❌ Container not found: {name_or_id}"
            
            cname, status = container
            
            if status != 'running':
                return f"❌ Container is not running: {cname}"
            
            # Simulate command execution
            output = f"[{cname}]$ {command}\n"
            output += f"Command executed in container {cname}\n"
            output += f"(simulated output)"
            
            return output
            
        except sqlite3.Error as e:
            return f"❌ Error: {e}"
    
    def inspect_container(self, name_or_id: str) -> Optional[Dict]:
        """Inspect container details"""
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute('''
                SELECT * FROM containers 
                WHERE name = ? OR id = ?
            ''', (name_or_id, name_or_id))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
            
        except sqlite3.Error as e:
            print(f"⚠️  Error inspecting container: {e}")
            return None
    
    def network_inspect(self, network_name: str = 'bridge0') -> Dict:
        """Inspect network"""
        if network_name in self.network:
            return self.network[network_name]
        return {}


# ===== INTEGRATED CLI =====

class KernelAddCLI:
    """Integrated CLI untuk package manager dan kernel"""
    
    def __init__(self):
        self.pm = AddPackageManager()
        self.kernel = MiniKernel()
        self.container = ContainerEngine(self.pm.db_manager, self.pm.prefix)
        
        # Initialize driver manager if available
        if DRIVERS_AVAILABLE:
            self.drivers = DriverManager()
        else:
            self.drivers = None
        
        # Commands
        self.commands = {
            # Package Manager Commands (add)
            'update': self._cmd_update,
            'install': self._cmd_install,
            'remove': self._cmd_remove,
            'search': self._cmd_search,
            'list': self._cmd_list,
            'info': self._cmd_info,
            'clean': self._cmd_clean,
            'mirror': self._cmd_mirror,
            'autoremove': self._cmd_autoremove,
            
            # Kernel Commands (kernel-add)
            'kernel': self._cmd_kernel_mode,
            'exec': self._cmd_exec,
            'kill': self._cmd_kill,
            'ps': self._cmd_ps,
            'malloc': self._cmd_malloc,
            'free': self._cmd_free,
            'mem': self._cmd_mem,
            'write': self._cmd_write,
            'read': self._cmd_read,
            'ls': self._cmd_ls,
            'mount': self._cmd_mount,
            'unmount': self._cmd_unmount,
            'devices': self._cmd_devices,
            'logs': self._cmd_logs,
            'kstatus': self._cmd_kstatus,
            'ksave': self._cmd_ksave,
            'kload': self._cmd_kload,
            
            # Integrated Commands
            'kinstall': self._cmd_kinstall,
            'kremove': self._cmd_kremove,
            'klist': self._cmd_klist,
            'test': self._cmd_test,
            
            # Hidden Filesystem Commands
            'hwrite': self._cmd_hwrite,
            'hread': self._cmd_hread,
            'hls': self._cmd_hls,
            'hrm': self._cmd_hrm,
            
            # Regular Filesystem Commands
            'cat': self._cmd_cat,
            'fls': self._cmd_fls,
            'fwrite': self._cmd_fwrite,
            
            # Database Management
            'repair': self._cmd_repair,
            'dbfix': self._cmd_dbfix,
            'dbclean': self._cmd_dbclean,
            
            # Container Commands
            'cimage': self._cmd_cimage,
            'crun': self._cmd_crun,
            'cstart': self._cmd_cstart,
            'cstop': self._cmd_cstop,
            'crm': self._cmd_crm,
            'cps': self._cmd_cps,
            'cexec': self._cmd_cexec,
            'cinspect': self._cmd_cinspect,
            'cnetwork': self._cmd_cnetwork,
            'cclean': self._cmd_cclean,
            
            # Driver Commands
            'lsmod': self._cmd_lsmod,
            'modprobe': self._cmd_modprobe,
            'rmmod': self._cmd_rmmod,
            'lsdev': self._cmd_lsdev,
            'drvinfo': self._cmd_drvinfo,
            
            'help': self._cmd_help
        }
    
    # ===== PACKAGE MANAGER COMMANDS =====
    
    def _cmd_update(self, args):
        """Update package list"""
        self.pm.update()
    
    def _cmd_install(self, args):
        """Install package"""
        if not args:
            print("❌ Usage: add install <package>")
            return
        
        for pkg in args:
            self.pm.install(pkg)
    
    def _cmd_remove(self, args):
        """Remove package"""
        if not args:
            print("❌ Usage: add remove <package>")
            return
        
        for pkg in args:
            self.pm.remove(pkg)
    
    def _cmd_search(self, args):
        """Search packages"""
        if not args:
            print("❌ Usage: add search <query>")
            return
        
        query = ' '.join(args)
        results = self.pm.search(query)
        
        if results:
            print(f"\n🔍 Found {len(results)} packages:")
            print(f"{'St':<3} {'Package':<20} {'Version':<15} {'Description'}")
            print("-" * 70)
            for pkg in results[:20]:
                print(f"{pkg['status']:<3} {pkg['name']:<20} {pkg['version']:<15} {pkg['description'][:30]}...")
        else:
            print("❌ No packages found")
    
    def _cmd_list(self, args):
        """List installed packages"""
        installed = self.pm.list_installed()
        if installed:
            print(f"\n📦 Installed packages ({len(installed)}):")
            print(f"{'Package':<20} {'Version':<15} {'Size'}")
            print("-" * 70)
            for pkg in installed:
                size_mb = pkg['size'] / 1024 / 1024
                print(f"{pkg['name']:<20} {pkg['version']:<15} {size_mb:.1f} MB")
        else:
            print("📭 No packages installed")
    
    def _cmd_info(self, args):
        """Show package info"""
        if not args:
            print("❌ Usage: add info <package>")
            return
        
        self.pm.info(args[0])
    
    def _cmd_clean(self, args):
        """Clean cache"""
        self.pm.clean()
    
    def _cmd_autoremove(self, args):
        """Remove orphaned packages"""
        self.pm.autoremove()
    
    def _cmd_mirror(self, args):
        """Manage mirrors"""
        if not args:
            self.pm.mirror_list()
            return
        
        if args[0] == 'list':
            self.pm.mirror_list()
        elif args[0] == 'set' and len(args) > 1:
            try:
                idx = int(args[1]) - 1
                self.pm.mirror_set(idx)
            except:
                print("❌ Invalid mirror number")
    
    # ===== KERNEL COMMANDS =====
    
    def _cmd_kernel_mode(self, args):
        """Enter kernel interactive mode"""
        print("""
╔══════════════════════════════════════╗
║        KERNEL-ADD MODE v1.0.0        ║
╚══════════════════════════════════════╝
Type 'exit' to return to main shell
        """)
        
        while True:
            try:
                cmd = input("kernel> ").strip().split()
                if not cmd:
                    continue
                
                action = cmd[0].lower()
                
                if action == 'exit':
                    break
                elif action in self.commands:
                    self.commands[action](cmd[1:])
                else:
                    print(f"❌ Unknown command: {action}")
            
            except KeyboardInterrupt:
                print("\nUse 'exit' to leave kernel mode")
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def _cmd_exec(self, args):
        """Execute process"""
        if len(args) < 2:
            print("❌ Usage: exec <pid> <name> [cmd]")
            return
        
        pid = int(args[0]) if args[0].isdigit() else len(self.kernel.state['processes']) + 1
        name = args[1]
        cmd = ' '.join(args[2:]) if len(args) > 2 else ""
        result = self.kernel.syscall('exec', pid, name, cmd)
        print(result)
    
    def _cmd_kill(self, args):
        """Kill process"""
        if not args:
            print("❌ Usage: kill <pid>")
            return
        
        pid = int(args[0])
        result = self.kernel.syscall('kill', pid)
        print(result)
    
    def _cmd_ps(self, args):
        """List processes"""
        print("\n" + "="*70)
        print(f"{'PID':<8} {'NAME':<20} {'STATE':<12} {'COMMAND'}")
        print("-"*70)
        
        for pid, proc in self.kernel.state['processes'].items():
            print(f"{pid:<8} {proc['name']:<20} {proc['state']:<12} {proc['command'][:30]}")
        
        print("="*70)
    
    def _cmd_malloc(self, args):
        """Allocate memory"""
        if not args:
            print("❌ Usage: malloc <size> [label]")
            return
        
        size = int(args[0])
        label = args[1] if len(args) > 1 else "unnamed"
        result = self.kernel.syscall('mem_alloc', size, label)
        print(result)
    
    def _cmd_free(self, args):
        """Free memory"""
        if not args:
            print("❌ Usage: free <addr>")
            return
        
        addr = args[0]
        result = self.kernel.syscall('mem_free', addr)
        print(result)
    
    def _cmd_mem(self, args):
        """Show memory info"""
        total_allocated = sum(m['size'] for m in self.kernel.state['memory'].values())
        
        print("\n" + "="*70)
        print(f"Memory Usage: {total_allocated:,} bytes ({total_allocated/1024:.1f} KB)")
        print("-"*70)
        print(f"{'ADDRESS':<12} {'SIZE':<12} {'LABEL'}")
        print("-"*70)
        
        for addr, mem in self.kernel.state['memory'].items():
            print(f"{addr:<12} {mem['size']:>8} B   {mem['label']}")
        
        print("="*70)
    
    def _cmd_write(self, args):
        """Write file"""
        if len(args) < 2:
            print("❌ Usage: write <path> <data>")
            return
        
        filepath = args[0]
        data = ' '.join(args[1:])
        result = self.kernel.syscall('write', filepath, data)
        print(result)
    
    def _cmd_read(self, args):
        """Read file"""
        if not args:
            print("❌ Usage: read <path>")
            return
        
        filepath = args[0]
        result = self.kernel.syscall('read', filepath)
        print(result)
    
    def _cmd_ls(self, args):
        """List files"""
        print("\n" + "="*70)
        print(f"{'FILEPATH':<40} {'SIZE':<10}")
        print("-"*70)
        
        for filepath, file_info in self.kernel.state['files'].items():
            print(f"{filepath:<40} {file_info['size']:>6} B")
        
        print("="*70)
    
    def _cmd_mount(self, args):
        """Mount device"""
        if len(args) < 2:
            print("❌ Usage: mount <device> <mountpoint>")
            return
        
        device = args[0]
        mountpoint = args[1]
        result = self.kernel.syscall('mount', device, mountpoint)
        print(result)
    
    def _cmd_unmount(self, args):
        """Unmount device"""
        if not args:
            print("❌ Usage: unmount <mountpoint>")
            return
        
        mountpoint = args[0]
        result = self.kernel.syscall('unmount', mountpoint)
        print(result)
    
    def _cmd_devices(self, args):
        """List devices"""
        print("\n" + "="*70)
        print(f"{'ID':<10} {'DEVICE':<25} {'MOUNTPOINT':<25} {'STATUS'}")
        print("-"*70)
        
        for dev_id, dev in self.kernel.state['devices'].items():
            print(f"{dev_id:<10} {dev['device']:<25} {dev['mountpoint']:<25} {dev['status']}")
        
        print("="*70)
    
    def _cmd_logs(self, args):
        """Show logs"""
        n = int(args[0]) if args and args[0].isdigit() else 20
        
        print("\n" + "="*70)
        print(f"KERNEL LOGS (last {n})")
        print("-"*70)
        
        for log in self.kernel.state['logs'][-n:]:
            print(log)
        
        print("="*70)
    
    def _cmd_kstatus(self, args):
        """Show kernel status"""
        self.kernel.status()
    
    def _cmd_ksave(self, args):
        """Save kernel state"""
        filepath = args[0] if args else None
        self.kernel.save(filepath)
    
    def _cmd_kload(self, args):
        """Load kernel state"""
        filepath = args[0] if args else None
        self.kernel.load(filepath)
    
    # ===== INTEGRATED COMMANDS =====
    
    def _cmd_kinstall(self, args):
        """Install package via kernel syscall"""
        if not args:
            print("❌ Usage: kinstall <package>")
            return
        
        for pkg in args:
            self.kernel.syscall('pkg_install', pkg, self.pm)
    
    def _cmd_kremove(self, args):
        """Remove package via kernel syscall"""
        if not args:
            print("❌ Usage: kremove <package>")
            return
        
        for pkg in args:
            self.kernel.syscall('pkg_remove', pkg, self.pm)
    
    def _cmd_klist(self, args):
        """List packages via kernel syscall"""
        result = self.kernel.syscall('pkg_list', self.pm)
        print(result)
    
    def _cmd_test(self, args):
        """Run test scenario"""
        print("\n🧪 Running integrated test scenario...\n")
        
        # Test 1: Update and install packages
        print("1️⃣ Package Management")
        self.pm.update()
        self.pm.install('python', simulate=True)
        self.pm.install('git', simulate=True)
        time.sleep(0.5)
        
        # Test 2: Kernel operations
        print("\n2️⃣ Kernel Operations")
        self.kernel.syscall('exec', 1, 'python', 'python3 app.py')
        self.kernel.syscall('exec', 2, 'git', 'git clone repo')
        self.kernel.syscall('mem_alloc', 2048, 'python_heap')
        self.kernel.syscall('write', '/etc/config.json', '{"version": "1.0"}')
        self.kernel.syscall('mount', '/dev/sda1', '/mnt/data')
        time.sleep(0.5)
        
        # Test 3: Show status
        print("\n3️⃣ System Status")
        self.kernel.status()
        
        print("\n✅ Test complete!")
    
    # ===== HIDDEN FILESYSTEM COMMANDS =====
    
    def _cmd_hwrite(self, args):
        """Write to hidden filesystem"""
        if len(args) < 2:
            print("❌ Usage: hwrite <path> <content>")
            return
        
        path = args[0]
        content = ' '.join(args[1:])
        
        if self.pm.db_manager.write_hidden_file(path, content.encode()):
            print(f"✅ Hidden file written: {path}")
        else:
            print(f"❌ Failed to write hidden file")
    
    def _cmd_hread(self, args):
        """Read from hidden filesystem"""
        if not args:
            print("❌ Usage: hread <path>")
            print("💡 Hidden files are stored in SQLite database, not on disk")
            print("💡 Use 'hls' to list hidden files")
            print("💡 Use 'cat' to read regular files from disk")
            return
        
        path = args[0]
        content = self.pm.db_manager.read_hidden_file(path)
        
        if content:
            print(f"\n📄 Hidden File: {path}")
            print("="*70)
            try:
                print(content.decode())
            except:
                print(f"<binary data: {len(content)} bytes>")
            print("="*70)
        else:
            print(f"❌ Hidden file not found: {path}")
            print("\n💡 Hidden files are NOT regular files on disk!")
            print("💡 They are stored in the SQLite database.")
            print("\n📋 Available hidden files:")
            
            # Show available hidden files
            files = self.pm.db_manager.list_hidden_files()
            if files:
                for f in files:
                    print(f"   - {f['path']}")
            else:
                print("   (none)")
            
            print("\n💡 If you want to read a regular file, use: cat <path>")
    
    def _cmd_hls(self, args):
        """List hidden filesystem"""
        files = self.pm.db_manager.list_hidden_files()
        
        if files:
            print("\n🔒 Hidden Filesystem:")
            print("="*70)
            print(f"{'PATH':<40} {'SIZE':<15} {'MODIFIED'}")
            print("-"*70)
            for file in files:
                modified = time.ctime(file['modified_time'])
                print(f"{file['path']:<40} {file['size']:>10} B    {modified}")
            print("="*70)
            print(f"Total: {len(files)} hidden file(s)")
        else:
            print("📭 No hidden files")
    
    def _cmd_hrm(self, args):
        """Delete hidden file"""
        if not args:
            print("❌ Usage: hrm <path>")
            return
        
        path = args[0]
        if self.pm.db_manager.delete_hidden_file(path):
            print(f"✅ Hidden file deleted: {path}")
        else:
            print(f"❌ Failed to delete hidden file")
    
    # ===== REGULAR FILESYSTEM COMMANDS =====
    
    def _cmd_cat(self, args):
        """Read file from disk"""
        if not args:
            print("❌ Usage: cat <path>")
            print("💡 Use absolute path or relative to ~/.kernel-add/")
            return
        
        filepath = args[0]
        
        # Handle relative paths
        if not filepath.startswith('/'):
            filepath = os.path.join(self.pm.prefix, filepath)
        
        # Expand home directory
        filepath = os.path.expanduser(filepath)
        
        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            
            # Show suggestions
            dirname = os.path.dirname(filepath)
            if os.path.exists(dirname):
                print(f"\n💡 Files in {dirname}:")
                try:
                    for item in os.listdir(dirname):
                        item_path = os.path.join(dirname, item)
                        if os.path.isfile(item_path):
                            print(f"   - {item}")
                except:
                    pass
            return
        
        if not os.path.isfile(filepath):
            print(f"❌ Not a file: {filepath}")
            return
        
        try:
            # Get file info
            file_size = os.path.getsize(filepath)
            file_mtime = time.ctime(os.path.getmtime(filepath))
            
            print(f"\n📄 File: {filepath}")
            print(f"   Size: {file_size:,} bytes")
            print(f"   Modified: {file_mtime}")
            print("="*70)
            
            # Read and display content
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Limit display if too large
                if file_size > 10000:
                    print(content[:5000])
                    print(f"\n... (showing first 5000 bytes of {file_size:,} total)")
                    print(f"\n💡 File is large. Use: cat {filepath} to see full content")
                else:
                    print(content)
            
            print("="*70)
            
        except Exception as e:
            print(f"❌ Error reading file: {e}")
    
    def _cmd_fls(self, args):
        """List files in directory"""
        path = args[0] if args else self.pm.prefix
        
        # Handle relative paths
        if not path.startswith('/'):
            path = os.path.join(self.pm.prefix, path)
        
        path = os.path.expanduser(path)
        
        if not os.path.exists(path):
            print(f"❌ Path not found: {path}")
            return
        
        print(f"\n📁 Directory: {path}")
        print("="*70)
        
        try:
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    mtime = time.ctime(os.path.getmtime(item_path))
                    items.append({
                        'type': 'file',
                        'name': item,
                        'size': size,
                        'mtime': mtime
                    })
                elif os.path.isdir(item_path):
                    items.append({
                        'type': 'dir',
                        'name': item + '/',
                        'size': 0,
                        'mtime': ''
                    })
            
            # Sort: directories first, then files
            items.sort(key=lambda x: (x['type'] == 'file', x['name']))
            
            if items:
                print(f"{'NAME':<40} {'TYPE':<8} {'SIZE':<15} {'MODIFIED'}")
                print("-"*70)
                
                for item in items:
                    if item['type'] == 'dir':
                        print(f"{item['name']:<40} {'DIR':<8} {'-':<15}")
                    else:
                        size_str = f"{item['size']:,} B"
                        print(f"{item['name']:<40} {'FILE':<8} {size_str:<15} {item['mtime']}")
                
                file_count = sum(1 for i in items if i['type'] == 'file')
                dir_count = sum(1 for i in items if i['type'] == 'dir')
                print("-"*70)
                print(f"Total: {dir_count} directories, {file_count} files")
            else:
                print("(empty directory)")
            
        except Exception as e:
            print(f"❌ Error listing directory: {e}")
        
        print("="*70)
    
    def _cmd_fwrite(self, args):
        """Write file to disk"""
        if len(args) < 2:
            print("❌ Usage: fwrite <path> <content>")
            return
        
        filepath = args[0]
        content = ' '.join(args[1:])
        
        # Handle relative paths
        if not filepath.startswith('/'):
            filepath = os.path.join(self.pm.prefix, filepath)
        
        filepath = os.path.expanduser(filepath)
        
        # Create directory if needed
        dirname = os.path.dirname(filepath)
        if dirname and not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
                print(f"📁 Created directory: {dirname}")
            except Exception as e:
                print(f"❌ Failed to create directory: {e}")
                return
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            
            file_size = os.path.getsize(filepath)
            print(f"✅ File written: {filepath}")
            print(f"   Size: {file_size} bytes")
            
        except Exception as e:
            print(f"❌ Error writing file: {e}")
    
    # ===== DATABASE REPAIR COMMAND =====
    
    def _cmd_repair(self, args):
        """Repair corrupted database"""
        print("\n⚠️  WARNING: This will attempt to repair the kernel database")
        print("A backup will be created before repair begins.")
        
        confirm = input("\nProceed with database repair? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("❌ Repair cancelled")
            return
        
        if self.pm.db_manager.repair():
            print("\n✅ Database repair completed successfully")
            print("💡 You may need to restart the kernel for changes to take effect")
        else:
            print("\n❌ Database repair failed")
            print("💡 Check backup files in var/lib/add/")
    
    def _cmd_dbfix(self, args):
        """Fix common database issues (duplicates, constraints)"""
        print("🔧 Running database diagnostics and fixes...")
        print("")
        
        try:
            cursor = self.pm.db_manager.conn.cursor()
            
            # Check 1: Find duplicate packages
            print("1️⃣ Checking for duplicate packages...")
            cursor.execute('''
                SELECT name, COUNT(*) as count 
                FROM packages 
                GROUP BY name 
                HAVING count > 1
            ''')
            duplicates = cursor.fetchall()
            
            if duplicates:
                print(f"   Found {len(duplicates)} duplicate(s)")
                for dup in duplicates:
                    print(f"   - {dup[0]}: {dup[1]} entries")
            else:
                print("   ✅ No duplicates found")
            
            # Check 2: Fix container constraints
            print("\n2️⃣ Checking container constraints...")
            cursor.execute('SELECT COUNT(*) FROM containers')
            container_count = cursor.fetchone()[0]
            print(f"   Total containers: {container_count}")
            
            # Check 3: Fix image constraints
            print("\n3️⃣ Checking image constraints...")
            cursor.execute('SELECT COUNT(*) FROM images')
            image_count = cursor.fetchone()[0]
            print(f"   Total images: {image_count}")
            
            # Check 4: Orphaned dependencies
            print("\n4️⃣ Checking orphaned dependencies...")
            cursor.execute('''
                SELECT COUNT(*) FROM dependencies 
                WHERE package NOT IN (SELECT name FROM packages)
                   OR depends_on NOT IN (SELECT name FROM packages)
            ''')
            orphaned_deps = cursor.fetchone()[0]
            
            if orphaned_deps > 0:
                print(f"   Found {orphaned_deps} orphaned dependencies")
                print("   Cleaning...")
                cursor.execute('''
                    DELETE FROM dependencies 
                    WHERE package NOT IN (SELECT name FROM packages)
                       OR depends_on NOT IN (SELECT name FROM packages)
                ''')
                self.pm.db_manager.conn.commit()
                print("   ✅ Cleaned")
            else:
                print("   ✅ No orphaned dependencies")
            
            # Check 5: Database integrity
            print("\n5️⃣ Running PRAGMA integrity_check...")
            cursor.execute('PRAGMA integrity_check')
            integrity = cursor.fetchone()[0]
            
            if integrity == 'ok':
                print("   ✅ Database integrity OK")
            else:
                print(f"   ⚠️  Integrity check: {integrity}")
            
            print("\n✅ Database diagnostics complete")
            
        except Exception as e:
            print(f"❌ Error during dbfix: {e}")
            import traceback
            traceback.print_exc()
    
    def _cmd_dbclean(self, args):
        """Clean ALL database data (RESET)"""
        print("\n⚠️  ⚠️  ⚠️  DANGER ZONE ⚠️  ⚠️  ⚠️")
        print("This will DELETE ALL DATA:")
        print("  - All installed packages")
        print("  - All containers and images")
        print("  - All hidden files")
        print("  - All dependencies")
        print("")
        
        confirm = input("Type 'DELETE EVERYTHING' to confirm: ").strip()
        
        if confirm != 'DELETE EVERYTHING':
            print("❌ Cancelled (safe!)")
            return
        
        print("\n🗑️  Deleting all data...")
        
        try:
            cursor = self.pm.db_manager.conn.cursor()
            
            # Delete all data from all tables
            tables = ['packages', 'dependencies', 'hidden_files', 
                     'containers', 'images', 'volumes', 'metadata']
            
            for table in tables:
                try:
                    cursor.execute(f'DELETE FROM {table}')
                    deleted = cursor.rowcount
                    print(f"   ✅ Deleted {deleted} rows from {table}")
                except sqlite3.Error as e:
                    print(f"   ⚠️  {table}: {e}")
            # Commit changes
            self.pm.db_manager.conn.commit()
            cursor.close()

            print("\n✅ Database cleaned successfully")
            print("💡 All data has been removed. Start fresh!")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
    
    # ===== CONTAINER ENGINE COMMANDS =====
    
    def _cmd_cimage(self, args):
        """Manage container images"""
        if not args or args[0] == 'ls':
            # List images
            images = self.container.list_images()
            if images:
                print("\n🐳 Container Images:")
                print("="*80)
                print(f"{'IMAGE ID':<15} {'NAME':<20} {'TAG':<10} {'SIZE':<15} {'CREATED'}")
                print("-"*80)
                for img in images:
                    size_mb = img['size'] / (1024 * 1024)
                    created = time.ctime(img['created_time'])
                    print(f"{img['id']:<15} {img['name']:<20} {img['tag']:<10} {size_mb:>10.1f} MB  {created}")
                print("="*80)
            else:
                print("📭 No images found")
        
        elif args[0] == 'create':
            if len(args) < 2:
                print("❌ Usage: cimage create <name> [tag]")
                return
            name = args[1]
            tag = args[2] if len(args) > 2 else 'latest'
            self.container.create_image(name, tag)
    
    def _cmd_crun(self, args):
        """Create and start container"""
        if len(args) < 2:
            print("❌ Usage: crun <name> <image> [command]")
            return
        
        name = args[0]
        image = args[1]
        command = ' '.join(args[2:]) if len(args) > 2 else '/bin/sh'
        
        # Create container
        container_id = self.container.create_container(name, image, command)
        if container_id:
            # Start immediately
            self.container.start_container(container_id)
    
    def _cmd_cstart(self, args):
        """Start container"""
        if not args:
            print("❌ Usage: cstart <container>")
            return
        
        self.container.start_container(args[0])
    
    def _cmd_cstop(self, args):
        """Stop container"""
        if not args:
            print("❌ Usage: cstop <container>")
            return
        
        self.container.stop_container(args[0])
    
    def _cmd_crm(self, args):
        """Remove container"""
        if not args:
            print("❌ Usage: crm <container> [-f]")
            return
        
        force = '-f' in args
        name = args[0]
        self.container.remove_container(name, force=force)
    
    def _cmd_cps(self, args):
        """List containers"""
        show_all = '-a' in args or '--all' in args
        
        containers = self.container.list_containers(all_containers=show_all)
        
        if containers:
            print("\n🐳 Containers:")
            print("="*110)
            print(f"{'CONTAINER ID':<15} {'NAME':<20} {'IMAGE ID':<15} {'STATUS':<10} {'IP ADDRESS':<15} {'PORTS'}")
            print("-"*110)
            
            for ctr in containers:
                ports = json.loads(ctr.get('ports', '[]'))
                ports_str = ', '.join(ports) if ports else '-'
                
                print(f"{ctr['id']:<15} {ctr['name']:<20} {ctr['image_id']:<15} "
                      f"{ctr['status']:<10} {ctr.get('ip_address', '-'):<15} {ports_str}")
            
            print("="*110)
            print(f"Total: {len(containers)} container(s)")
        else:
            status_msg = "all" if show_all else "running"
            print(f"📭 No {status_msg} containers")
    
    def _cmd_cexec(self, args):
        """Execute command in container"""
        if len(args) < 2:
            print("❌ Usage: cexec <container> <command>")
            return
        
        container = args[0]
        command = ' '.join(args[1:])
        
        result = self.container.exec_container(container, command)
        print(result)
    
    def _cmd_cinspect(self, args):
        """Inspect container"""
        if not args:
            print("❌ Usage: cinspect <container>")
            return
        
        container_info = self.container.inspect_container(args[0])
        
        if container_info:
            print(f"\n🔍 Container Inspection:")
            print("="*70)
            print(f"ID:          {container_info['id']}")
            print(f"Name:        {container_info['name']}")
            print(f"Image ID:    {container_info['image_id']}")
            print(f"Status:      {container_info['status']}")
            print(f"IP Address:  {container_info.get('ip_address', 'N/A')}")
            print(f"PID:         {container_info.get('pid', 'N/A')}")
            print(f"Command:     {container_info.get('command', 'N/A')}")
            
            created = time.ctime(container_info['created_time'])
            print(f"Created:     {created}")
            
            if container_info.get('started_time'):
                started = time.ctime(container_info['started_time'])
                print(f"Started:     {started}")
            
            ports = json.loads(container_info.get('ports', '[]'))
            if ports:
                print(f"Ports:       {', '.join(ports)}")
            
            volumes = json.loads(container_info.get('volumes', '[]'))
            if volumes:
                print(f"Volumes:     {', '.join(volumes)}")
            
            env = json.loads(container_info.get('env_vars', '{}'))
            if env:
                print(f"Environment:")
                for k, v in env.items():
                    print(f"  {k}={v}")
            
            print("="*70)
        else:
            print(f"❌ Container not found: {args[0]}")
    
    def _cmd_cnetwork(self, args):
        """Inspect container network"""
        network_name = args[0] if args else 'bridge0'
        
        network = self.container.network_inspect(network_name)
        
        if network:
            print(f"\n🌐 Network: {network_name}")
            print("="*70)
            print(f"Subnet:      {network.get('subnet')}")
            print(f"Gateway:     {network.get('gateway')}")
            print(f"\nConnected Containers:")
            print("-"*70)
            
            containers = network.get('containers', {})
            if containers:
                print(f"{'CONTAINER ID':<15} {'NAME':<20} {'IP ADDRESS':<15} {'PID'}")
                print("-"*70)
                for cid, cinfo in containers.items():
                    print(f"{cid:<15} {cinfo['name']:<20} {cinfo['ip']:<15} {cinfo['pid']}")
            else:
                print("No containers connected")
            
            print("="*70)
        else:
            print(f"❌ Network not found: {network_name}")
    
    def _cmd_cclean(self, args):
        """Clean all container data (reset)"""
        if not self.container:
            print("❌ Container engine not available")
            return
        
        print("⚠️  WARNING: This will delete ALL containers and images!")
        confirm = input("Are you sure? Type 'yes' to confirm: ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Cancelled")
            return
        
        try:
            cursor = self.pm.db_manager.conn.cursor()
            
            # Delete all containers
            cursor.execute('DELETE FROM containers')
            deleted_containers = cursor.rowcount
            
            # Delete all images
            cursor.execute('DELETE FROM images')
            deleted_images = cursor.rowcount
            
            # Delete all volumes
            cursor.execute('DELETE FROM volumes')
            
            self.pm.db_manager.conn.commit()
            
            # Reset network
            self.container.network['bridge0']['containers'] = {}
            
            print(f"✅ Container data cleaned")
            print(f"   Deleted {deleted_containers} container(s)")
            print(f"   Deleted {deleted_images} image(s)")
            print(f"💡 You can now create fresh containers without conflicts")
            
        except Exception as e:
            print(f"❌ Error cleaning container data: {e}")
    
    # ===== DRIVER MANAGEMENT COMMANDS =====
    
    def _cmd_lsmod(self, args):
        """List loaded kernel modules/drivers"""
        if not self.drivers:
            print("❌ Driver system not available")
            return
        
        drivers = self.drivers.list_drivers()
        
        print("\n🔧 Kernel Drivers:")
        print("="*90)
        print(f"{'NAME':<15} {'FULL NAME':<25} {'VERSION':<12} {'STATUS':<12} {'DEVICES'}")
        print("-"*90)
        
        for drv in drivers:
            status_icon = "✅" if drv['loaded'] else "⭕"
            print(f"{drv['name']:<15} {drv['full_name']:<25} {drv['version']:<12} "
                  f"{status_icon} {drv['status']:<10} {drv['devices']}")
        
        print("="*90)
        print(f"Total: {len(drivers)} drivers ({len(self.drivers.loaded_drivers)} loaded)")
    
    def _cmd_modprobe(self, args):
        """Load kernel module/driver"""
        if not self.drivers:
            print("❌ Driver system not available")
            return
        
        if not args:
            print("❌ Usage: modprobe <driver>")
            print("💡 Available drivers: block, network, usb, gpu")
            return
        
        driver_name = args[0]
        self.drivers.load_driver(driver_name)
    
    def _cmd_rmmod(self, args):
        """Unload kernel module/driver"""
        if not self.drivers:
            print("❌ Driver system not available")
            return
        
        if not args:
            print("❌ Usage: rmmod <driver>")
            return
        
        driver_name = args[0]
        self.drivers.unload_driver(driver_name)
    
    def _cmd_lsdev(self, args):
        """List all detected devices"""
        if not self.drivers:
            print("❌ Driver system not available")
            return
        
        all_devices = self.drivers.get_all_devices()
        
        if not all_devices:
            print("📭 No devices detected (load drivers first)")
            print("💡 Use: modprobe <driver> to load drivers")
            return
        
        print("\n🔍 Detected Hardware Devices:")
        print("="*90)
        
        for driver_type, devices in all_devices.items():
            print(f"\n{driver_type.upper()} DEVICES:")
            print("-"*90)
            
            if driver_type == 'block':
                for dev in devices:
                    size_gb = dev['size'] / (1024**3)
                    mounted = "✓" if dev.get('mounted') else " "
                    print(f"  [{mounted}] {dev['id']:<10} {dev['model']:<30} {size_gb:>8.1f} GB")
            
            elif driver_type == 'network':
                for dev in devices:
                    state = "UP" if dev['state'] == 'up' else "DOWN"
                    ip = dev.get('ip') or 'N/A'
                    print(f"  [{state}] {dev['id']:<10} {dev['type']:<15} MAC: {dev['mac']:<20} IP: {ip}")
            
            elif driver_type == 'usb':
                for dev in devices:
                    print(f"  {dev['id']:<12} {dev['vendor']:<15} {dev['product']:<30} {dev['type']}")
            
            elif driver_type == 'gpu':
                for dev in devices:
                    vram_gb = dev['vram'] / 1024
                    print(f"  {dev['id']:<8} {dev['vendor']} {dev['model']:<30} VRAM: {vram_gb:.0f}GB")
        
        print("="*90)
    
    def _cmd_drvinfo(self, args):
        """Show detailed driver/device information"""
        if not self.drivers:
            print("❌ Driver system not available")
            return
        
        if not args:
            print("❌ Usage: drvinfo <driver>")
            print("💡 Available: block, network, usb, gpu")
            return
        
        driver_name = args[0]
        driver = self.drivers.get_driver(driver_name)
        
        if not driver:
            print(f"❌ Driver not found: {driver_name}")
            return
        
        if not driver.loaded:
            print(f"⚠️  Driver not loaded: {driver_name}")
            print(f"💡 Use: modprobe {driver_name}")
            return
        
        print(f"\n🔧 Driver Information: {driver.name}")
        print("="*70)
        print(f"Version:       {driver.version}")
        print(f"Status:        {driver.status}")
        print(f"Loaded:        {'Yes' if driver.loaded else 'No'}")
        print(f"Devices:       {len(driver.devices)}")
        print("\nDetected Devices:")
        print("-"*70)
        
        # Show detailed device info based on driver type
        if driver_name == 'gpu' and driver.devices:
            for gpu_id, gpu in driver.devices.items():
                print(f"\n{gpu_id}:")
                print(f"  Model:          {gpu['vendor']} {gpu['model']}")
                print(f"  VRAM:           {gpu['vram'] / 1024:.0f} GB")
                print(f"  PCIe:           {gpu['pcie_gen']}")
                print(f"  Driver Version: {gpu['driver_version']}")
                
                # Get live stats
                stats = driver.get_stats(gpu_id)
                if stats:
                    print(f"  Temperature:    {stats['temperature']}°C")
                    print(f"  Power:          {stats['power_usage']}W")
                    print(f"  Utilization:    {stats['utilization']}%")
                    print(f"  VRAM Used:      {stats['vram_used']} / {stats['vram_total']} MB")
        
        elif driver_name == 'network' and driver.devices:
            for iface_id, iface in driver.devices.items():
                state_icon = "🟢" if iface['state'] == 'up' else "🔴"
                print(f"\n{state_icon} {iface_id}:")
                print(f"  Type:      {iface['type']}")
                print(f"  MAC:       {iface['mac']}")
                print(f"  State:     {iface['state']}")
                print(f"  IP:        {iface.get('ip', 'Not assigned')}")
                print(f"  Speed:     {iface['speed']}")
                print(f"  Driver:    {iface['driver']}")
        
        elif driver_name == 'block' and driver.devices:
            for dev_id, dev in driver.devices.items():
                size_gb = dev['size'] / (1024**3)
                print(f"\n{dev_id}:")
                print(f"  Type:       {dev['type']}")
                print(f"  Model:      {dev['model']}")
                print(f"  Size:       {size_gb:.1f} GB ({dev['size']:,} bytes)")
                print(f"  Mounted:    {'Yes' if dev.get('mounted') else 'No'}")
                if dev.get('mounted'):
                    print(f"  Mountpoint: {dev.get('mountpoint')}")
                if dev.get('partitions'):
                    print(f"  Partitions: {', '.join(dev['partitions'])}")
        
        elif driver_name == 'usb' and driver.devices:
            for usb_id, usb in driver.devices.items():
                print(f"\n{usb_id} (Port {usb['port']}):")
                print(f"  Vendor:     {usb['vendor']} ({usb['vendor_id']})")
                print(f"  Product:    {usb['product']} ({usb['product_id']})")
                print(f"  Type:       {usb['type']}")
                print(f"  Speed:      {usb['speed']}")
        
        print("="*70)
    
    def _cmd_help(self, args):
        """Show help"""
        print("""
╔══════════════════════════════════════╗
║    KERNEL-ADD INTEGRATED SHELL       ║
╚══════════════════════════════════════╝

📦 PACKAGE MANAGER (add):
  update               Update package list
  install <pkg>       Install package
  remove <pkg>        Remove package
  autoremove          Remove orphaned packages
  search <query>      Search packages
  list                List installed packages
  info <pkg>          Show package info
  clean               Clean cache
  mirror list         List mirrors
  mirror set <n>      Set mirror (1-5)

🐧 KERNEL COMMANDS (kernel-add):
  kernel              Enter kernel interactive mode
  exec <pid> <n> [c]  Execute process
  kill <pid>          Kill process
  ps                  List processes
  malloc <sz> [l]     Allocate memory
  free <addr>         Free memory
  mem                 Show memory info
  write <p> <d>       Write file
  read <path>         Read file
  ls                  List files
  mount <d> <m>       Mount device
  unmount <m>         Unmount device
  devices             List devices
  logs [n]            Show logs
  kstatus             Show kernel status
  ksave [file]        Save kernel state
  kload [file]        Load kernel state

🔗 INTEGRATED COMMANDS:
  kinstall <pkg>      Install via kernel syscall
  kremove <pkg>       Remove via kernel syscall
  klist               List via kernel syscall
  test                Run test scenario

🔒 HIDDEN FILESYSTEM (SQLite):
  hwrite <p> <c>      Write to hidden filesystem
  hread <path>        Read from hidden filesystem
  hls                 List hidden files
  hrm <path>          Delete hidden file

📁 REGULAR FILESYSTEM (Disk):
  cat <path>          Read file from disk
  fls [path]          List files/directories
  fwrite <p> <c>      Write file to disk

🔧 DATABASE MANAGEMENT:
  repair              Repair corrupted SQLite database
  dbfix               Fix common database issues
  dbclean             Clean ALL database data (RESET)

🐳 CONTAINER ENGINE:
  cimage ls           List container images
  cimage create <n>   Create new image
  crun <n> <img> [c]  Create and run container
  cstart <ctr>        Start container
  cstop <ctr>         Stop container
  crm <ctr> [-f]      Remove container (force)
  cps [-a]            List containers (all)
  cexec <ctr> <cmd>   Execute command in container
  cinspect <ctr>      Inspect container details
  cnetwork [name]     Inspect container network
  cclean              Clean all container data (RESET)

🔧 DRIVER MANAGEMENT:
  lsmod               List loaded drivers
  modprobe <driver>   Load driver module
  rmmod <driver>      Unload driver module
  lsdev               List all hardware devices
  drvinfo <driver>    Show driver/device details

💡 MIRRORS:
  1. https://mirror.nevacloud.com/applications/termux/termux-main
  2. https://mirror.twds.com.tw/ubuntu/
  3. https://mirror.jeonnam.school/rocky-linux/
  4. https://mirror.alpinelinux.org/alpine/
  5. https://mirror.archlinux.tw/ArchLinux/
        """)
    
    def run(self):
        """Run CLI"""
        if len(sys.argv) < 2:
            self._interactive_shell()
            return
        
        command = sys.argv[1]
        args = sys.argv[2:]
        
        if command in self.commands:
            self.commands[command](args)
        else:
            print(f"❌ Unknown command: {command}")
            self._cmd_help([])
    
    def _interactive_shell(self):
        """Interactive shell"""
        print("""
╔══════════════════════════════════════╗
║    KERNEL-ADD SHELL v1.0.0           ║
║    Package Manager + Mini Kernel     ║
╚══════════════════════════════════════╝
Type 'help' for commands, 'exit' to quit

Active mirror: {}
        """.format(self.pm.current_mirror))
        
        while True:
            try:
                cmd = input("[localhost[@]MiniKernel]>-~& ").strip().split()
                if not cmd:
                    continue
                
                action = cmd[0].lower()
                
                if action == 'exit':
                    save = input("Save kernel state? (y/N): ").lower()
                    if save == 'y':
                        self.kernel.save()
                    print("👋 Goodbye!")
                    break
                
                elif action in self.commands:
                    self.commands[action](cmd[1:])
                
                else:
                    print(f"❌ Unknown command: {action}")
                    print("Type 'help' for available commands")
            
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except Exception as e:
                print(f"❌ Error: {e}")


# ===== MAIN =====

def main():
    """Main entry point"""
    cli = KernelAddCLI()
    cli.run()


if __name__ == "__main__":
    main()
