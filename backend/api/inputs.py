"""输入文档管理路由：上传、列表、删除。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from manimind.bootstrap import repo_root, sanitize_identifier

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt", ".text"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _inputs_dir(project_id: str) -> Path:
    safe_id = sanitize_identifier(project_id)
    return repo_root() / "runtime" / "inputs" / safe_id


def _manifest_path(project_id: str) -> Path:
    return _inputs_dir(project_id) / "manifest.json"


def _load_manifest(project_id: str) -> list[dict[str, Any]]:
    path = _manifest_path(project_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(project_id: str, docs: list[dict[str, Any]]) -> None:
    path = _manifest_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/{project_id}/inputs/upload")
async def upload_input_document(
    project_id: str,
    file: UploadFile = File(...),
    role: str = Form("raw_material"),
    title: str = Form(""),
    consumer_roles: str = Form(""),
    notes: str = Form(""),
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing_filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported_extension: {suffix}. Allowed: {ALLOWED_EXTENSIONS}",
        )

    inputs_dir = _inputs_dir(project_id)
    inputs_dir.mkdir(parents=True, exist_ok=True)

    dest = inputs_dir / file.filename
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file_too_large")
    dest.write_bytes(content)

    consumers = [r.strip() for r in consumer_roles.split(",") if r.strip()] if consumer_roles else []

    docs = _load_manifest(project_id)
    doc_entry = {
        "path": str(dest.relative_to(repo_root())),
        "role": role,
        "title": title or file.filename,
        "consumer_roles": consumers,
        "notes": notes,
    }
    existing_idx = next((i for i, d in enumerate(docs) if d.get("path") == doc_entry["path"]), None)
    if existing_idx is not None:
        docs[existing_idx] = doc_entry
    else:
        docs.append(doc_entry)
    _save_manifest(project_id, docs)

    return {"status": "uploaded", "document": doc_entry}


@router.get("/{project_id}/inputs")
async def list_input_documents(project_id: str) -> dict[str, Any]:
    docs = _load_manifest(project_id)
    inputs_dir = _inputs_dir(project_id)
    files_on_disk = []
    if inputs_dir.exists():
        files_on_disk = [
            f.name for f in inputs_dir.iterdir()
            if f.is_file() and f.name != "manifest.json"
        ]
    return {"project_id": project_id, "documents": docs, "files_on_disk": files_on_disk}


@router.delete("/{project_id}/inputs/{filename}")
async def delete_input_document(project_id: str, filename: str) -> dict[str, Any]:
    inputs_dir = _inputs_dir(project_id)
    file_path = inputs_dir / filename
    if file_path.exists():
        file_path.unlink()

    docs = _load_manifest(project_id)
    rel_path = str(file_path.relative_to(repo_root()))
    docs = [d for d in docs if d.get("path") != rel_path]
    _save_manifest(project_id, docs)

    return {"status": "deleted", "filename": filename}


@router.post("/create")
async def create_project(body: dict[str, Any]) -> dict[str, Any]:
    """从前端创建项目：生成 manifest 并初始化目录。"""
    project_id = body.get("project_id")
    title = body.get("title", "")
    audience = body.get("audience", "大众观众")
    style_refs = body.get("style_refs", [])
    segments = body.get("segments", [])

    if not project_id:
        raise HTTPException(status_code=400, detail="missing_project_id")

    safe_id = sanitize_identifier(project_id)
    inputs_dir = _inputs_dir(safe_id)
    inputs_dir.mkdir(parents=True, exist_ok=True)

    docs = _load_manifest(safe_id)

    paper_path = ""
    if docs:
        raw_docs = [d for d in docs if d.get("role") == "raw_material"]
        if raw_docs:
            paper_path = raw_docs[0]["path"]

    manifest = {
        "project_id": safe_id,
        "title": title,
        "source_bundle": {
            "paper_path": paper_path,
            "note_paths": [],
            "audience": audience,
            "style_refs": style_refs,
            "documents": docs,
        },
        "segments": segments,
    }

    config_dir = repo_root() / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = config_dir / f"{safe_id}.json"
    manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    project_dir = repo_root() / "runtime" / "projects" / safe_id
    project_dir.mkdir(parents=True, exist_ok=True)

    return {
        "status": "created",
        "project_id": safe_id,
        "manifest_path": str(manifest_file.relative_to(repo_root())),
        "manifest": manifest,
    }
