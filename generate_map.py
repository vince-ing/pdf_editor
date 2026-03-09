import os
import ast
import json
import re
from pathlib import Path

EXCLUDE_DIRS = {
    "__pycache__", "generate_map.py", ".git", "venv", "models",
    "node_modules", "pytesseract", "generate_tree.py", ".gitignore",
    "output", "testfiles", "speechtest.py", "structure.txt", "fonts",
    "build_tools", "build", "dist", "installer.iss", "installer_output",
    "tests", ".workspace",
}
EXCLUDE_SUFFIXES = {".pyc"}
OUTPUT_FILE = "repo_map.json"


# ── Python analysis ───────────────────────────────────────────────────────────

def analyze_python(path: Path) -> dict:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    classes = {}
    functions = []
    api_routes = []

    for node in ast.walk(tree):
        # FastAPI route decorators → extract method + path
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                route = _extract_route(dec)
                if route:
                    params = _py_func_params(node)
                    api_routes.append({
                        "method": route["method"],
                        "path": route["path"],
                        "handler": node.name,
                        "params": params,
                    })

        # Top-level classes with their methods + signatures
        if isinstance(node, ast.ClassDef):
            # Check if it's a Pydantic BaseModel — extract fields instead of methods
            bases = [ast.unparse(b) for b in node.bases]
            is_model = any("BaseModel" in b for b in bases)

            if is_model:
                fields = []
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        field = item.target.id
                        annotation = ast.unparse(item.annotation)
                        default = f" = {ast.unparse(item.value)}" if item.value else ""
                        fields.append(f"{field}: {annotation}{default}")
                classes[f"class {node.name}"] = fields
            else:
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Skip private/internal methods (underscore-prefixed), except __init__
                        if item.name.startswith("_") and item.name != "__init__":
                            continue
                        methods.append({
                            "name": item.name,
                            "params": _py_func_params(item),
                        })
                classes[f"class {node.name}"] = methods

        # Top-level functions
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if _is_top_level(tree, node):
                functions.append({
                    "name": node.name,
                    "params": _py_func_params(node),
                })

    result = {}
    if classes:
        result["classes"] = classes
    if functions:
        result["functions"] = functions
    if api_routes:
        result["api_routes"] = api_routes
    return result


def _extract_route(dec):
    """Extract HTTP method and path from a FastAPI decorator."""
    HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
    if isinstance(dec, ast.Call):
        func = dec.func
        method = None
        if isinstance(func, ast.Attribute) and func.attr in HTTP_METHODS:
            method = func.attr.upper()
        elif isinstance(func, ast.Name) and func.id in HTTP_METHODS:
            method = func.id.upper()
        if method and dec.args:
            path_node = dec.args[0]
            if isinstance(path_node, ast.Constant):
                return {"method": method, "path": path_node.value}
    return None


def _py_func_params(node) -> list[str]:
    """Return a list of 'param: type = default' strings, skipping 'self'."""
    args = node.args
    params = []
    all_args = args.args + getattr(args, "posonlyargs", [])
    defaults_offset = len(all_args) - len(args.defaults)

    for i, arg in enumerate(all_args):
        if arg.arg == "self":
            continue
        annotation = ast.unparse(arg.annotation) if arg.annotation else None
        default_idx = i - defaults_offset
        default = ast.unparse(args.defaults[default_idx]) if default_idx >= 0 else None
        parts = arg.arg
        if annotation:
            parts += f": {annotation}"
        if default:
            parts += f" = {default}"
        params.append(parts)
    return params


def _is_top_level(tree, target):
    for node in ast.iter_child_nodes(tree):
        if node is target:
            return True
    return False


# ── TypeScript / JavaScript analysis ─────────────────────────────────────────

