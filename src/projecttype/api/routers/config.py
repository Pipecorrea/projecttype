"""Editor de prompts / casos borde (base de PT-22).

Escribibles: l3.yaml, reglas_discriminantes.yaml, few_shot_examples.yaml (cambian
prompt_version, mecanismo diseñado para afinar sin re-clasificar la cartera).
Solo lectura: la taxonomía (editar tipos cambia taxonomy_hash → PT-22).
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from projecttype.review.config_files import (
    ConfigFileInfo,
    ConfigWriteError,
    list_config_files,
    read_config_file,
    write_config_file,
)

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigFileResponse(BaseModel):
    kind: str
    path: str
    content: str
    version: str
    bytes: int
    writable: bool


class WriteConfigRequest(BaseModel):
    content: str = Field(min_length=0)


def _to_response(info: ConfigFileInfo) -> ConfigFileResponse:
    return ConfigFileResponse(**asdict(info))


@router.get("/files", response_model=list[ConfigFileResponse])
def list_files() -> list[ConfigFileResponse]:
    return [_to_response(f) for f in list_config_files()]


@router.get("/file/{kind}", response_model=ConfigFileResponse)
def get_file(kind: str) -> ConfigFileResponse:
    try:
        info = read_config_file(kind)
    except ConfigWriteError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(info)


@router.put("/file/{kind}", response_model=ConfigFileResponse)
def put_file(kind: str, body: WriteConfigRequest) -> ConfigFileResponse:
    try:
        info = write_config_file(kind, body.content)
    except ConfigWriteError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(info)
