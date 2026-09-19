from __future__ import annotations

from io import BytesIO

from .models import Calculation, StoredCsvResult, StoredInputFile


def calculation_artifacts(calculation: Calculation, *, admin: bool = False) -> list[dict]:
    """Return only artifacts whose bytes are still available."""

    prefix = "/api/v1/admin/calculations" if admin else "/api/v1/calculations"
    artifacts: list[dict] = []

    if calculation.input_file_id and artifact_exists(calculation.input_file):
        input_file = calculation.input_file
        uploaded_name = (
            (calculation.input_payload or {}).get("original_filename")
            or input_file.canonical_filename
        )
        item = {
            "id": input_file.id,
            "kind": "input_workbook",
            "filename": uploaded_name,
            "original_filename": uploaded_name,
            "content_type": input_file.content_type,
            "size_bytes": input_file.size_bytes,
            "sha256": input_file.sha256,
            "download_path": f"{prefix}/{calculation.public_id}/files/{input_file.id}/download/",
        }
        if admin:
            item["delete_path"] = f"{prefix}/{calculation.public_id}/files/{input_file.id}/"
        artifacts.append(item)

    if calculation.csv_result_id and artifact_exists(calculation.csv_result):
        csv_result = calculation.csv_result
        item = {
            "id": csv_result.id,
            "kind": "legacy_csv",
            "filename": csv_result.filename,
            "original_filename": "",
            "content_type": csv_result.content_type,
            "size_bytes": csv_result.size_bytes,
            "sha256": csv_result.sha256,
            "download_path": f"{prefix}/{calculation.public_id}/files/{csv_result.id}/download/",
        }
        if admin:
            item["delete_path"] = f"{prefix}/{calculation.public_id}/files/{csv_result.id}/"
        artifacts.append(item)

    return artifacts


def resolve_artifact_object(calculation: Calculation, file_id):
    if calculation.input_file_id and str(calculation.input_file_id) == str(file_id):
        return calculation.input_file
    if calculation.csv_result_id and str(calculation.csv_result_id) == str(file_id):
        return calculation.csv_result
    return None


def artifact_exists(artifact) -> bool:
    storage_file = getattr(artifact, "storage_file", None)
    if storage_file and storage_file.name:
        try:
            return storage_file.storage.exists(storage_file.name)
        except Exception:
            return False
    return getattr(artifact, "data", None) is not None


def resolve_artifact(calculation: Calculation, file_id):
    """Resolve an artifact to a file-like object plus download metadata.

    Supabase-backed files are opened lazily so Django can stream them instead
    of loading the entire object into memory. Legacy BinaryField rows remain
    readable until ``migrate_binary_artifacts_to_storage`` is run.
    """

    artifact = resolve_artifact_object(calculation, file_id)
    if artifact is None:
        return None

    if isinstance(artifact, StoredInputFile):
        filename = (
            (calculation.input_payload or {}).get("original_filename")
            or artifact.canonical_filename
        )
    elif isinstance(artifact, StoredCsvResult):
        filename = artifact.filename
    else:
        return None

    storage_file = artifact.storage_file
    if storage_file and storage_file.name:
        try:
            storage_file.open("rb")
            return storage_file, artifact.content_type, filename, artifact.size_bytes
        except Exception:
            return None

    legacy_data = getattr(artifact, "data", None)
    if legacy_data is not None:
        return BytesIO(bytes(legacy_data)), artifact.content_type, filename, artifact.size_bytes

    return None
