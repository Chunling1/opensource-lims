"""Database-side list projections. Full forms remain on explicit detail reads.

Projected objects are transient: they must never replace an identity-map object
or be used for writes. No cross-request cache and no change to data authorization.
"""
import json
from sqlalchemy import Text, and_, case, cast, func
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

from .extensions import db
from .models import Agreement, Entrust, Report


def leaves(text):
    return dict.fromkeys(text.split())


ENTRUST_INFO = leaves('''erpContractNo erpProjectNo projectCode projectRecordNo
    projectTradeCode erpType erpProjectType projectType contractPartyA otherPartyA
    entrustDate handler handleDept handleDepartment handlerDepartment consignor
    consignorPhone clientAddr clientAddress remark note sampleRegistrar sampleRegistrarDepartment''')
AGREEMENT_INFO = leaves('''regTime regDate auditTime projectAuditTime bizDept projectOwner
    registrar testDept remark note fromErp contractStartDate erpLogReceivedAt
    sourceEventId sourceUpdatedAt sourceFieldSummary projectAddr erpSourceKey''')
SNAPSHOT = {**leaves('''sourceEntrustId sourceEntrustNo entrustNo contractNo client projectName
    projectType amount department owner'''), 'info': ENTRUST_INFO}
RAW = leaves('''projectList projects project sampleName seal centerPrefix schemeName testPlan schemeCode
    baseReportNo testDept registrar registrarDepartment stdPrice reportCategory reportFormat reportType testCategory
    registeredAt sampleArrivalDate sendDate sampleUnit sampler sampleTime sampleHandle spec manufacturer
    produceDate sampleAmount factoryNo appearance testLocation testBasis standardJudge payWay
    samplingLocation testBases standardItemIds capabilityEntryIds manualCapabilityItems
    actualTestLocations isOnsiteTesting onsiteTestLocation entrustDate requiredTestDate testDueDate deliverWay''')
CHECK = leaves('''standard standards testStartDate testDate result resultStatus conclusion seal entryStaff people''')
DETAIL = {**leaves('''summary dataEntryStarted sampleRegisteredAt sampleRegistrar sampleRegistrarDepartment
    derivedFrom centerPrefix reportCategory returnInfo internalCorrectionRevision workflowDates complianceResolution reportDelivery
    sampleConfiguration'''), 'rawSample': RAW, 'checkInput': CHECK, 'entrustSnapshot': SNAPSHOT,
    'contractReview': leaves('reviewer reviewedAt reviewTime sealRequirement requiredCma requiredCnas'),
    'mobileSampleFlow': {'inbound': leaves('operatorName operatorAccount operatedAt'),
                         'return': leaves('disposalMethod')}}


def _paths(shape, prefix=()):
    for key, child in shape.items():
        path = (*prefix, key)
        if isinstance(child, dict):
            yield from _paths(child, path)
        else:
            yield path


def _source(column):
    source = cast(column, Text)
    return case((func.json_valid(source), source), else_='{}')


class _projection_values(FunctionElement):
    """Return one slot per requested path, including missing and JSON null."""
    type = Text()
    inherit_cache = False

    def __init__(self, source, paths):
        self.paths = paths
        super().__init__(source)


@compiles(_projection_values, 'sqlite')
def _sqlite_values(element, compiler, **kw):
    source = list(element.clauses)[0]
    value = func.json_extract(source, *element.paths)
    if len(element.paths) == 1:
        value = func.json_array(value)
    return compiler.process(value, **kw)


@compiles(_projection_values, 'mysql')
@compiles(_projection_values, 'mariadb')
def _mysql_values(element, compiler, **kw):
    source = list(element.clauses)[0]
    if getattr(compiler.dialect, 'is_mariadb', False):
        return compiler.process(func.json_array(*[
            func.json_extract(source, path) for path in element.paths]), **kw)
    # MySQL multi-path JSON_EXTRACT drops absent paths. JSON_TABLE preserves
    # positions and JSON types while parsing the large source once per chunk.
    columns = ', '.join(
        f"c{i} JSON PATH {compiler.render_literal_value(path, Text())} NULL ON EMPTY"
        for i, path in enumerate(element.paths))
    values = ', '.join(f'list_json.c{i}' for i in range(len(element.paths)))
    return (f"(SELECT JSON_ARRAY({values}) FROM JSON_TABLE("
            f"{compiler.process(source, **kw)}, '$' COLUMNS ({columns})) AS list_json)")


def read_list(query, model, *, shape=None, column_names=None):
    """Keep the caller's scope/filters/order; never fetch detail/info wholesale."""
    shape = shape if shape is not None else DETAIL if model is Report else ENTRUST_INFO if model is Entrust else AGREEMENT_INFO
    field = 'detail' if model is Report else 'info'
    # Database-specific extraction must preserve missing-path positions.
    # Other deployments must implement a projection, never silently read full forms.
    if db.engine.dialect.name not in {'sqlite', 'mysql', 'mariadb'}:
        raise RuntimeError('This database requires a list JSON projection implementation')
    columns = [c for c in model.__table__.columns if c.key != field
               and (column_names is None or c.key in column_names)]
    paths = list(_paths(shape))
    # One multi-path extraction per chunk, not one parse of a large JSON value
    # for every field. Keep under SQLite's function argument limit as well.
    chunks = [paths[i:i+100] for i in range(0, len(paths), 100)]
    expressions = [*columns]
    for chunk in chunks:
        expressions.append(_projection_values(_source(getattr(model, field)),
                           ['$.' + '.'.join(path) for path in chunk]))
    if model is Report:
        # Preserve legacy checkInput truthiness, even if it only has non-list fields.
        check = func.json_extract(_source(Report.detail), '$.checkInput')
        expressions.append(and_(func.lower(func.json_type(check)) == 'object', check != '{}'))
    result = []
    for values in query.with_entities(*expressions).all():
        attrs = dict(zip((c.key for c in columns), values))
        data = {}
        for index, chunk in enumerate(chunks):
            extracted = json.loads(values[len(columns)+index] or 'null')
            if not isinstance(extracted, list) or len(extracted) != len(chunk):
                raise ValueError('List JSON projection returned misaligned fields')
            for path, value in zip(chunk, extracted or [None] * len(chunk)):
                if value is None:
                    continue
                target = data
                for key in path[:-1]:
                    target = target.setdefault(key, {})
                target[path[-1]] = value
        if model is Report:
            # Empty nested projections must not invent a saved data-entry form.
            if not data.get('checkInput') and values[-1]:
                data['checkInput'] = {'_listHasSavedInput': True}
            elif not values[-1]:
                data['checkInput'] = {}
        attrs[field] = data
        result.append(model(**attrs))
    return result


def list_reports(query, *, page_ids=None):
    rows = read_list(query, Report)
    if page_ids is not None:
        order = {identity: index for index, identity in enumerate(page_ids)}
        rows.sort(key=lambda row: order[row.id])
    return rows


def list_entrusts(query, *, page_ids=None):
    rows = read_list(query, Entrust)
    if page_ids is not None:
        order = {identity: index for index, identity in enumerate(page_ids)}
        rows.sort(key=lambda row: order[row.id])
    return rows


def list_agreements(query):
    return read_list(query, Agreement)
