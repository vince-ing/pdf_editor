import os
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
OUTPUT = ROOT / "repo_map.json"
SCAN_DIRS = ["engine", "frontend"]

# 1. EXPLICITLY IGNORE THESE FOLDERS
EXCLUDE_DIRS = {"node_modules", "venv", ".venv", "env", "__pycache__", ".git", "dist", "build", ".next"}

files_map = {}
dependencies = set()

def get_short_doc(node):
    """Grabs only the first line of a docstring to save space."""
    doc = ast.get_docstring(node)
    return doc.strip().split('\n')[0][:100] if doc else None

def get_signature(node):
    """Extracts function arguments compactly."""
    args = [arg.arg for arg in node.args.args]
    if node.args.vararg: args.append("*" + node.args.vararg.arg)
    if node.args.kwarg: args.append("**" + node.args.kwarg.arg)
    return "(" + ", ".join(args) + ")"

class RepoVisitor(ast.NodeVisitor):
    def __init__(self):
        self.classes = {}
        self.functions = []
        self.imports = set()
        self.current_class = None

    def visit_ClassDef(self, node):
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        base_str = f"({', '.join(bases)})" if bases else ""
        class_sig = f"class {node.name}{base_str}"
        
        self.current_class = class_sig
        self.classes[class_sig] = [] # List of method signatures
        
        self.generic_visit(node)
        self.current_class = None

    def _handle_func(self, node, is_async=False):
        if node.name.startswith("_") and node.name != "__init__": 
            return # Skip private methods
            
        prefix = "async def " if is_async else "def "
        sig = f"{prefix}{node.name}{get_signature(node)}"
        
        if self.current_class:
            self.classes[self.current_class].append(sig)
        else:
            self.functions.append(sig)

    def visit_FunctionDef(self, node):
        self._handle_func(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._handle_func(node, is_async=True)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name.startswith(tuple(SCAN_DIRS)): self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and node.module.startswith(tuple(SCAN_DIRS)): self.imports.add(node.module)
        self.generic_visit(node)

def analyze_python(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        src = f.read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None

    visitor = RepoVisitor()
    visitor.visit(tree)
    
    return visitor.classes, visitor.functions, list(visitor.imports)

def analyze_frontend(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        src = f.read()

    classes = {}
    functions = []

    for match in re.finditer(r'class\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_.]+))?', src):
        name, base = match.groups()
        class_sig = f"class {name}({base})" if base else f"class {name}"
        classes[class_sig] = []

    func_pattern = r'(?:function\s+([A-Za-z0-9_]+))|(?:(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_]+)\s*=>)'
    for match in re.finditer(func_pattern, src):
        name = match.group(1) or match.group(2)
        if name: functions.append(f"function {name}()")

    return classes, functions, []

def scan():
    for root_dir in SCAN_DIRS:
        start = ROOT / root_dir
        if not start.exists(): continue

        for root, dirs, filenames in os.walk(start):
            # 2. MODIFY DIRS IN-PLACE TO SKIP JUNK FOLDERS
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for f in filenames:
                path = Path(root) / f
                rel_path = path.relative_to(ROOT).as_posix()
                
                if f.endswith(".py"):
                    result = analyze_python(path)
                elif f.endswith((".js", ".jsx", ".ts", ".tsx")):
                    result = analyze_frontend(path)
                else:
                    continue

                if not result: continue
                classes, functions, imports = result

                # 3. ONLY ADD KEYS IF THEY ARE NOT EMPTY
                if classes or functions:
                    entry = {}
                    if classes: entry["classes"] = classes
                    if functions: entry["functions"] = functions
                    files_map[rel_path] = entry

                for imp in imports:
                    target_file = imp.replace(".", "/") + ".py"
                    dependencies.add((rel_path, target_file))

def write():
    data = {
        "files": files_map,
        "dependencies": [{"source": src, "target": tgt} for src, tgt in dependencies]
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        # indent=2 keeps it readable, but the flattened structure prevents bloat
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    scan()
    write()