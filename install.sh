#!/bin/bash
# install.sh - Helper script untuk install dependencies

echo "╔════════════════════════════════════════╗"
echo "║  Kernel-Add Installation Helper        ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check Python version
echo "🔍 Checking Python version..."
python3 --version

if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found!"
    echo "💡 Please install Python 3.8 or higher"
    exit 1
fi

echo ""
echo "📦 Installing PyQt6..."
pip3 install PyQt6

if [ $? -eq 0 ]; then
    echo "✅ PyQt6 installed successfully!"
else
    echo "⚠️  PyQt6 installation may have issues"
    echo "💡 Try: pip3 install --user PyQt6"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "🚀 Quick Start:"
echo "   Terminal mode: python3 LinuxKernel.py"
echo "   GUI mode:      python3 gui.py"
echo ""