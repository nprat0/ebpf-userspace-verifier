# eBPF Userspace Verifier

The eBPF Userspace Verifier is an automated porting framework designed to decouple the Linux kernel's eBPF verifier (`kernel/bpf/verifier.c`) from kernelspace and execute it natively as a userspace application.

## Project Scope
The in-kernel eBPF verifier is constrained by strict resource limits, including bounded stack sizes and maximum execution time thresholds designed to prevent system lockups. These structural constraints make it impossible to introduce computationally heavy, high-precision analysis techniques such as model checking, deep inter-procedural static analysis, or advanced symbolic execution.

This project overcomes these limitations by extracting and compiling the original kernel verifier in a 1:1 ratio, explicitly avoiding any forks or manual modifications to the upstream Linux source code. Executing in userspace lifts memory and time restrictions, enabling deeper program analysis while allowing the use of standard userspace tooling (GDB, Valgrind, AFL/libFuzzer) to debug and fuzz the verifier itself.

## Environment & Prerequisites
This project is designed for **Ubuntu 24.04 (WSL2 or Native)**. Before initializing the project, ensure your host environment has the required compiler toolchains and BTF (BPF Type Format) utilities installed.

```bash
sudo apt update
sudo apt install -y build-essential clang lld llvm \
                    python3-venv python3-dev \
                    dwarves libelf-dev zlib1g-dev
```
* **`clang` / `lld` / `llvm`**: The primary C compiler and linker toolchain used to extract AST dependencies and build the userspace binary.
* **`dwarves`**: Provides `pahole`, required by the kernel to generate BTF type information.
* **`libelf-dev` / `zlib1g-dev`**: Required C libraries to natively compile the local `bpftool` binary from the kernel source tree.

## Architecture
To ensure the extraction is resilient to upstream kernel updates, the project avoids manual dependency tracking in favor of a compiler-driven automated pipeline:

* **`analyzer/`**: A Python-based static analysis engine leveraging `libclang`. It intercepts the exact Clang compiler flags used by the Linux kernel build system, generates an Abstract Syntax Tree (AST) of the verifier, and exhaustively maps every external function, data structure, and macro required for compilation.
* **`shim/`**: The userspace abstraction layer. It provides the dynamically generated mock headers and C stubs necessary to satisfy the verifier's dependencies, translating kernel primitives (e.g., `kmalloc`, `RCU` locks) into their userspace equivalents (e.g., `malloc`, `pthreads`).
* **`src/`**: The userspace entry point (`main.c`) that wraps the verifier, initializes the mock kernel environment, loads eBPF programs, and triggers the `bpf_check()` routine.

## Getting Started

The build system handles downloading the target kernel (v6.8 baseline), configuring the Kbuild environment, and orchestrating the AST extraction.

1. **Initialize the Environment**
   ```bash
   ./setup.sh
   ```
   *Downloads the kernel, generates the `defconfig`, enables all required BPF/BTF Kconfig flags, and sets up the Python virtual environment.*

2. **Generate the Compilation Database**
   ```bash
   make compdb
   ```
   *Compiles `verifier.o` using Clang to extract the exact preprocessor directives, macros, and include paths used by the kernel.*

3. **Extract Dependencies**
   ```bash
   make analyze
   ```
   *Parses the AST and outputs the definitive lists of missing functions, types, and macros into the `analyzer/output/` directory.*
