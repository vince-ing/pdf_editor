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
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
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

    # API calls: axios.get/post/patch/delete with their URL and payload shape
    axios_pattern = re.compile(
        r'axios\.(get|post|put|patch|delete)\s*\(\s*`([^`]+)`',
        re.MULTILINE
    )
    for m in axios_pattern.finditer(src):
        # Try to grab the payload object on the same line
        after = src[m.end():m.end() + 200]
        payload_match = re.search(r',\s*(\{[^}]+\})', after)
        payload = payload_match.group(1).strip() if payload_match else None
        api_calls.append({
            "method": m.group(1).upper(),
            "url": m.group(2),
            "payload": payload,
        })

    result = {}
    if interfaces:
        result["interfaces"] = interfaces
    if functions:
        result["functions"] = [f["name"] + ("(" + ", ".join(f["params"]) + ")" if f["params"] else "()") for f in functions]
    if api_calls:
        result["api_calls"] = api_calls
    return result


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