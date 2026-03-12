import os
import ast
import sys

stdlib = sys.stdlib_module_names if hasattr(sys, 'stdlib_module_names') else set()

def get_imports(directory):
    imports = set()
    for root, dirs, files in os.walk(directory):
        if 'venv' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read(), filename=path)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    imports.add(alias.name.split('.')[0])
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    imports.add(node.module.split('.')[0])
                except Exception as e:
                    print(f"Error parsing {path}: {e}")
    return imports

third_party = {imp for imp in get_imports('.') if imp not in stdlib and imp not in ('agents', 'agents_endpoint', '', 'main')}

print("Third-party imports found:")
for imp in sorted(third_party):
    print(imp)

try:
    with open('requirements.txt', 'r') as f:
        reqs = {line.split('[')[0].split('=')[0].split('>')[0].split('<')[0].strip().lower() for line in f if line.strip() and not line.startswith('#')}
except FileNotFoundError:
    reqs = set()

# Map common import names to package names if needed
# e.g., dotenv -> python-dotenv
pkg_map = {
    'dotenv': 'python-dotenv'
}
normalized_imports = {pkg_map.get(imp, imp) for imp in third_party}

missing = normalized_imports - reqs
print("\nMissing from requirements.txt:")
for m in sorted(missing):
    print(m)
