"""Document version history endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from typing import Optional
import psycopg2

from backend.config import settings

router = APIRouter(prefix="/api/doc-history", tags=["doc-history"])


class DocumentVersion(BaseModel):
    version_id: str
    source_key: str
    source_label: str
    version_label: str
    pub_date: Optional[date]
    url: str
    doc_type: str          # 'xml' | 'pdf'
    is_indexed: bool
    is_latest_pdf: bool
    xml_doc_id: Optional[str]
    node_count: Optional[int] = None


class DocumentHistory(BaseModel):
    source_key: str
    source_label: str
    versions: list[DocumentVersion]
    indexed_version: Optional[DocumentVersion]   # convenience: the is_indexed=True entry


@router.get("", response_model=list[DocumentHistory])
def list_all_histories():
    """Return version history for all registered document sources."""
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT source_key, source_label
                FROM regulatory_document_versions
                ORDER BY source_key
            """)
            sources = cur.fetchall()

    return [_get_history(sk, sl) for sk, sl in sources]


@router.get("/{source_key}", response_model=DocumentHistory)
def get_history(source_key: str):
    """Return version history for a specific document source."""
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT source_label FROM regulatory_document_versions "
                "WHERE source_key = %s LIMIT 1",
                (source_key,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Source '{source_key}' not found")
    return _get_history(source_key, row[0])


def _get_history(source_key: str, source_label: str) -> DocumentHistory:
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    rdv.version_id::text,
                    rdv.source_key,
                    rdv.source_label,
                    rdv.version_label,
                    rdv.pub_date,
                    rdv.url,
                    rdv.doc_type,
                    rdv.is_indexed,
                    rdv.is_latest_pdf,
                    rdv.xml_doc_id::text,
                    COUNT(rn.node_id) AS node_count
                FROM regulatory_document_versions rdv
                LEFT JOIN harvest_documents hd ON hd.doc_id = rdv.xml_doc_id
                LEFT JOIN regulatory_nodes rn ON rn.source_doc_id = hd.doc_id
                WHERE rdv.source_key = %s
                GROUP BY rdv.version_id, rdv.source_key, rdv.source_label,
                         rdv.version_label, rdv.pub_date, rdv.url, rdv.doc_type,
                         rdv.is_indexed, rdv.is_latest_pdf, rdv.xml_doc_id
                ORDER BY rdv.pub_date DESC NULLS LAST, rdv.version_label DESC
            """, (source_key,))
            rows = cur.fetchall()

    versions = [
        DocumentVersion(
            version_id=r[0],
            source_key=r[1],
            source_label=r[2],
            version_label=r[3],
            pub_date=r[4],
            url=r[5],
            doc_type=r[6],
            is_indexed=r[7],
            is_latest_pdf=r[8],
            xml_doc_id=r[9],
            node_count=r[10] if r[10] > 0 else None,
        )
        for r in rows
    ]

    indexed = next((v for v in versions if v.is_indexed), None)
    return DocumentHistory(
        source_key=source_key,
        source_label=source_label,
        versions=versions,
        indexed_version=indexed,
    )
