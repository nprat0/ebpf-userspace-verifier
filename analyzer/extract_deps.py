import clang.cindex
from clang.cindex import CursorKind
import os
import sys

# Define absolute paths based on the script's location
ANALYZER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(ANALYZER_DIR, '..'))
KERNEL_DIR = os.path.join(PROJECT_ROOT, 'linux')
VERIFIER_C = os.path.join(KERNEL_DIR, 'kernel', 'bpf', 'verifier.c')

def get_compile_args(compdb_path, file_path):
    """Extracts ONLY the preprocessor and semantic arguments from the database."""
    if not os.path.exists(compdb_path):
        print(f"Error: Compilation database not found at {compdb_path}")
        sys.exit(1)

    compdb = clang.cindex.CompilationDatabase.fromDirectory(KERNEL_DIR)
    commands = compdb.getCompileCommands(file_path)
    
    if not commands:
        print(f"Error: No compile commands found for {file_path}")
        sys.exit(1)

    raw_args = list(commands[0].arguments)[1:]
    clean_args = []
    skip_next = False

    for i, arg in enumerate(raw_args):
        if skip_next:
            skip_next = False
            continue
            
        # Ignore output and input file assignments inside the arguments list
        # (libclang.parse() handles the input file automatically)
        if arg == '-o':
            skip_next = True
            continue
        if arg == '-c' or arg.endswith('.c') or arg.endswith('.o'):
            continue

        # ALLOWLIST: Keep includes, defines, and system includes
        if arg.startswith('-I') or arg.startswith('-D') or arg.startswith('-U') or arg.startswith('-include'):
            clean_args.append(arg)
            continue
        if arg in ['-I', '-D', '-U', '-include', '-isystem']:
            clean_args.append(arg)
            if i + 1 < len(raw_args):
                clean_args.append(raw_args[i+1])
                skip_next = True
            continue
            
        # ALLOWLIST: Keep language standard and core environment flags
        if arg.startswith('-std=') or arg == '-nostdinc':
            clean_args.append(arg)
            continue
            
        # ALLOWLIST: Keep target architecture
        if arg in ['-m64', '-m32'] or arg.startswith('--target='):
            clean_args.append(arg)
            continue

    # Tell libclang we are parsing C code
    clean_args.append('-x')
    clean_args.append('c')

    return clean_args

def find_external_dependencies(cursor, target_file):
    """Iteratively traverses the AST to find external functions, types, and macros."""
    external_funcs = set()
    external_types = set()
    external_macros = set()
    
    stack = [cursor]
    target_abs = os.path.abspath(target_file)

    while stack:
        node = stack.pop()
        
        # 1. EXTRACT FUNCTIONS
        if node.kind == CursorKind.CALL_EXPR:
            ref = node.referenced
            if ref and ref.kind == CursorKind.FUNCTION_DECL:
                loc = ref.location.file
                if loc:
                    if os.path.abspath(loc.name) != target_abs:
                        if ref.spelling:
                            external_funcs.add(ref.spelling)
                else:
                    if ref.spelling:
                        external_funcs.add(ref.spelling)
            elif not ref:
                for child in node.get_children():
                    if child.kind == CursorKind.DECL_REF_EXPR and child.spelling:
                        external_funcs.add(child.spelling)
                        break

        # 2. EXTRACT TYPES (Structs, Unions, Enums, Typedefs)
        elif node.kind == CursorKind.TYPE_REF:
            ref = node.referenced
            if ref:
                loc = ref.location.file
                if loc and os.path.abspath(loc.name) != target_abs:
                    if ref.spelling and not ref.spelling.startswith("anonymous "):
                        prefix = ""
                        if ref.kind == CursorKind.STRUCT_DECL and not ref.spelling.startswith("struct "):
                            prefix = "struct "
                        elif ref.kind == CursorKind.UNION_DECL and not ref.spelling.startswith("union "):
                            prefix = "union "
                        elif ref.kind == CursorKind.ENUM_DECL and not ref.spelling.startswith("enum "):
                            prefix = "enum "
                        external_types.add(prefix + ref.spelling)

        # 3. EXTRACT MACROS
        elif node.kind == CursorKind.MACRO_INSTANTIATION:
            # Check if this macro is used (instantiated) inside our target file
            inst_loc = node.location.file
            if inst_loc and os.path.abspath(inst_loc.name) == target_abs:
                ref = node.referenced
                if ref:
                    # Where was the macro actually defined?
                    def_loc = ref.location.file
                    if def_loc:
                        # If defined in a different header file, it's external
                        if os.path.abspath(def_loc.name) != target_abs:
                            external_macros.add(node.spelling)
                    else:
                        # Defined via compiler command line (-D) or built-in compiler macro
                        external_macros.add(node.spelling)

        stack.extend(node.get_children())

    return external_funcs, external_types, external_macros

def main():
    print("🔍 Initializing libclang analyzer...")
    try:
        index = clang.cindex.Index.create()
    except Exception as e:
        print("Error initializing libclang.")
        sys.exit(1)

    print(f"📥 Loading compile flags for verifier.c...")
    args = get_compile_args(KERNEL_DIR, VERIFIER_C)

    print(f"🧠 Parsing AST (this will take 10-30 seconds)...")
    options = clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
    os.chdir(KERNEL_DIR)
    
    try:
        tu = index.parse(VERIFIER_C, args=args, options=options)
    except clang.cindex.TranslationUnitLoadError:
        print("\n❌ FATAL: libclang crashed while parsing.")
        sys.exit(1)

    print("🌲 Traversing AST to extract dependencies (Functions, Types, Macros)...")
    funcs, types, macros = find_external_dependencies(tu.cursor, VERIFIER_C)

    # Change back to project root to save the files
    os.chdir(PROJECT_ROOT)
    
    funcs_file = os.path.join(ANALYZER_DIR, 'output', 'missing_functions.txt')
    with open(funcs_file, 'w') as f:
        for func in sorted(funcs):
            f.write(f"{func}\n")
            
    types_file = os.path.join(ANALYZER_DIR, 'output', 'missing_types.txt')
    with open(types_file, 'w') as f:
        for t in sorted(types):
            f.write(f"{t}\n")

    macros_file = os.path.join(ANALYZER_DIR, 'output', 'missing_macros.txt')
    with open(macros_file, 'w') as f:
        for m in sorted(macros):
            f.write(f"{m}\n")
            
    print(f"\n✅ Extraction complete!")
    print(f"  - 🔧 Found {len(funcs)} external functions -> {funcs_file}")
    print(f"  - 📦 Found {len(types)} external data types -> {types_file}")
    print(f"  - 🏷️ Found {len(macros)} external macros -> {macros_file}")

if __name__ == "__main__":
    main()
