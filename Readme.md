# Kernel-Add System

Lightweight Linux-like kernel dengan package manager, container engine, driver system, dan GUI.

## 📦 File Structure

```
kernel-add/
├── LinuxKernel.py      # Main kernel & package manager
├── KernelDriver.py     # Hardware driver system
├── gui.py              # Simple GUI interface
└── README.md           # This file
```

## 🚀 Quick Start

### Prerequisites

**Install PyQt6:**
```bash
pip install PyQt6
```

### Terminal Mode (CLI)

```bash
python3 LinuxKernel.py
```

Ini akan membuka interactive shell:
```
[localhost[@]MiniKernel]>-~& 
```

### GUI Mode (PyQt6)

**Install PyQt6 first:**
```bash
pip install PyQt6
```

**Then run:**
```bash
python3 gui.py
```

**Note:** GUI menggunakan PyQt6. Install dulu dengan pip sebelum menjalankan.

## 💻 Features

### 📦 Package Manager
- **SQLite Database** - Robust package tracking
- **5 Mirrors** - Termux, Ubuntu, Rocky Linux, Alpine, Arch
- **Dependencies** - Auto-tracking & resolution
- **Autoremove** - Clean orphaned packages

Commands:
```bash
update                  # Update package list
install <package>       # Install package
remove <package>        # Remove package
autoremove             # Remove orphaned packages
search <query>         # Search packages
list                   # List installed
info <package>         # Show package info
```

### 🔒 Hidden Filesystem
Files stored in SQLite database - **invisible** to `ls -a`!

Commands:
```bash
hwrite <path> <data>   # Write hidden file
hread <path>           # Read hidden file
hls                    # List hidden files
hrm <path>             # Delete hidden file
```

### 📁 Regular Filesystem
Normal file operations:

```bash
cat <path>             # Read file from disk
fls [path]             # List files/directories
fwrite <path> <data>   # Write file to disk
```

### 🐳 Container Engine
Docker-like container management:

```bash
# Images
cimage ls              # List images
cimage create <name>   # Create image

# Containers
crun <name> <image>    # Create & run container
cstart <container>     # Start container
cstop <container>      # Stop container
crm <container> [-f]   # Remove container
cps [-a]              # List containers
cexec <ctr> <cmd>     # Execute in container
cinspect <container>   # Inspect details
cnetwork              # View network
```

### 🔧 Driver System
Hardware driver management:

```bash
lsmod                  # List loaded drivers
modprobe <driver>      # Load driver
rmmod <driver>         # Unload driver
lsdev                  # List all devices
drvinfo <driver>       # Driver details
```

Available drivers:
- **block** - Storage devices (SATA, NVMe, Loop)
- **network** - Network interfaces (eth0, wlan0, lo)
- **usb** - USB devices
- **gpu** - Graphics cards (NVIDIA, AMD)

### 🐧 Kernel Commands

```bash
kernel                 # Enter kernel mode
exec <pid> <n> [c]    # Execute process
kill <pid>            # Kill process
ps                    # List processes
malloc <size> [l]     # Allocate memory
free <addr>           # Free memory
mem                   # Show memory info
write <p> <d>         # Write file
read <path>           # Read file
ls                    # List files
```

### 🔧 Database

```bash
repair                # Repair SQLite database
```

## 📝 Usage Examples

### Example 1: Package Management
```bash
[localhost[@]MiniKernel]>-~& update
[localhost[@]MiniKernel]>-~& search python
[localhost[@]MiniKernel]>-~& install python
[localhost[@]MiniKernel]>-~& list
[localhost[@]MiniKernel]>-~& remove python
[localhost[@]MiniKernel]>-~& autoremove
```

### Example 2: Container Workflow
```bash
# Create images
[localhost[@]MiniKernel]>-~& cimage create ubuntu latest
[localhost[@]MiniKernel]>-~& cimage create python 3.11

# Run containers
[localhost[@]MiniKernel]>-~& crun web-server ubuntu nginx
[localhost[@]MiniKernel]>-~& crun backend python "python app.py"

# Check status
[localhost[@]MiniKernel]>-~& cps
[localhost[@]MiniKernel]>-~& cinspect web-server

# Execute commands
[localhost[@]MiniKernel]>-~& cexec backend "python --version"

# Stop and remove
[localhost[@]MiniKernel]>-~& cstop web-server
[localhost[@]MiniKernel]>-~& crm web-server
```

