"""Catálogo de imágenes autorizadas, tal como lo ve el panel para elegir un servicio."""

from fastapi import APIRouter, Request

from minipaas.common.catalog import CatalogEntry, enabled_entries
from minipaas.controlplane.api.deps import SessionDep

router = APIRouter(prefix="/api/catalog")


def entry_to_dict(entry: CatalogEntry) -> dict:
    """Solo lo que el panel necesita: nada de opciones de Docker (usuario, tmpfs, PIDs...)."""
    return {
        "id": entry.id,
        "name": entry.name,
        "description": entry.description,
        "version": entry.version,
        "repository": entry.repository,
        "digest": entry.digest,
        "architectures": list(entry.architectures),
        "internal_ports": list(entry.internal_ports),
        "default_internal_port": entry.default_internal_port,
        "publishable": entry.publishable,
        "env": [
            {
                "name": v.name,
                "label": v.label,
                "help": v.help,
                "pattern": v.pattern,
                "max_length": v.max_length,
            }
            for v in entry.env
        ],
        "memory_mb": _range(entry.memory_mb),
        "cpus": _range(entry.cpus),
        "license": entry.license,
        "source": entry.source,
        "limitations": entry.limitations,
        "test_only": entry.test_only,
    }


def _range(value) -> dict:
    return {"default": value.default, "min": value.minimum, "max": value.maximum}


@router.get("")
def get_catalog(request: Request, _: SessionDep) -> dict:
    include_test = request.app.state.settings.enable_test_catalog
    return {"items": [entry_to_dict(e) for e in enabled_entries(include_test)]}
