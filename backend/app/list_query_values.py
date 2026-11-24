"""Per-row JSON extraction shared by filters; no persisted state."""
from sqlalchemy import column, Text, func, true, case
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause
from sqlalchemy.sql.selectable import ScalarSelect, Exists
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.ext.compiler import compiles
from .models import Report

class RawValues(FunctionElement):
    inherit_cache = False
    def __init__(self, source, paths):
        self.paths = paths
        super().__init__(source)

@compiles(RawValues,'mysql')
@compiles(RawValues,'mariadb')
def compile_raw(element, compiler, **kw):
    source=compiler.process(list(element.clauses)[0],**kw)
    columns=', '.join('v'+str(i)+' JSON PATH '+compiler.render_literal_value(path,Text())+' NULL ON EMPTY, e'+str(i)+' INT EXISTS PATH '+compiler.render_literal_value(path,Text()) for i,path in enumerate(element.paths))
    return "JSON_TABLE("+source+", '$' COLUMNS ("+columns+"))"

def materialize_fields(query, fields, *, model=Report, json_column=None):
    from .list_paging import JsonText, JsonType, SummaryValue, DisplayText, DateText
    from .list_projection import _source
    fields={k:v.__clause_element__() if hasattr(v,'__clause_element__') else v for k,v in fields.items()}
    json_column = model.detail if json_column is None else json_column
    paths=[]
    def raw_path(node):
        if not isinstance(node,(JsonText,JsonType,SummaryValue)):return None
        args=list(node.clauses)
        cols=[n for n in visitors.iterate(args[0]) if isinstance(n,ColumnClause) and getattr(n,'table',None) is not None]
        if not cols or any(n.table.name!=model.__tablename__ or n.name!=json_column.key for n in cols):return None
        return '$.summary' if isinstance(node,SummaryValue) else args[1].value
    def gather(node):
        if isinstance(node,(ScalarSelect,Exists)):return node
        path=raw_path(node)
        if path:
            if path not in paths:paths.append(path)
            return node
        return None
    for expr in fields.values():visitors.replacement_traverse(expr,{},gather)
    raw=RawValues(_source(json_column),paths).table_valued(*[column(prefix+str(i),Text()) for i in range(len(paths)) for prefix in ('v','e')],joins_implicitly=True).alias('list_raw_json')
    query=query.join(raw,true())
    def extracted(node):
        if isinstance(node,(ScalarSelect,Exists)):return node
        path=raw_path(node)
        if path:
            value=raw.c['v'+str(paths.index(path))]
            if isinstance(node,JsonType):return case((raw.c['e'+str(paths.index(path))]==0,None),else_=func.coalesce(func.lower(func.json_type(value)),'null'))
            if isinstance(node,SummaryValue):return SummaryValue(func.json_object('summary',value),*list(node.clauses)[1:])
            return func.nullif(func.json_unquote(value),'null')
        return None
    current={k:visitors.replacement_traverse(v,{},extracted) for k,v in fields.items()}

    def layer(query, expressions, capture_key, alias):
        nodes = {}
        identities = {}
        def capture(node):
            key = capture_key(node)
            if key is not None:
                nodes.setdefault(key, node)
                identities[id(node)] = key
                return node
            return None
        for expr in expressions.values():
            visitors.replacement_traverse(expr, {}, capture)
        names = {key:'v'+str(i) for i,key in enumerate(nodes)}
        relation = query.with_entities(model.id.label('_report_id'), *[
            node.label(names[key]) for key,node in nodes.items()
        ]).order_by(None).limit(18446744073709551615).subquery(alias)
        def replace(node):
            key = identities.get(id(node))
            return relation.c[names[key]] if key is not None else None
        return model.query.join(relation,relation.c._report_id==model.id), {
            key:visitors.replacement_traverse(expr,{},replace) for key,expr in expressions.items()}

    def leaves(node):
        if isinstance(node,SummaryValue):
            return ('summary',tuple(n.value for n in list(node.clauses)[1:]))
        if isinstance(node,ColumnClause):
            return ('column',id(getattr(node,'table',None)),node.name)
        if isinstance(node,(DisplayText,ScalarSelect,Exists)):
            return ('expression',id(node))
        return None
    query,current=layer(query,current,leaves,'list_raw_values')
    inputs={id(list(n.clauses)[0]) for expr in current.values()
            for n in visitors.iterate(expr) if isinstance(n,DateText)}
    def dates(node):
        if id(node) in inputs:return ('date_input',id(node))
        if isinstance(node,ColumnClause):return ('column',id(getattr(node,'table',None)),node.name)
        return None
    return layer(query,current,dates,'list_date_values')