### Example 3: Driver Management
```bash
# Load drivers
[localhost[@]MiniKernel]>-~& modprobe block
[localhost[@]MiniKernel]>-~& modprobe network
[localhost[@]MiniKernel]>-~& modprobe gpu

# View drivers
[localhost[@]MiniKernel]>-~& lsmod

# View devices
[localhost[@]MiniKernel]>-~& lsdev

# Get GPU info
[localhost[@]MiniKernel]>-~& drvinfo gpu
```

### Example 4: Hidden Filesystem
```bash
# Write secret data
[localhost[@]MiniKernel]>-~& hwrite /secret/password.txt "my_password_123"

# List hidden files
[localhost[@]MiniKernel]>-~& hls

# Read hidden file
[localhost[@]MiniKernel]>-~& hread /secret/password.txt

# Try to find with regular ls (won't work!)
[localhost[@]MiniKernel]>-~& fls
# /secret/password.txt TIDAK akan muncul!

# Delete hidden file
[localhost[@]MiniKernel]>-~& hrm /secret/password.txt
```

## 🎨 GUI Features (Simple v1.0)

GUI menyediakan interface sederhana dengan:

- **📦 Package Manager Buttons** - Update, List, Search
- **🐧 Kernel Buttons** - Status, Processes, Memory
- **🔧 Driver Buttons** - List Drivers, List Devices
- **🐳 Container Buttons** - List Containers, List Images
- **💻 Command Input** - Execute any command
- **📺 Output Console** - Green terminal-style output

### GUI Controls:
- Click buttons untuk quick commands
- Atau ketik command di bawah dan tekan Enter/Execute
- Clear Output button untuk clear console

## 🗂️ File Locations

### Database & Data:
```
~/.kernel-add/
├── var/
│   ├── lib/add/.kernel.db     # SQLite database (hidden!)
│   └── cache/add/             # Package cache
├── containers/                # Container data
├── images/                    # Container images
└── kernel/                    # Kernel state
```

### Hidden Files:
Stored in SQLite database table `hidden_files` - **not** on disk!

## 🛠️ Technical Details

### Database Schema (SQLite):
- `packages` - Installed packages
- `dependencies` - Package dependencies
- `metadata` - System metadata
- `hidden_files` - Hidden filesystem
- `images` - Container images
- `containers` - Container instances
- `volumes` - Container volumes

### Virtual Networking:
- Network: bridge0 (172.17.0.0/16)
- Gateway: 172.17.0.1
- Auto IP allocation for containers

### Driver Architecture:
```python
BaseDriver (Abstract)
├── BlockDriver
├── NetworkDriver
├── USBDriver
└── GPUDriver
```

## 🔐 Security Notes

- Hidden filesystem stored in SQLite (not visible with ls/find)
- Database file is hidden (.kernel.db)
- Container isolation (simulated)
- No actual system modification - all virtual!

## 📚 Help

Type `help` in the shell for full command list:
```bash
[localhost[@]MiniKernel]>-~& help
```

## 🐛 Troubleshooting

### GUI won't start:
- Check DISPLAY environment variable
- Use terminal mode instead: `python3 LinuxKernel.py`

### Database corruption:
```bash
[localhost[@]MiniKernel]>-~& repair
```

### Clear everything:
```bash
rm -rf ~/.kernel-add/
```

## 📈 Roadmap

**Phase 1 - Simple GUI (Current):**
- ✅ Basic button interface
- ✅ Command execution
- ✅ Output console

**Phase 2 - Enhanced GUI (Next):**
- Package manager with search/install UI
- Container management panel
- Driver/device tree view
- System monitor (CPU, memory, network)

**Phase 3 - Advanced GUI (Future):**
- File manager with hidden filesystem
- Container terminal
- Network topology view
- Plugin system

## 💡 Tips

1. **Start with drivers:**
   ```bash
   modprobe block
   modprobe network
   lsdev
   ```

2. **Use hidden filesystem for secrets:**
   ```bash
   hwrite /config/api_key.txt "secret123"
   ```

3. **Container networking:**
   Each container gets auto IP (172.17.0.x)

4. **Save kernel state:**
   ```bash
   ksave
   kload
   ```

## 📄 License

Educational project - MIT License

## 🙏 Credits

Built with Python, SQLite, and Tkinter
Inspired by Linux, Docker, and APT

---

**Version:** 1.0.0  
**Author:** Kernel-Add Development Team  
**Date:** 2026