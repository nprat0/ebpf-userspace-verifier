# Base directories
KERNEL_DIR = linux
ANALYZER_DIR = analyzer
SHIM_DIR = shim
SRC_DIR = src
BUILD_DIR = build

# Files
VMLINUX = $(KERNEL_DIR)/vmlinux
VMLINUX_H = $(BUILD_DIR)/vmlinux.h
BPFTOOL = $(KERNEL_DIR)/tools/bpf/bpftool/bpftool

# Python commands (using the virtual environment)
PYTHON = $(ANALYZER_DIR)/venv/bin/python

# Compiler variables for the final userspace target
CC = clang
# -I$(SHIM_DIR)/include instructs the compiler to search our mock headers FIRST
CFLAGS = -Wall -g -I$(SHIM_DIR)/include

.PHONY: all kernel_verifier compdb analyze types userspace clean clean-kernel

# Default target
all: userspace

# 1. Compile the verifier within the kernel to generate .cmd files
kernel_verifier:
	@echo "==> Compiling kernel/bpf/verifier.o..."
	$(MAKE) -C $(KERNEL_DIR) CC=clang LLVM=1 kernel/bpf/verifier.o

# 2. Use the kernel script to generate compile_commands.json
compdb: kernel_verifier
	@echo "==> Generating Compilation Database..."
	cd $(KERNEL_DIR) && ./scripts/clang-tools/gen_compile_commands.py
	@echo "==> Database generated at $(KERNEL_DIR)/compile_commands.json"

# 3. Execute the Python static analysis tool (to be implemented)
analyze: compdb
	@echo "==> Running libclang static analyzer..."
	$(PYTHON) $(ANALYZER_DIR)/extract_deps.py

# 4. Extract the BTF types into the C header
$(VMLINUX):
	@echo "==> Compiling vmlinux to generate BTF data (this will take several minutes)..."
	$(MAKE) -C $(KERNEL_DIR) CC=clang -j$$(nproc) vmlinux

$(BPFTOOL):
	@echo "==> Building local bpftool..."
	$(MAKE) -C $(KERNEL_DIR)/tools/bpf/bpftool

types: $(VMLINUX) $(BPFTOOL)
	@echo "==> Extracting BTF types to $(VMLINUX_H)"
	$(BPFTOOL) btf dump file $(VMLINUX) format c > $(VMLINUX_H)

# 5. Compile the final userspace project (stubs + main)
userspace:
	@echo "==> Compiling the userspace target..."
	# This command will include main.c, the stubs in shim/src, and verifier.c
	# $(CC) $(CFLAGS) $(SRC_DIR)/main.c $(SHIM_DIR)/src/*.c $(KERNEL_DIR)/kernel/bpf/verifier.c -o $(BUILD_DIR)/ebpf_verifier
	@echo "Userspace compilation is commented out until the shim layer is ready."

# Clean generated userspace files
clean:
	@echo "==> Cleaning userspace build artifacts..."
	rm -rf $(BUILD_DIR)/*

# Clean the kernel tree
clean-kernel:
	@echo "==> Cleaning kernel build artifacts..."
	$(MAKE) -C $(KERNEL_DIR) clean
