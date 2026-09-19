from __future__ import annotations

from .models import Calculation, StoredCsvResult, StoredInputFile


def calculation_artifacts(calculation: Calculation, *, admin: bool = False) -> list[dict]:
    """Return only files that still physically exist for this calculation.

    Calculation records intentionally survive independent admin deletion of
    input/output blobs, so either artifact may be absent.
    """

    prefix = "/api/v1/admin/calculations" if admin else "/api/v1/calculations"
    artifacts: list[dict] = []

    if calculation.input_file_id:
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

    if calculation.csv_result_id:
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


def resolve_artifact(calculation: Calculation, file_id):
    artifact = resolve_artifact_object(calculation, file_id)
    if artifact is None:
        return None

    if isinstance(artifact, StoredInputFile):
        filename = (
            (calculation.input_payload or {}).get("original_filename")
            or artifact.canonical_filename
        )
        return bytes(artifact.data), artifact.content_type, filename, artifact.size_bytes

    if isinstance(artifact, StoredCsvResult):
        return bytes(artifact.data), artifact.content_type, artifact.filename, artifact.size_bytes

    return None