def analyze_typescript(path: Path) -> dict:
    try:
        src = path.read_text(encoding="utf-8")
    except Exception:
        return {}

    functions = []
    interfaces = {}
    api_calls = []

    # Named exports and regular functions with their params
    func_pattern = re.compile(
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
        re.MULTILINE
    )
    for m in func_pattern.finditer(src):
        params = _ts_parse_params(m.group(2))
        functions.append({"name": m.group(1), "params": params})

    # Arrow function exports: export const foo = (...) =>
    arrow_pattern = re.compile(
        r'export\s+const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*[\w<>\[\], |]+)?\s*=>',
        re.MULTILINE
    )
    for m in arrow_pattern.finditer(src):
        params = _ts_parse_params(m.group(2))
        functions.append({"name": m.group(1), "params": params})

    # Interfaces / types — capture their fields
    iface_pattern = re.compile(
        r'(?:export\s+)?interface\s+(\w+)[^{]*\{([^}]*)\}',
        re.MULTILINE | re.DOTALL
    )
    for m in iface_pattern.finditer(src):
        fields = []
        for line in m.group(2).splitlines():
            line = line.strip().rstrip(";").rstrip(",")
            if line and not line.startswith("//"):
                fields.append(line)
        if fields:
            interfaces[m.group(1)] = fields

    # For client.ts: extract named API methods with their signature + axios payload
    # Match:  methodName: async (params) => { ... axios.METHOD(`url`, payload ...) }
    # We find each top-level key in the engineApi object
    is_api_client = "engineApi" in src or "axios" in src
    if is_api_client:
        # Find each property: `  name: async (...) =>` style entries
        method_pattern = re.compile(
            r'^\s{2}(\w+):\s*async\s*\(([^)]*)\)',
            re.MULTILINE
        )
        for mm in method_pattern.finditer(src):
            fn_name = mm.group(1)
            fn_params = [p.strip() for p in mm.group(2).split(",") if p.strip()]

            # Find the axios call within ~400 chars after this method starts
            chunk = src[mm.start(): mm.start() + 600]
            axios_m = re.search(
                r'axios\.(get|post|put|patch|delete)\s*\(\s*`([^`]+)`(.*?)(?:\),|\)\s*\))',
                chunk, re.DOTALL
            )
            if axios_m:
                method = axios_m.group(1).upper()
                url = axios_m.group(2)
                # Extract payload: the second argument to axios (skip session header arg)
                args_text = axios_m.group(3)
                # Find first { } block that looks like a payload
                payload = _extract_first_object(args_text)
                api_calls.append({
                    "fn": fn_name,
                    "signature": f"{fn_name}({', '.join(fn_params)})",
                    "method": method,
                    "url": url,
                    "payload": payload,
                })

    result = {}
    if interfaces:
        result["interfaces"] = interfaces
    if api_calls:
        result["api_calls"] = api_calls
    elif functions:
        # Only show generic functions for non-client files
        result["functions"] = [f["name"] + ("(" + ", ".join(f["params"]) + ")" if f["params"] else "()") for f in functions]
    if not api_calls and functions:
        result["functions"] = [f["name"] + ("(" + ", ".join(f["params"]) + ")" if f["params"] else "()") for f in functions]

    # For hooks/state files: extract the keys of the final return { ... } object
    # This shows what a hook exposes without reading the whole file
    if path.name.startswith("use") or "State" in path.name:
        return_keys = _extract_return_keys(src)
        if return_keys:
            result["returns"] = return_keys

    return result


def _extract_return_keys(src: str) -> list[str] | None:
    """Find the last top-level `return { ... }` and extract its keys."""
    # Find all `return {` blocks
    pattern = re.compile(r'\breturn\s*\(\s*\{|\breturn\s*\{', re.MULTILINE)
    matches = list(pattern.finditer(src))
    if not matches:
        return None

    # Use the last one (the main return statement of the hook)
    m = matches[-1]
    start = src.index("{", m.start())
    obj = _extract_first_object(src[start:])
    if not obj:
        return None

    # Extract just the keys (left side of each `key: value` or bare `key,`)
    keys = []
    for line in obj.split(","):
        line = line.strip().lstrip("{").rstrip("}")
        # Match `key:` or bare `key`
        key_match = re.match(r'^(\w+)\s*(?::|$)', line.strip())
        if key_match:
            keys.append(key_match.group(1))
    return keys if keys else None


def _extract_first_object(text: str) -> str | None:
    """Extract the first {...} block from text, handling nesting."""
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                raw = text[start:i+1].strip()
                # Collapse whitespace for readability
                raw = re.sub(r'\s+', ' ', raw)
                return raw
    return None


def _ts_parse_params(raw: str) -> list[str]:
    """Split a TS param string into individual param names (with types)."""
    params = []
    depth = 0
    current = ""
    for ch in raw:
        if ch in "({[<":
            depth += 1
            current += ch
        elif ch in ")}]>":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            p = current.strip()
            if p:
                params.append(p)
            current = ""
        else:
            current += ch
    if current.strip():
        params.append(current.strip())
    return params


# ── File walker ───────────────────────────────────────────────────────────────

ANALYZABLE = {".py", ".ts", ".tsx"}

def build_map(start_path=".") -> dict:
    start = Path(start_path).resolve()
    files = {}

    for root, dirs, filenames in os.walk(start):
        # Prune excluded dirs in-place
        dirs[:] = [
            d for d in sorted(dirs)
            if d not in EXCLUDE_DIRS and not d.startswith(".")
        ]
        for fname in sorted(filenames):
            p = Path(root) / fname
            if p.name in EXCLUDE_DIRS or p.suffix in EXCLUDE_SUFFIXES:
                continue
            rel = str(p.relative_to(start))

            if p.suffix == ".py":
                info = analyze_python(p)
            elif p.suffix in {".ts", ".tsx"}:
                info = analyze_typescript(p)
            else:
                info = {}

            if info:
                files[rel] = info

    return {"files": files}


if __name__ == "__main__":
    data = build_map()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {OUTPUT_FILE} ({len(data['files'])} files)")