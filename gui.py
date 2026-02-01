#!/usr/bin/env python3
"""
gui.py - Simple GUI for Kernel-Add using PyQt6
GUI sederhana - step by step improvement
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit, QTabWidget,
    QGroupBox, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette

# Import kernel components
try:
    from LinuxKernel import KernelAddCLI
    KERNEL_AVAILABLE = True
except ImportError:
    KERNEL_AVAILABLE = False
    print("⚠️  LinuxKernel.py not found")


class CommandThread(QThread):
    """Thread untuk execute commands tanpa freeze GUI"""
    output_ready = pyqtSignal(str)
    
    def __init__(self, cli, command):
        super().__init__()
        self.cli = cli
        self.command = command
    
    def run(self):
        """Execute command dan emit output"""
        import io
        
        # Parse command
        parts = self.command.split()
        if not parts:
            return
        
        action = parts[0].lower()
        args = parts[1:]
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            if action in self.cli.commands:
                self.cli.commands[action](args)
            else:
                print(f"❌ Unknown command: {action}")
                print("Type 'help' for available commands")
            
            # Get output
            output = sys.stdout.getvalue()
            if output:
                self.output_ready.emit(output)
        
        except Exception as e:
            self.output_ready.emit(f"❌ Error: {e}")
        
        finally:
            sys.stdout = old_stdout


class KernelGUI(QMainWindow):
    """Main GUI Window - Simple Version"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize kernel CLI
        if KERNEL_AVAILABLE:
            self.cli = KernelAddCLI()
        else:
            self.cli = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI - SIMPLE LAYOUT"""
        
        # Window setup
        self.setWindowTitle("Kernel-Add GUI v1.0")
        self.setGeometry(100, 100, 1000, 700)  # Larger window
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout with padding
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)  # No margin for title
        main_layout.setSpacing(0)
        central_widget.setLayout(main_layout)
        
        # ===== TITLE =====
        title_label = QLabel("🐧 KERNEL-ADD CONTROL PANEL")
        title_font = QFont("Arial", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                       stop:0 #2c3e50, stop:1 #34495e);
            color: white;
            padding: 15px;
            border-bottom: 3px solid #3498db;
        """)
        main_layout.addWidget(title_label)
        
        # ===== CONTENT LAYOUT =====
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)  # Add padding
        content_layout.setSpacing(15)  # Space between left and right panels
        main_layout.addLayout(content_layout)
        
        # ===== LEFT PANEL - Buttons =====
        left_panel = QWidget()
        left_panel.setMaximumWidth(240)  # Slightly wider
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)  # Space between groups
        left_panel.setLayout(left_layout)
        
        # Package Manager Group
        pkg_group = QGroupBox("📦 Package Manager")
        pkg_group.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        pkg_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        pkg_layout = QVBoxLayout()
        
        self.create_button(pkg_layout, "Update Packages", self.cmd_update)
        self.create_button(pkg_layout, "List Installed", self.cmd_list)
        self.create_button(pkg_layout, "Search Packages", self.cmd_search)
        
        pkg_group.setLayout(pkg_layout)
        left_layout.addWidget(pkg_group)
        
        # Kernel Group
        kernel_group = QGroupBox("🐧 Kernel")
        kernel_group.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        kernel_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e74c3c;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        kernel_layout = QVBoxLayout()
        
        self.create_button(kernel_layout, "Kernel Status", self.cmd_kstatus)
        self.create_button(kernel_layout, "List Processes", self.cmd_ps)
        self.create_button(kernel_layout, "Memory Info", self.cmd_mem)
        
        kernel_group.setLayout(kernel_layout)
        left_layout.addWidget(kernel_group)
        
        # Drivers Group
        driver_group = QGroupBox("🔧 Drivers")
        driver_group.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        driver_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f39c12;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        driver_layout = QVBoxLayout()
        
        self.create_button(driver_layout, "List Drivers", self.cmd_lsmod)
        self.create_button(driver_layout, "List Devices", self.cmd_lsdev)
        
        driver_group.setLayout(driver_layout)
        left_layout.addWidget(driver_group)
        
        # Containers Group
        container_group = QGroupBox("🐳 Containers")
        container_group.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        container_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #9b59b6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        container_layout = QVBoxLayout()
        
        self.create_button(container_layout, "List Containers", self.cmd_cps)
        self.create_button(container_layout, "List Images", self.cmd_cimage)
        
        container_group.setLayout(container_layout)
        left_layout.addWidget(container_group)
        
        # System buttons
        clear_btn = QPushButton("🗑️  Clear Output")
        clear_btn.setMinimumHeight(40)
        clear_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
        clear_btn.clicked.connect(self.clear_output)
        left_layout.addWidget(clear_btn)
        
        left_layout.addStretch()
        
        content_layout.addWidget(left_panel)
        
        # ===== RIGHT PANEL - Output & Command =====
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        # Output label
        output_label = QLabel("📺 Output Console:")
        output_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        output_label.setStyleSheet("color: #2c3e50; padding: 5px;")
        right_layout.addWidget(output_label)
        
        # Output console
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 11))  # Larger font
        
        # Terminal style with better contrast
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #58d68d;
                border: 2px solid #34495e;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        
        right_layout.addWidget(self.output_text)
        
        # Command input
        cmd_layout = QHBoxLayout()
        
        cmd_label = QLabel("⌨️  Command:")
        cmd_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        cmd_label.setStyleSheet("color: #2c3e50;")
        cmd_layout.addWidget(cmd_label)
        
        self.command_input = QLineEdit()
        self.command_input.setFont(QFont("Consolas", 11))
        self.command_input.setPlaceholderText("Type command here...")
        self.command_input.setMinimumHeight(35)
        self.command_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #3498db;
                border-radius: 5px;
                padding: 5px 10px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 2px solid #2980b9;
            }
        """)
        self.command_input.returnPressed.connect(self.execute_command)
        cmd_layout.addWidget(self.command_input)
        
        exec_btn = QPushButton("▶️  Execute")
        exec_btn.setMinimumHeight(35)
        exec_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        exec_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        exec_btn.clicked.connect(self.execute_command)
        cmd_layout.addWidget(exec_btn)
        
        right_layout.addLayout(cmd_layout)
        
        content_layout.addWidget(right_panel)
        
        # ===== STATUS BAR =====
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #34495e;
                color: white;
                font-size: 11pt;
                font-weight: bold;
                padding: 5px;
            }
        """)
        if KERNEL_AVAILABLE:
            self.statusBar().showMessage("✅ Kernel loaded successfully - Ready to execute commands")
        else:
            self.statusBar().showMessage("❌ Kernel not available - Running in demo mode")
        
        # ===== WELCOME MESSAGE =====
        self.print_output("=" * 70)
        self.print_output("  KERNEL-ADD GUI v1.0 (PyQt6)")
        self.print_output("  Simple Interface for Kernel Management")
        self.print_output("=" * 70)
        self.print_output("")
        if KERNEL_AVAILABLE:
            self.print_output("✅ Kernel loaded successfully")
            self.print_output("💡 Click 'Update Packages' to fetch real packages from Alpine")
            self.print_output("💡 Or use buttons for quick commands")
        else:
            self.print_output("❌ Kernel not available - GUI demo mode")
        self.print_output("")
    
    def create_button(self, layout, text, callback):
        """Helper untuk create button dengan style bagus"""
        btn = QPushButton(text)
        btn.clicked.connect(callback)
        btn.setMinimumHeight(35)  # Tinggi button
        btn.setFont(QFont("Arial", 10))  # Font size
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        layout.addWidget(btn)
        return btn
    
    def print_output(self, text):
        """Print to output console"""
        self.output_text.append(text)
        self.output_text.ensureCursorVisible()
    
    def clear_output(self):
        """Clear output console"""
        self.output_text.clear()
        self.print_output("Output cleared.")
    
    def execute_command(self):
        """Execute custom command"""
        if not KERNEL_AVAILABLE:
            self.print_output("❌ Kernel not available")
            return
        
        command = self.command_input.text().strip()
        if not command:
            return
        
        self.command_input.clear()
        self.print_output(f"[localhost[@]MiniKernel]>-~& {command}")
        
        # Run command in thread
        self.run_command_thread(command)
    
    def run_command_thread(self, command):
        """Run command in background thread"""
        self.thread = CommandThread(self.cli, command)
        self.thread.output_ready.connect(self.handle_output)
        self.thread.finished.connect(lambda: self.print_output(""))
        self.thread.start()
    
    def handle_output(self, output):
        """Handle command output"""
        for line in output.split('\n'):
            if line:
                self.print_output(line)
    
    # ===== COMMAND HANDLERS =====
    
    def cmd_update(self):
        """Update packages"""
        if not KERNEL_AVAILABLE:
            return
        self.print_output("[Executing: update]")
        self.run_command_thread("update")
    
    def cmd_list(self):
        """List packages"""
        if not KERNEL_AVAILABLE:
            return
        self.print_output("[Executing: list]")
        self.run_command_thread("list")
    
    def cmd_search(self):
        """Search packages"""
        if not KERNEL_AVAILABLE:
            return
        
        query, ok = QInputDialog.getText(self, "Search Packages", "Enter search query:")
        if ok and query:
            self.print_output(f"[Executing: search {query}]")
            self.run_command_thread(f"search {query}")
    
    def cmd_kstatus(self):
        """Kernel status"""
        if not KERNEL_AVAILABLE:
            return
        self.print_output("[Executing: kstatus]")
        self.run_command_thread("kstatus")
    
    def cmd_ps(self):
        """List processes"""
        if not KERNEL_AVAILABLE:
            return
        self.print_output("[Executing: ps]")
        self.run_command_thread("ps")
    
    def cmd_mem(self):
        """Memory info"""
        if not KERNEL_AVAILABLE:
            return
        self.print_output("[Executing: mem]")
        self.run_command_thread("mem")
    
    def cmd_lsmod(self):
        """List drivers"""
        if not KERNEL_AVAILABLE:
            return
        self.print_output("[Executing: lsmod]")
        self.run_command_thread("lsmod")
    
    def cmd_lsdev(self):
        """List devices"""
        if not KERNEL_AVAILABLE:
            return
        self.print_output("[Executing: lsdev]")
        self.run_command_thread("lsdev")
    
    def cmd_cps(self):
        """List containers"""
        if not KERNEL_AVAILABLE:
            return
        self.print_output("[Executing: cps -a]")
        self.run_command_thread("cps -a")
    
    def cmd_cimage(self):
        """List images"""
        if not KERNEL_AVAILABLE:
            return
        self.print_output("[Executing: cimage ls]")
        self.run_command_thread("cimage ls")


# ===== MAIN =====

def main():
    """Main entry point"""
    
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show GUI
    gui = KernelGUI()
    gui.show()
    
    print("🖥️  PyQt6 GUI Started")
    print("💡 Close the window to exit")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
