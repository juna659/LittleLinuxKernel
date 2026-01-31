# Kernel-Add Quick Reference

## 🚀 Installation

```bash
# Install PyQt6
pip install PyQt6

# Or use helper script
bash install.sh
```

## 💻 Running

```bash
# Terminal Mode
python3 LinuxKernel.py

# GUI Mode (PyQt6)
python3 gui.py
```

## 📦 Complete File List

```
kernel-add/
├── LinuxKernel.py      # Main kernel (1800+ lines)
├── KernelDriver.py     # Driver system (700+ lines)
├── gui.py              # PyQt6 GUI (350+ lines)
├── install.sh          # Installation helper
├── README.md           # Full documentation
└── QUICKREF.md         # This file
```

## ⚡ Quick Commands

### Package Manager
```bash
update                  # Update package list
install python          # Install package
remove python           # Remove package  
autoremove             # Clean orphaned packages
search query           # Search packages
list                   # List installed
```

### Containers
```bash
cimage create ubuntu    # Create image
crun web ubuntu nginx   # Run container
cps -a                 # List all containers
cstop web              # Stop container
crm web -f             # Force remove
```

### Drivers
```bash
modprobe block         # Load block driver
lsmod                  # List loaded drivers
lsdev                  # List all devices
drvinfo gpu            # GPU driver info
```

### Hidden Filesystem
```bash
hwrite /secret/key.txt "data"   # Write hidden file
hread /secret/key.txt           # Read hidden file
hls                             # List hidden files
```

### Regular Filesystem
```bash
cat path/to/file       # Read file
fls                    # List files
fwrite file.txt "data" # Write file
```

## 🎯 GUI Quick Guide

### Layout
- **Left Panel:** Quick action buttons
- **Right Panel:** Output console + command input
- **Bottom:** Status bar

### Features
- Click buttons for common tasks
- Type commands in input box
- Thread-based execution (no freeze)
- Terminal-style output (green on black)

## 🔧 Architecture

```
┌──────────┐
│  gui.py  │  ← PyQt6 GUI Layer
└────┬─────┘
     │
┌────▼─────────────┐
│ LinuxKernel.py   │  ← Main Kernel
├──────────────────┤
│ • Package Mgr    │
│ • Container Eng  │
│ • Filesystem     │
│ • Mini Kernel    │
└────┬─────────────┘
     │
┌────▼─────────────┐
│ KernelDriver.py  │  ← Driver Layer
├──────────────────┤
│ • Block Driver   │
│ • Network Driver │
│ • USB Driver     │
│ • GPU Driver     │
└──────────────────┘
```

## 💾 Data Storage

### SQLite Database
```
~/.kernel-add/var/lib/add/.kernel.db
```

**Tables:**
- `packages` - Installed packages
- `dependencies` - Package deps
- `hidden_files` - Hidden filesystem
- `images` - Container images
- `containers` - Container instances
- `volumes` - Container volumes
- `metadata` - System metadata

### Regular Files
```
~/.kernel-add/
├── var/cache/add/     # Package cache
├── containers/        # Container data
├── images/           # Container images
└── kernel/           # Kernel state
```

## 🎮 Example Workflows

### Workflow 1: Setup System
```bash
# Load all drivers
modprobe block
modprobe network
modprobe gpu

# View hardware
lsdev
drvinfo gpu

# Update packages
update
```

### Workflow 2: Deploy App
```bash
# Create images
cimage create ubuntu latest
cimage create python 3.11

# Run containers
crun db ubuntu "postgresql"
crun api python "python app.py"
crun web ubuntu "nginx"

# Check status
cps
cnetwork
```

### Workflow 3: Manage Secrets
```bash
# Store secrets in hidden filesystem
hwrite /secrets/db_password "secret123"
hwrite /secrets/api_key "key_abc"

# List hidden files
hls

# Read when needed
hread /secrets/db_password

# Won't appear in regular ls!
fls
```

## ⚙️ Advanced Features

### Container Networking
- Network: bridge0 (172.17.0.0/16)
- Gateway: 172.17.0.1
- Auto IP assignment

### Database Repair
```bash
repair    # Fix corrupted SQLite DB
```

### Kernel State
```bash
ksave     # Save kernel state
kload     # Load kernel state
```

## 🐛 Troubleshooting

### GUI won't start
```bash
# Install PyQt6
pip install PyQt6

# Or use Tkinter version (built-in)
# Contact support for Tkinter GUI
```

### Database corruption
```bash
repair
```

### Clear all data
```bash
rm -rf ~/.kernel-add/
```

## 📚 Resources

- **Full Docs:** README.md
- **Main Kernel:** LinuxKernel.py
- **Drivers:** KernelDriver.py
- **GUI:** gui.py

## 🎯 Tips

1. **Start simple:** Just run `python3 LinuxKernel.py`
2. **Load drivers:** `modprobe block` → `lsdev`
3. **Try containers:** `cimage create test` → `crun name test sh`
4. **Use GUI:** `python3 gui.py` for user-friendly interface
5. **Hidden files:** Use `h*` commands for secret data

---

**Version:** 1.0.0  
**Last Updated:** 2026-01-31 