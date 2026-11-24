"""Read-only inventory of supplier public combinations; no vendor import side effects."""
import ast
from .document_module import VENDOR, verify_vendor


def template_catalog():
    verify_vendor()
    tree = ast.parse((VENDOR / 'report_demo.py').read_text(encoding='utf-8-sig'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ReportConfig')
    assignment = next(node for node in cls.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'report_context' for t in node.targets))
    config = ast.literal_eval(assignment.value)
    reports, entrusts = [], []
    for path in sorted((VENDOR / 'assets/templates').glob('LAB-*.docx')):
        parts = path.name.split('-')
        if parts[1] == 'Report':
            _, _, kind, language, variant, _ = parts
            reports.append(dict(kind=kind.lower(), language=language, variant=variant, filename=path.name,
                centers=[center for center, data in config.items() if kind in data['category']]))
        elif parts[1] == 'Entrust':
            _, _, code, variant, _ = parts
            kind = 'product' if code == '4204d' else 'engineering'
            entrusts.append(dict(kind=kind, variant=variant, filename=path.name,
                templateKind=kind + ('-extended' if variant == 'Extended' else '')))
    return dict(reports=reports, entrusts=entrusts)
