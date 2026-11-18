from uuid import uuid4
from .policy import Problem
from .schema import files


def append_pdf(
    db,
    actor,
    report_id,
    data,
    upload,
    content,
    digest,
    store,
    created_paths,
    max_bytes,
    docs,
    now,
    audit,
):
    if (
        upload is None
        or not upload.filename.lower().endswith(".pdf")
        or not content.startswith(b"%PDF-")
    ):
        raise Problem("请选择 PDF 文件，文件内容和扩展名均须为 PDF。")
    if len(content) > max_bytes:
        raise Problem("文件超过单个 PDF 大小上限。")
    name = upload.filename.replace("\\", "/").split("/")[-1]
    if len(name) > 255:
        raise Problem("文件名最多 255 个字符。")
    kind = data.get("kind")
    if kind not in {"source", "draft"}:
        raise Problem("请选择原始记录或待签报告。")
    replaces = data.get("replaces")
    if kind == "draft":
        replaces = next((f["id"] for f in docs if f["kind"] == "draft"), None)
    if replaces is not None and not any(f["id"] == replaces and f["kind"] == kind for f in docs):
        raise Problem("请选择当前版本中同类型的文件。")
    file_key = uuid4().hex
    destination = store / file_key
    with destination.open("xb") as stream:
        created_paths.append(destination)
        stream.write(content)
    file_id = db.scalar(
        files.insert()
        .values(
            report_id=report_id,
            name=name,
            key=file_key,
            kind=kind,
            sha256=digest,
            size=len(content),
            by_user=actor.id,
            created=now,
            replaces=replaces,
        )
        .returning(files.c.id)
    )
    audit.update(fileId=file_id, replaces=replaces, sha256=digest)
