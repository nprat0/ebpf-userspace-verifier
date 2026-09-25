#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

KERNEL_VERSION="v6.8"
KERNEL_REPO="https://github.com/torvalds/linux.git"

echo "🚀 Initializing eBPF Userspace Verifier project..."

# 1. Create untracked/generated directories
echo "📁 Creating build and output directories..."
mkdir -p build
mkdir -p analyzer/output

# 2. Shallow clone the Linux Kernel
if [ ! -d "linux" ]; then
    echo "🐧 Downloading Linux Kernel ($KERNEL_VERSION)..."
    # --depth 1 fetches only the specified commit, saving disk space and time
    git clone --depth 1 -b $KERNEL_VERSION $KERNEL_REPO linux
else
    echo "✅ Directory 'linux' already exists, skipping download."
fi

# 3. Setup Python virtual environment
if [ ! -d "analyzer/venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv analyzer/venv
    
    echo "📦 Installing Python dependencies..."
    analyzer/venv/bin/pip install -r analyzer/requirements.txt
fi

# 4. Kernel configuration and preparation
echo "⚙️  Configuring the kernel for eBPF extraction..."
cd linux

# Generate the base default configuration
make defconfig

# Explicitly enable all required BPF and BTF features
./scripts/config --enable CONFIG_BPF
./scripts/config --enable CONFIG_BPF_SYSCALL
./scripts/config --enable CONFIG_BPF_JIT
./scripts/config --enable CONFIG_DEBUG_INFO_BTF
./scripts/config --enable CONFIG_CGROUP_BPF
./scripts/config --enable CONFIG_NET

# Resolve Debug Info dependencies to ensure BTF generation succeeds
./scripts/config --disable CONFIG_DEBUG_INFO_NONE
./scripts/config --enable CONFIG_DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT
./scripts/config --enable CONFIG_DEBUG_INFO_BTF

# Resolve dependencies and apply the new configuration
make olddefconfig

# Generate autoconf.h and required kernel headers
echo "🔨 Preparing kernel headers..."
make prepare

cd ..

echo "🎉 Setup completed successfully!"
echo "👉 Next step: run 'make kernel_verifier' to generate compilation flags."
