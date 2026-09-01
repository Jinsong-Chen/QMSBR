"""Build and validate QMSBR from split private/public repositories."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
from html import escape
from html.parser import HTMLParser
import ipaddress
import json
import os
import platform
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
import zipfile

import yaml


WEBSITE_ROOT = Path(__file__).resolve().parents[1]
UMBRELLA_ROOT = WEBSITE_ROOT.parent
DEFAULT_MATERIALS_ROOT = UMBRELLA_ROOT / "materials"
WORK_ROOT = WEBSITE_ROOT / ".qmsbr"
PROJECT_ROOT = WORK_ROOT / "project"
SITE_ROOT = WORK_ROOT / "site"
MANIFEST_RELATIVE = "publication/public-files.yml"

CATALOG_RELATIVE = "publication/catalog.yml"
APPROVALS_RELATIVE = "publication/approvals.yml"
OUTPUT_POLICY_PATH = WEBSITE_ROOT / "config/output-policy.yml"
SOURCE_POLICY_PATH = WEBSITE_ROOT / "config/source-policy.yml"
QUARTO_BASE_PATH = WEBSITE_ROOT / "config/quarto-base.yml"

QUARTO_WINDOWS_URL = (
    "https://github.com/quarto-dev/quarto-cli/releases/download/"
    "v1.10.18/quarto-1.10.18-win.zip"
)
QUARTO_WINDOWS_SHA256 = (
    "4e824652ff0da3f646868277582ed59c0872d1456e35350b7d7cdc4243ee18c2"
)
QUARTO_WINDOWS_SIZE = 148_278_833
PY_YAML_VERSION = "6.0.3"

ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*$")
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}$")
TEXT_EXTENSIONS = {
    "", ".bib", ".cff", ".csl", ".css", ".csv", ".html", ".js",
    ".json", ".lock", ".map", ".md", ".py", ".qmd", ".r", ".rproj",
    ".scss", ".sh", ".sha256", ".sps", ".svg", ".tex", ".toml",
    ".txt", ".xml", ".yaml", ".yml",
}
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class PublicationError(RuntimeError):
    """A publication boundary or reproducibility check failed."""


def check_python_environment() -> None:
    actual = str(getattr(yaml, "__version__", ""))
    if actual != PY_YAML_VERSION:
        raise PublicationError(
            f"PyYAML {PY_YAML_VERSION} is required by requirements-release.txt; "
            f"observed {actual or 'unknown'}"
        )


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.Node, deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise PublicationError(f"Duplicate YAML key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PublicationError(f"Cannot read {path}: {exc}") from exc
    return load_yaml_bytes(data, str(path))


def load_yaml_bytes(data: bytes, owner: str) -> dict[str, Any]:
    try:
        value = yaml.load(data.decode("utf-8"), Loader=UniqueKeyLoader)
    except (UnicodeError, yaml.YAMLError) as exc:
        raise PublicationError(f"Cannot read {owner}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationError(f"{owner} must contain a YAML mapping")
    return value


def yaml_bytes(value: Any, header: str | None = None) -> bytes:
    body = yaml.dump(
        value, Dumper=NoAliasDumper, sort_keys=False, allow_unicode=True,
        default_flow_style=False, width=100,
    )
    text = f"# {header}\n{body}" if header else body
    return text.replace("\r\n", "\n").encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temporary = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-", dir=path.parent,
    )
    temporary = Path(raw_temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def normalize_relative(value: object, owner: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicationError(f"{owner} must be a non-empty relative path")
    if (
        "\\" in value
        or any(character in value for character in "*?[]<>\"|")
        or any(ord(character) < 32 for character in value)
    ):
        raise PublicationError(f"{owner} must be an exact POSIX-style path: {value!r}")
    path = PurePosixPath(value)
    if value != path.as_posix():
        raise PublicationError(f"{owner} is not a canonical relative path: {value!r}")
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PublicationError(f"{owner} escapes its repository: {value!r}")
    for part in path.parts:
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED_NAMES or part.endswith((" ", ".")) or ":" in part:
            raise PublicationError(f"{owner} is not portable on Windows: {value!r}")
    return path.as_posix()


def is_link_or_junction(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise PublicationError(f"Cannot inspect {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse)


def checked_file(root: Path, relative: str, owner: str) -> Path:
    relative = normalize_relative(relative, owner)
    root = root.resolve(strict=True)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    current = root
    for part in PurePosixPath(relative).parts:
        if not current.is_dir():
            raise PublicationError(f"{owner} has a non-directory parent: {current}")
        matches = [entry.name for entry in current.iterdir() if entry.name.casefold() == part.casefold()]
        if len(matches) != 1 or matches[0] != part:
            raise PublicationError(f"{owner} has missing, ambiguous, or case-mismatched path: {relative}")
        current = current / part
        if is_link_or_junction(current):
            raise PublicationError(f"{owner} must not traverse a link or junction: {relative}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise PublicationError(f"{owner} escapes its repository: {relative}") from exc
    if not resolved.is_file():
        raise PublicationError(f"{owner} is not a file: {relative}")
    return resolved


def canonical_bytes(relative: str, data: bytes) -> bytes:
    if PurePosixPath(relative).suffix.lower() in TEXT_EXTENSIONS:
        return data.replace(b"\r\n", b"\n")
    return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(root: Path, relative: str, owner: str) -> str:
    path = checked_file(root, relative, owner)
    return sha256_bytes(canonical_bytes(relative, path.read_bytes()))


def require_mapping(value: object, owner: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PublicationError(f"{owner} must be a mapping")
    return value


def require_records(value: object, owner: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise PublicationError(f"{owner} must be a list of mappings")
    return value


def require_string_list(value: object, owner: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PublicationError(f"{owner} must be a list of strings")
    if len({item.casefold() for item in value}) != len(value):
        raise PublicationError(f"{owner} contains duplicate values")
    return value


def approved_hash_mapping(value: object, owner: str) -> dict[str, str]:
    mapping = require_mapping(value, owner)
    result: dict[str, str] = {}
    for raw_path, raw_digest in mapping.items():
        path = normalize_relative(raw_path, f"{owner} path")
        digest = str(raw_digest).lower()
        if not DIGEST_PATTERN.fullmatch(digest):
            raise PublicationError(f"{owner} has an invalid SHA-256 for {path}")
        if path.casefold() in {key.casefold() for key in result}:
            raise PublicationError(f"{owner} has a case-colliding path: {path}")
        result[path] = digest
    return result


def render_context_digest(context: dict[str, Any]) -> str:
    payload = json.dumps(
        context, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return sha256_bytes(payload)


def load_model(materials_root: Path) -> dict[str, Any]:
    materials_root = materials_root.resolve(strict=True)
    catalog_path = checked_file(
        materials_root, CATALOG_RELATIVE, "publication catalogue",
    )
    catalog_bytes = canonical_bytes(CATALOG_RELATIVE, catalog_path.read_bytes())
    catalog = load_yaml_bytes(catalog_bytes, str(catalog_path))
    approvals_path = checked_file(
        materials_root, APPROVALS_RELATIVE, "publication approvals",
    )
    approvals_bytes = canonical_bytes(APPROVALS_RELATIVE, approvals_path.read_bytes())
    approvals = load_yaml_bytes(approvals_bytes, str(approvals_path))
    output_path = checked_file(
        WEBSITE_ROOT, "config/output-policy.yml", "website output policy",
    )
    output_bytes = canonical_bytes("config/output-policy.yml", output_path.read_bytes())
    output = load_yaml_bytes(output_bytes, str(output_path))
    if approvals.get("schema_version") != 1 or output.get("schema_version") != 1:
        raise PublicationError("Unsupported publication-policy schema version")

    output_release = require_mapping(output.get("release"), "output policy release")
    scope = require_mapping(approvals.get("release_scope"), "approval release_scope")
    module_ids = require_string_list(output_release.get("module_ids"), "release module_ids")
    note_ids = require_string_list(output_release.get("note_module_ids"), "release note_module_ids")
    supplement_ids = require_string_list(output_release.get("supplement_ids"), "release supplement_ids")
    if module_ids != require_string_list(scope.get("modules"), "approval modules"):
        raise PublicationError("Website and materials module scopes disagree")
    if note_ids != require_string_list(scope.get("classroom_notes"), "approval classroom_notes"):
        raise PublicationError("Website and materials note scopes disagree")
    if supplement_ids != require_string_list(scope.get("supplements"), "approval supplements"):
        raise PublicationError("Website and materials supplement scopes disagree")
    if supplement_ids:
        raise PublicationError("Release 1 must have an empty supplement scope")

    modules = require_records(catalog.get("modules"), "catalog modules")
    module_map: dict[str, dict[str, Any]] = {}
    for module in modules:
        module_id = str(module.get("id", ""))
        if not ID_PATTERN.fullmatch(module_id) or module_id in module_map:
            raise PublicationError(f"Invalid or duplicate module ID: {module_id!r}")
        module_map[module_id] = module
    available_ids = [str(module["id"]) for module in modules if module.get("public_stage") == "available"]
    if available_ids != module_ids:
        raise PublicationError(
            "The catalog's available modules must exactly match Release 1: "
            + ", ".join(module_ids)
        )

    released: list[dict[str, Any]] = []
    for module_id in module_ids:
        module = module_map.get(module_id)
        if module is None:
            raise PublicationError(f"Release module is absent from catalog: {module_id}")
        chapter = require_mapping(module.get("chapter"), f"{module_id} chapter")
        source = normalize_relative(chapter.get("source"), f"{module_id} chapter source")
        pdf = normalize_relative(chapter.get("pdf"), f"{module_id} chapter PDF")
        if not source.startswith("chapters/") or not pdf.startswith("chapters/"):
            raise PublicationError(f"{module_id} must use stable chapters/ routes")
        if require_string_list(module.get("supplements", []), f"{module_id} supplements"):
            raise PublicationError(f"{module_id} must expose no supplements in Release 1")
        note = module.get("classroom_note_example")
        if module_id in note_ids:
            note_map = require_mapping(note, f"{module_id} classroom note")
            normalize_relative(note_map.get("pdf"), f"{module_id} classroom-note PDF")
        elif note is not None:
            raise PublicationError(f"Unapproved classroom-note example on {module_id}")
        released.append(module)

    render_only = approved_hash_mapping(
        approvals.get("render_only_inputs"), "render_only_inputs",
    )
    approved_sources = approved_hash_mapping(
        approvals.get("approved_sources"), "approved_sources",
    )
    approved_binaries = approved_hash_mapping(
        approvals.get("approved_binaries"), "approved_binaries",
    )
    approved_rendered_assets = approved_hash_mapping(
        approvals.get("approved_rendered_assets"), "approved_rendered_assets",
    )
    expected_sources = {module["chapter"]["source"] for module in released}
    expected_binaries = {module["chapter"]["pdf"] for module in released}
    expected_binaries.update(
        module["classroom_note_example"]["pdf"]
        for module in released if module["id"] in note_ids
    )
    if set(approved_sources) != expected_sources:
        raise PublicationError("approved_sources does not exactly match released chapter sources")
    if set(approved_binaries) != expected_binaries:
        raise PublicationError("approved_binaries does not exactly match released PDFs")
    expected_rendered_assets = set(require_string_list(
        output.get("generated_chapter_assets"), "generated_chapter_assets",
    ))
    if set(approved_rendered_assets) != expected_rendered_assets:
        raise PublicationError(
            "approved_rendered_assets does not exactly match generated_chapter_assets"
        )

    for group_name, mapping in (
        ("render-only input", render_only),
        ("approved source", approved_sources),
        ("approved binary", approved_binaries),
    ):
        for relative, approved in mapping.items():
            actual = file_digest(materials_root, relative, group_name)
            if actual != approved:
                raise PublicationError(
                    f"{group_name} changed without approval: {relative}\n"
                    f"  approved: {approved}\n  current:  {actual}"
                )

    review = require_mapping(approvals.get("review"), "approvals review")
    version = str(review.get("quarto_version", ""))
    r_version = str(review.get("r_version", ""))
    recipe = review.get("recipe_version")
    if (
        not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", r_version)
        or not isinstance(recipe, int)
    ):
        raise PublicationError(
            "review requires exact quarto_version, r_version, and integer recipe_version"
        )
    release = require_mapping(approvals.get("release"), "approvals release")
    release_id = str(release.get("id", ""))
    epoch = release.get("source_date_epoch")
    if (
        not re.fullmatch(r"[0-9]{4}\.[0-9]+(?:\.[0-9]+)?", release_id)
        or not isinstance(epoch, int)
    ):
        raise PublicationError(
            "release.id must be YYYY.N or YYYY.N.P and source_date_epoch must be an integer"
        )

    approved_contexts = approved_hash_mapping(
        approvals.get("approved_render_contexts"), "approved_render_contexts",
    )
    if set(approved_contexts) != set(module_ids):
        raise PublicationError("approved_render_contexts does not exactly match released modules")
    contexts: dict[str, dict[str, Any]] = {}
    context_hashes: dict[str, str] = {}
    for module in released:
        module_id = module["id"]
        paths = sorted(
            [module["chapter"]["source"], *render_only], key=str.casefold,
        )
        context = {
            "recipe_version": recipe,
            "quarto_version": version,
            "r_version": r_version,
            "source_date_epoch": epoch,
            "inputs": {
                path: file_digest(materials_root, path, f"{module_id} render input")
                for path in paths
            },
        }
        digest = render_context_digest(context)
        if digest != approved_contexts[module_id]:
            raise PublicationError(
                f"Render inputs changed without approval: {module_id}\n"
                f"  approved: {approved_contexts[module_id]}\n  current:  {digest}"
            )
        contexts[module_id] = context
        context_hashes[module_id] = digest

    return {
        "materials_root": materials_root,
        "catalog": catalog,
        "catalog_sha256": sha256_bytes(catalog_bytes),
        "approvals": approvals,
        "approvals_sha256": sha256_bytes(approvals_bytes),
        "output": output,
        "output_policy_sha256": sha256_bytes(output_bytes),
        "modules": released,
        "module_ids": module_ids,
        "note_ids": note_ids,
        "render_only": render_only,
        "approved_sources": approved_sources,
        "approved_binaries": approved_binaries,
        "approved_rendered_assets": approved_rendered_assets,
        "render_contexts": contexts,
        "render_context_hashes": context_hashes,
        "quarto_version": version,
        "r_version": r_version,
        "release_id": release_id,
        "source_date_epoch": epoch,
    }


def manifest_document(model: dict[str, Any]) -> dict[str, Any]:
    material_inputs = {
        **model["approved_sources"],
        **model["render_only"],
        **model["approved_binaries"],
    }
    return {
        "schema_version": 1,
        "catalog_sha256": model["catalog_sha256"],
        "approvals_sha256": model["approvals_sha256"],
        "output_policy_sha256": model["output_policy_sha256"],
        "release": {
            "id": model["release_id"],
            "tag": f"v{model['release_id']}",
            "quarto_version": model["quarto_version"],
            "r_version": model["r_version"],
            "pyyaml_version": PY_YAML_VERSION,
        },
        "module_ids": model["module_ids"],
        "note_module_ids": model["note_ids"],
        "supplement_ids": [],
        "render_targets": [module["chapter"]["source"] for module in model["modules"]],
        "render_only_inputs": list(model["render_only"]),
        "copied_resources": list(model["approved_binaries"]),
        "material_inputs": material_inputs,
        "render_contexts": model["render_contexts"],
        "render_context_hashes": model["render_context_hashes"],
        "approved_rendered_assets": model["approved_rendered_assets"],
        "required_outputs": require_string_list(
            model["output"].get("required_outputs"), "required_outputs",
        ),
    }


def sync_manifest_model(model: dict[str, Any], *, check: bool) -> bool:
    expected = yaml_bytes(
        manifest_document(model),
        "Generated by website/tools/manage.py; do not edit by hand.",
    )
    path = model["materials_root"] / MANIFEST_RELATIVE
    current = path.read_bytes() if path.is_file() else None
    if current == expected:
        print("Publication manifest is current.")
        return False
    if check:
        raise PublicationError(
            f"Publication manifest is stale or absent: {path}\n"
            "Run `python tools/manage.py sync`."
        )
    atomic_write(path, expected)
    print(f"Updated {path}")
    return True


def sync_manifest(materials_root: Path, *, check: bool) -> bool:
    return sync_manifest_model(load_model(materials_root), check=check)


def source_paths(root: Path) -> list[str]:
    git = root / ".git"
    if git.exists():
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if result.returncode:
            raise PublicationError(result.stderr.decode(errors="replace").strip())
        return sorted(
            (item.decode("utf-8") for item in result.stdout.split(b"\0") if item),
            key=str.casefold,
        )
    skipped = {".git", ".qmsbr", ".quarto", ".Rproj.user", "__pycache__", "_site"}
    result_paths: list[str] = []
    for current, directories, files in os.walk(root):
        current_path = Path(current)
        directories[:] = [
            name for name in directories
            if name not in skipped
            and not (current_path == root / "renv" and name in {"library", "local", "staging", "cellar"})
        ]
        for name in files:
            relative = (current_path / name).relative_to(root).as_posix()
            result_paths.append(relative)
    return sorted(result_paths, key=str.casefold)


def validate_source_repository(root: Path, policy_path: Path) -> None:
    policy = load_yaml(policy_path)
    paths = source_paths(root)
    exact_allowed_value = policy.get("allowed_files")
    if exact_allowed_value is not None:
        exact_allowed = {
            normalize_relative(path, "allowed_files path")
            for path in require_string_list(exact_allowed_value, "allowed_files")
        }
        actual = set(paths)
        missing = sorted(exact_allowed - actual, key=str.casefold)
        unexpected = sorted(actual - exact_allowed, key=str.casefold)
        if missing or unexpected:
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if unexpected:
                details.append("unexpected: " + ", ".join(unexpected))
            raise PublicationError(
                f"Exact source inventory failed for {root.name}; " + "; ".join(details)
            )
        forbidden_extensions = {item.casefold() for item in require_string_list(
            policy.get("forbidden_extensions", []), "forbidden extensions",
        )}
        for relative in paths:
            normalized = normalize_relative(relative, f"source path in {root.name}")
            if PurePosixPath(normalized).suffix.casefold() in forbidden_extensions:
                raise PublicationError(f"Forbidden file type in {root.name}: {normalized}")
            checked_file(root, normalized, f"source policy {root.name}")
        print(f"Source boundary OK: {root.name} ({len(paths)} exact files inspected).")
        return

    allowed_roots = set(require_string_list(policy.get("allowed_roots", policy.get("tracked_roots")), "allowed roots"))
    allowed_files = set(require_string_list(
        policy.get("allowed_root_files", policy.get("tracked_root_files")),
        "allowed root files",
    ))
    forbidden_roots = {item.casefold() for item in require_string_list(
        policy.get("forbidden_roots", policy.get("excluded_local_roots", [])),
        "forbidden roots",
    )}
    forbidden_extensions = {item.casefold() for item in require_string_list(
        policy.get("forbidden_extensions", []), "forbidden extensions",
    )}
    seen: set[str] = set()
    for relative in paths:
        normalized = normalize_relative(relative, f"source path in {root.name}")
        folded = normalized.casefold()
        if folded in seen:
            raise PublicationError(f"Case-colliding source path in {root}: {normalized}")
        seen.add(folded)
        parts = PurePosixPath(normalized).parts
        top = parts[0]
        if top.casefold() in forbidden_roots:
            raise PublicationError(f"Forbidden tracked/source root in {root.name}: {normalized}")
        if len(parts) == 1:
            if normalized not in allowed_files:
                raise PublicationError(f"Unexpected root file in {root.name}: {normalized}")
        elif top not in allowed_roots:
            raise PublicationError(f"Unexpected source root in {root.name}: {normalized}")
        if PurePosixPath(normalized).suffix.casefold() in forbidden_extensions:
            raise PublicationError(f"Forbidden file type in {root.name}: {normalized}")
        checked_file(root, normalized, f"source policy {root.name}")
    print(f"Source boundary OK: {root.name} ({len(paths)} files inspected).")


def validate_boundaries(materials_root: Path) -> None:
    if (UMBRELLA_ROOT / ".git").exists():
        raise PublicationError("The QMSBR umbrella must not itself be a Git repository")
    for name in ("planning", "instructor", "archive"):
        if (materials_root / name).exists() or (WEBSITE_ROOT / name).exists():
            raise PublicationError(f"Local-only {name}/ must remain outside both repositories")
    validate_source_repository(materials_root, materials_root / "publication/source-policy.yml")
    validate_source_repository(WEBSITE_ROOT, SOURCE_POLICY_PATH)


def public_fragments(model: dict[str, Any]) -> dict[str, bytes]:
    rows: list[str] = []
    for module in model["modules"]:
        number = escape(str(module["number"]))
        title = escape(str(module["title"]))
        summary = escape(str(module.get("summary", "")))
        stem = PurePosixPath(module["chapter"]["source"]).stem
        rows.append(
            "<tr>\n"
            f"<td>{number}</td>\n"
            f"<td><span class=\"status-badge\">Available</span>"
            f"<h3>{title}</h3><p>{summary}</p></td>\n"
            f"<td><a href=\"../chapters/{stem}.html\">Read online</a> · "
            f"<a href=\"../chapters/{stem}.pdf\">Download PDF</a></td>\n"
            "</tr>"
        )
    library = (
        "## Foundations and research reasoning {#conceptual-basis}\n\n"
        "<div class=\"library-table-wrap\">\n"
        "<table class=\"library-table\">\n"
        "<thead><tr><th>No.</th><th>Chapter</th><th>Formats</th></tr></thead>\n"
        "<tbody>\n" + "\n".join(rows) + "\n</tbody>\n</table>\n</div>\n"
    )
    note_module = next(module for module in model["modules"] if module["id"] in model["note_ids"])
    note = note_module["classroom_note_example"]
    note_text = (
        "::: {.note-card}\n"
        f"### Chapter {escape(str(note_module['number']))} classroom-note example\n\n"
        f"{escape(str(note.get('summary', '')))}\n\n"
        f"[Download the reviewed PDF](../{note['pdf']})\n"
        ":::\n"
    )
    roadmap_records = require_records(model["catalog"].get("roadmap"), "catalog roadmap")
    roadmap_cards = []
    for record in roadmap_records:
        roadmap_cards.append(
            "::: {.roadmap-card}\n"
            f"### {escape(str(record['number']))} · {escape(str(record['title']))}\n\n"
            "Coming later\n"
            ":::\n"
        )
    roadmap = "::: {.roadmap-grid}\n" + "\n".join(roadmap_cards) + ":::\n"
    return {
        "library/_generated/library.qmd": library.encode("utf-8"),
        "library/_generated/note-example.qmd": note_text.encode("utf-8"),
        "library/_generated/roadmap.qmd": roadmap.encode("utf-8"),
    }


def ensure_work_root() -> Path:
    website = WEBSITE_ROOT.resolve(strict=True)
    if WORK_ROOT.exists():
        if is_link_or_junction(WORK_ROOT):
            raise PublicationError(f"Ignored work root must not be a link or junction: {WORK_ROOT}")
        work = WORK_ROOT.resolve(strict=True)
    else:
        WORK_ROOT.mkdir(parents=False)
        work = WORK_ROOT.resolve(strict=True)
    try:
        work.relative_to(website)
    except ValueError as exc:
        raise PublicationError(f"Work root escapes the website repository: {WORK_ROOT}") from exc
    return work


def ensure_work_directory(relative: str) -> Path:
    """Create an ordinary directory below .qmsbr without traversing reparse points."""
    relative = normalize_relative(relative, "work directory")
    work = ensure_work_root()
    current = WORK_ROOT
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.exists():
            if is_link_or_junction(current) or not current.is_dir():
                raise PublicationError(
                    f"Ignored work directory must be an ordinary directory: {current}"
                )
        else:
            current.mkdir()
        try:
            current.resolve(strict=True).relative_to(work)
        except ValueError as exc:
            raise PublicationError(f"Work directory escapes {WORK_ROOT}: {current}") from exc
    return current


def verify_work_descendant_directory(path: Path, owner: str) -> Path:
    """Verify every lexical ancestor from .qmsbr to an existing directory."""
    work = ensure_work_root()
    try:
        relative = path.absolute().relative_to(WORK_ROOT.absolute())
    except ValueError as exc:
        raise PublicationError(f"{owner} is outside the ignored work root: {path}") from exc
    current = WORK_ROOT
    for part in relative.parts:
        current = current / part
        if not current.exists() or not current.is_dir() or is_link_or_junction(current):
            raise PublicationError(f"{owner} has an absent or linked ancestor: {current}")
        try:
            current.resolve(strict=True).relative_to(work)
        except ValueError as exc:
            raise PublicationError(f"{owner} escapes the ignored work root: {current}") from exc
    return current.resolve(strict=True)


def safe_remove_tree(path: Path) -> None:
    work = ensure_work_root()
    try:
        lexical = path.absolute()
        lexical.relative_to(WORK_ROOT.absolute())
    except ValueError as exc:
        raise PublicationError(f"Refusing to remove a directory outside {WORK_ROOT}: {path}") from exc
    current = WORK_ROOT
    for part in lexical.relative_to(WORK_ROOT.absolute()).parts[:-1]:
        current = current / part
        if current.exists() and is_link_or_junction(current):
            raise PublicationError(f"Refusing to traverse linked build directory: {current}")
    resolved_parent = path.parent.resolve(strict=True)
    try:
        resolved_parent.relative_to(work)
    except ValueError as exc:
        raise PublicationError(f"Refusing to remove a directory outside {WORK_ROOT}: {path}") from exc
    if path.exists():
        if is_link_or_junction(path):
            raise PublicationError(f"Refusing to remove linked build directory: {path}")
        shutil.rmtree(path)


def copy_snapshot(root: Path, relative: str) -> bytes:
    path = checked_file(root, relative, f"snapshot {relative}")
    return canonical_bytes(relative, path.read_bytes())


def current_website_input_hashes(model: dict[str, Any]) -> dict[str, str]:
    site_sources = require_mapping(model["output"].get("site_sources"), "site_sources")
    source_files = [
        *require_string_list(site_sources.get("render"), "site render targets"),
        *require_string_list(site_sources.get("assets"), "site assets"),
        "styles.scss",
    ]
    result = {
        f"src/{relative}": file_digest(
            WEBSITE_ROOT / "src", relative, f"website source {relative}",
        )
        for relative in source_files
    }
    for relative in (
        "CITATION.cff", "LICENSE", "NOTICE", "LICENSES/CC-BY-4.0.txt",
        "LICENSES/CC-BY-SA-3.0.txt", "LICENSES/CC0-1.0.txt", "LICENSES/MIT.txt",
    ):
        result[relative] = file_digest(WEBSITE_ROOT, relative, f"website input {relative}")
    result["config/quarto-base.yml"] = file_digest(
        WEBSITE_ROOT, "config/quarto-base.yml", "Quarto base config",
    )
    return result


def quarto_document(model: dict[str, Any]) -> dict[str, Any]:
    base = load_yaml(QUARTO_BASE_PATH)
    project = require_mapping(base.get("project"), "Quarto project")
    site_render = require_string_list(
        require_mapping(model["output"].get("site_sources"), "site_sources").get("render"),
        "site render targets",
    )
    project["output-dir"] = "_site"
    project["render"] = [*site_render, *[module["chapter"]["source"] for module in model["modules"]]]
    return base


def assemble_project(model: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    ensure_work_root()
    safe_remove_tree(PROJECT_ROOT)
    PROJECT_ROOT.mkdir(parents=True)

    site_sources = require_mapping(model["output"].get("site_sources"), "site_sources")
    website_files = [
        *require_string_list(site_sources.get("render"), "site render targets"),
        *require_string_list(site_sources.get("assets"), "site assets"),
        "styles.scss",
    ]
    website_hashes = current_website_input_hashes(model)
    staged_hashes: dict[str, str] = {}
    for relative in website_files:
        source = checked_file(WEBSITE_ROOT / "src", relative, f"website source {relative}")
        data = canonical_bytes(relative, source.read_bytes())
        atomic_write(PROJECT_ROOT / Path(*PurePosixPath(relative).parts), data)
        if website_hashes[f"src/{relative}"] != sha256_bytes(data):
            raise PublicationError(f"Website source changed during snapshot: {relative}")
        staged_hashes[relative] = sha256_bytes(data)

    manifest = manifest_document(model)
    for relative in manifest["material_inputs"]:
        data = copy_snapshot(model["materials_root"], relative)
        if sha256_bytes(data) != manifest["material_inputs"][relative]:
            raise PublicationError(f"Material changed during snapshot capture: {relative}")
        atomic_write(PROJECT_ROOT / Path(*PurePosixPath(relative).parts), data)
        staged_hashes[relative] = sha256_bytes(data)

    legal = [
        "CITATION.cff", "LICENSE", "NOTICE",
        "LICENSES/CC-BY-4.0.txt", "LICENSES/CC-BY-SA-3.0.txt",
        "LICENSES/CC0-1.0.txt", "LICENSES/MIT.txt",
    ]
    for relative in legal:
        data = copy_snapshot(WEBSITE_ROOT, relative)
        atomic_write(PROJECT_ROOT / Path(*PurePosixPath(relative).parts), data)
        if website_hashes[relative] != sha256_bytes(data):
            raise PublicationError(f"Website legal input changed during snapshot: {relative}")
        staged_hashes[relative] = sha256_bytes(data)

    for relative, data in public_fragments(model).items():
        atomic_write(PROJECT_ROOT / Path(*PurePosixPath(relative).parts), data)
        staged_hashes[relative] = sha256_bytes(data)
    quarto = yaml_bytes(quarto_document(model), "Generated release-specific Quarto project.")
    atomic_write(PROJECT_ROOT / "_quarto.yml", quarto)
    staged_hashes["_quarto.yml"] = sha256_bytes(quarto)
    return website_hashes, staged_hashes


def verify_staged_inputs(staged_hashes: dict[str, str]) -> None:
    current_paths: set[str] = set()
    for relative, expected in staged_hashes.items():
        path = checked_file(PROJECT_ROOT, relative, f"staged input {relative}")
        actual = sha256_bytes(canonical_bytes(relative, path.read_bytes()))
        if actual != expected:
            raise PublicationError(
                f"Staged input was modified during rendering: {relative}\n"
                f"  expected: {expected}\n  current:  {actual}"
            )
        current_paths.add(relative)
    if current_paths != set(staged_hashes):
        raise PublicationError("Staged input inventory changed during rendering")


def quarto_executable(model: dict[str, Any], explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    environment = os.environ.get("QMSBR_QUARTO")
    if environment:
        candidates.append(Path(environment))
    executable = "quarto.exe" if os.name == "nt" else "quarto"
    managed = WORK_ROOT / "tools" / f"quarto-{model['quarto_version']}" / "bin" / executable
    candidates.append(managed)
    system = shutil.which("quarto")
    if system:
        candidates.append(Path(system))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if candidate == managed:
            candidate = checked_file(
                WORK_ROOT,
                f"tools/quarto-{model['quarto_version']}/bin/{executable}",
                "managed Quarto executable",
            )
        elif is_link_or_junction(candidate):
            raise PublicationError(f"Quarto executable must not be a link: {candidate}")
        result = subprocess.run(
            [str(candidate), "--version"], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == model["quarto_version"]:
            return candidate.resolve()
    raise PublicationError(
        f"Quarto {model['quarto_version']} is required. Run "
        "`python tools/manage.py bootstrap-quarto` or pass --quarto."
    )


def run_quarto(model: dict[str, Any], executable: Path) -> None:
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = str(model["source_date_epoch"])
    environment["RENV_PROJECT"] = str(model["materials_root"])
    environment["RENV_CONFIG_AUTO_SNAPSHOT"] = "FALSE"
    command = [str(executable), "render", ".", "--to", "html", "--no-cache"]
    print("Rendering the four approved chapters and five site pages...")
    result = subprocess.run(command, cwd=PROJECT_ROOT, env=environment, check=False)
    if result.returncode:
        raise PublicationError(f"Quarto render failed with exit code {result.returncode}")


def check_r_environment(model: dict[str, Any]) -> None:
    rscript = shutil.which("Rscript")
    if not rscript:
        raise PublicationError("Rscript is required to validate the approved render environment")
    environment = os.environ.copy()
    environment["QMSBR_RENV_PROJECT"] = str(model["materials_root"])
    expression = (
        "project <- Sys.getenv('QMSBR_RENV_PROJECT'); "
        "invisible(capture.output(status <- renv::status(project = project))); "
        "cat(paste(R.version$major, R.version$minor, sep = '.')); "
        "if (!isTRUE(status$synchronized)) quit(status = 42L)"
    )
    result = subprocess.run(
        [rscript, "--vanilla", "-e", expression], env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    actual = result.stdout.strip()
    if result.returncode or actual != model["r_version"]:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        raise PublicationError(
            "The R/renv environment does not match the approved lock state:\n"
            f"  expected R: {model['r_version']}\n  observed: {actual or 'unknown'}\n"
            f"  detail: {detail}"
        )
    print(f"R/renv environment OK: R {actual}, lockfile synchronized.")


def git_state(root: Path) -> tuple[str | None, bool]:
    if not (root / ".git").exists():
        return None, True
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if revision.returncode:
        return None, True
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if status.returncode:
        raise PublicationError(status.stderr.strip())
    return revision.stdout.strip(), bool(status.stdout.strip())


def release_specification(model: dict[str, Any], release_id: str | None) -> dict[str, Any]:
    if release_id is None:
        identifier = "preview"
        return {
            "release_id": identifier,
            "planned_release_id": model["release_id"],
            "release_tag": None,
            "mode": "nondeployable-preview",
            "nondeployable": True,
            "checksum_name": f"SHA256SUMS-{identifier}.txt",
            "built_at_utc": None,
        }
    if release_id != model["release_id"] or not re.fullmatch(
        r"[0-9]{4}\.[0-9]+(?:\.[0-9]+)?", release_id,
    ):
        raise PublicationError(
            f"Production release must exactly match the approved ID {model['release_id']}"
        )
    return {
        "release_id": release_id,
        "planned_release_id": model["release_id"],
        "release_tag": f"v{release_id}",
        "mode": "production",
        "nondeployable": False,
        "checksum_name": f"SHA256SUMS-{release_id}.txt",
        "built_at_utc": datetime.fromtimestamp(
            model["source_date_epoch"], tz=UTC,
        ).isoformat().replace("+00:00", "Z"),
    }


def resolved_required_outputs(model: dict[str, Any], release: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for raw in require_string_list(model["output"].get("required_outputs"), "required_outputs"):
        relative = normalize_relative(
            raw.replace("{release_id}", str(release["release_id"])),
            "resolved required output",
        )
        if "{" in relative or "}" in relative:
            raise PublicationError(f"Unknown placeholder in required output: {raw}")
        result.append(relative)
    if len({path.casefold() for path in result}) != len(result):
        raise PublicationError("Resolved required outputs contain duplicate paths")
    if release["checksum_name"] not in result:
        raise PublicationError("Resolved required outputs omit the release checksum index")
    return result


def validate_production_gate(model: dict[str, Any], release: dict[str, Any]) -> None:
    required_environment = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "Jinsong-Chen/QMSBR",
        "GITHUB_REF": "refs/heads/main",
        "QMSBR_PUBLICATION_APPROVED": "true",
    }
    for name, expected in required_environment.items():
        actual = os.environ.get(name, "")
        if actual.casefold() != expected.casefold():
            raise PublicationError(
                f"Production release gate rejected {name}; expected {expected!r}"
            )
    expected_materials = os.environ.get("QMSBR_EXPECTED_MATERIALS_SHA", "").lower()
    expected_website = os.environ.get("QMSBR_EXPECTED_WEBSITE_SHA", "").lower()
    github_sha = os.environ.get("GITHUB_SHA", "").lower()
    for name, value in (
        ("QMSBR_EXPECTED_MATERIALS_SHA", expected_materials),
        ("QMSBR_EXPECTED_WEBSITE_SHA", expected_website),
        ("GITHUB_SHA", github_sha),
    ):
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise PublicationError(f"Production release gate requires a full SHA in {name}")
    if expected_website != github_sha:
        raise PublicationError("Requested website SHA differs from the workflow commit")
    materials_revision, materials_dirty = git_state(model["materials_root"])
    website_revision, website_dirty = git_state(WEBSITE_ROOT)
    if materials_revision != expected_materials or materials_dirty:
        raise PublicationError("Private materials checkout is not the requested clean commit")
    if website_revision != expected_website or website_dirty:
        raise PublicationError("Public website checkout is not the requested clean commit")
    if release["release_id"] != model["release_id"] or release["nondeployable"]:
        raise PublicationError("Production release specification is not approved")


def enumerate_ordinary_files(root: Path, owner: str) -> list[Path]:
    if not root.is_dir() or is_link_or_junction(root):
        raise PublicationError(f"{owner} is absent, not a directory, or linked: {root}")
    pending = [root]
    discovered: list[Path] = []
    while pending:
        directory = pending.pop()
        if is_link_or_junction(directory):
            raise PublicationError(f"Linked directory is forbidden in {owner}: {directory}")
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                if is_link_or_junction(path):
                    raise PublicationError(
                        f"Linked entry is forbidden in {owner}: {path.relative_to(root)}"
                    )
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    discovered.append(path)
                else:
                    raise PublicationError(
                        f"Unsupported entry in {owner}: {path.relative_to(root)}"
                    )
    return sorted(
        discovered,
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    )


def safe_output_destination(root: Path, relative: str) -> Path:
    """Resolve an output destination without following renderer-created links."""
    relative = normalize_relative(relative, "public output destination")
    verify_work_descendant_directory(root, "public output root")
    if not root.is_dir() or is_link_or_junction(root):
        raise PublicationError(f"Public output root must be an ordinary directory: {root}")
    resolved_root = root.resolve(strict=True)
    path = PurePosixPath(relative)
    current = root
    for part in path.parts[:-1]:
        current = current / part
        if current.exists():
            if is_link_or_junction(current) or not current.is_dir():
                raise PublicationError(
                    f"Public output parent must be an ordinary directory: {current}"
                )
        else:
            current.mkdir()
        try:
            current.resolve(strict=True).relative_to(resolved_root)
        except ValueError as exc:
            raise PublicationError(f"Public output destination escapes its root: {relative}") from exc
    destination = current / path.name
    if destination.exists() and (
        is_link_or_junction(destination) or not destination.is_file()
    ):
        raise PublicationError(f"Public output destination is not an ordinary file: {relative}")
    return destination


def add_public_resources(
    model: dict[str, Any], website_hashes: dict[str, str], release: dict[str, Any],
) -> None:
    output = PROJECT_ROOT / "_site"
    verify_work_descendant_directory(output, "renderer-created site output")
    enumerate_ordinary_files(output, "renderer-created site output")
    manifest = manifest_document(model)
    for relative in manifest["copied_resources"]:
        source = checked_file(PROJECT_ROOT, relative, f"staged public PDF {relative}")
        staged_digest = sha256_bytes(source.read_bytes())
        if staged_digest != model["approved_binaries"][relative]:
            raise PublicationError(f"Staged approved PDF changed during rendering: {relative}")
        destination = safe_output_destination(output, relative)
        atomic_write(destination, source.read_bytes())
    for relative in (
        "CITATION.cff", "LICENSE", "NOTICE", "LICENSES/CC-BY-4.0.txt",
        "LICENSES/CC-BY-SA-3.0.txt", "LICENSES/CC0-1.0.txt", "LICENSES/MIT.txt",
        "assets/favicon.svg", "assets/social-preview.png",
    ):
        source = checked_file(PROJECT_ROOT, relative, f"staged public resource {relative}")
        destination = safe_output_destination(output, relative)
        atomic_write(destination, source.read_bytes())
    atomic_write(safe_output_destination(output, ".nojekyll"), b"")

    pdf_paths = sorted(manifest["copied_resources"], key=str.casefold)
    checksum_lines = [
        f"{sha256_bytes((output / Path(*PurePosixPath(path).parts)).read_bytes())}  {path}"
        for path in pdf_paths
    ]
    checksum_name = str(release["checksum_name"])
    atomic_write(
        safe_output_destination(output, checksum_name),
        ("\n".join(checksum_lines) + "\n").encode("utf-8"),
    )

    materials_revision, materials_dirty = git_state(model["materials_root"])
    website_revision, website_dirty = git_state(WEBSITE_ROOT)
    artifact_checksums = {
        path: sha256_bytes((output / Path(*PurePosixPath(path).parts)).read_bytes())
        for path in pdf_paths
    }
    output_inventory = {
        path.relative_to(output).as_posix(): sha256_bytes(path.read_bytes())
        for path in enumerate_ordinary_files(output, "assembled site output")
        if path.name != "release.json"
    }
    inventory_payload = "".join(
        f"{path}\t{digest}\n" for path, digest in output_inventory.items()
    ).encode("utf-8")
    release_record = {
        "schema_version": 1,
        "release_id": release["release_id"],
        "planned_release_id": release["planned_release_id"],
        "release_tag": release["release_tag"],
        "mode": release["mode"],
        "nondeployable": release["nondeployable"],
        "built_at_utc": release["built_at_utc"] or datetime.now(tz=UTC).isoformat().replace(
            "+00:00", "Z",
        ),
        "materials_commit": materials_revision,
        "materials_dirty": materials_dirty,
        "website_commit": website_revision,
        "website_dirty": website_dirty,
        "quarto_version": model["quarto_version"],
        "r_version": model["r_version"],
        "python_version": platform.python_version(),
        "pyyaml_version": PY_YAML_VERSION,
        "publication_manifest_sha256": sha256_bytes(
            yaml_bytes(manifest, "Generated by website/tools/manage.py; do not edit by hand."),
        ),
        "website_inputs": website_hashes,
        "output_inventory": output_inventory,
        "output_inventory_sha256": sha256_bytes(inventory_payload),
        "artifact_checksums": artifact_checksums,
        "modules": model["module_ids"],
        "classroom_note_examples": model["note_ids"],
        "supplements": [],
    }
    atomic_write(
        safe_output_destination(output, "release.json"),
        (json.dumps(release_record, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
    )
    enumerate_ordinary_files(output, "assembled site output")


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value and name in {"href", "src"}:
                self.links.append(value)


def check_links(site: Path) -> None:
    failures: list[str] = []
    allowed_nonnetwork_schemes = {"data", "mailto", "tel"}

    def forbidden_network_target(parsed: Any) -> str | None:
        if parsed.username is not None or parsed.password is not None:
            return "credentials in URL"
        try:
            hostname = parsed.hostname
        except ValueError:
            return "invalid network host"
        if not hostname:
            return "missing network host"
        folded = hostname.rstrip(".").casefold()
        if folded == "localhost" or folded.endswith(".localhost"):
            return "local or unqualified network host"
        try:
            address = ipaddress.ip_address(folded)
        except ValueError:
            if "." not in folded:
                return "local or unqualified network host"
            return None
        if any((
            address.is_private, address.is_loopback, address.is_link_local,
            address.is_multicast, address.is_reserved, address.is_unspecified,
        )):
            return "non-public network address"
        return None

    for html_path in site.rglob("*.html"):
        parser = LinkCollector()
        parser.feed(html_path.read_text(encoding="utf-8", errors="replace"))
        for raw in parser.links:
            if raw.startswith("#"):
                continue
            parsed = urlsplit(raw)
            scheme = parsed.scheme.casefold()
            if scheme:
                if scheme in allowed_nonnetwork_schemes:
                    continue
                if scheme in {"http", "https"}:
                    reason = forbidden_network_target(parsed)
                    if reason is None:
                        continue
                    failures.append(
                        f"{html_path.relative_to(site)} -> {raw} ({reason})"
                    )
                    continue
                failures.append(
                    f"{html_path.relative_to(site)} -> {raw} (forbidden or unknown URI scheme)"
                )
                continue
            if parsed.netloc:
                reason = forbidden_network_target(parsed)
                if reason is not None:
                    failures.append(
                        f"{html_path.relative_to(site)} -> {raw} ({reason})"
                    )
                continue
            path_text = unquote(parsed.path)
            if not path_text:
                continue
            stripped = path_text.lstrip("/")
            if (
                "\\" in path_text
                or stripped.casefold().startswith("file:")
                or re.match(r"^[A-Za-z]:", stripped)
            ):
                failures.append(
                    f"{html_path.relative_to(site)} -> {raw} (local filesystem path)"
                )
                continue
            target = site / path_text.lstrip("/") if path_text.startswith("/") else html_path.parent / path_text
            try:
                resolved = target.resolve()
                resolved.relative_to(site.resolve())
            except ValueError:
                failures.append(f"{html_path.relative_to(site)} -> {raw} (escapes site)")
                continue
            if resolved.is_dir():
                resolved = resolved / "index.html"
            if not resolved.exists():
                failures.append(f"{html_path.relative_to(site)} -> {raw}")
    if failures:
        preview = "\n".join(f"  {item}" for item in failures[:30])
        raise PublicationError(f"Broken internal links ({len(failures)}):\n{preview}")


def validate_output(
    site: Path, model: dict[str, Any], release: dict[str, Any] | None = None,
) -> None:
    release = release or release_specification(model, None)
    try:
        site.absolute().relative_to(WORK_ROOT.absolute())
    except ValueError:
        pass
    else:
        verify_work_descendant_directory(site, "rendered site output")
    policy = model["output"]
    discovered = enumerate_ordinary_files(site, "rendered site output")
    files = sorted((path.relative_to(site).as_posix() for path in discovered), key=str.casefold)
    folded = [path.casefold() for path in files]
    if len(folded) != len(set(folded)):
        raise PublicationError("Rendered output has case-colliding paths")
    required = set(resolved_required_outputs(model, release))
    generated_assets = set(require_string_list(
        policy.get("generated_chapter_assets"), "generated_chapter_assets",
    ))
    generated_runtime = set(require_string_list(
        policy.get("generated_runtime_files"), "generated_runtime_files",
    ))
    allowed = required | generated_assets | generated_runtime
    actual = set(files)
    missing = sorted(allowed - actual, key=str.casefold)
    unexpected = sorted(actual - allowed, key=str.casefold)
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected: " + ", ".join(unexpected))
        raise PublicationError("Exact deployed inventory failed; " + "; ".join(details))

    forbidden_roots = {item.casefold() for item in require_string_list(
        policy.get("forbidden_output_roots"), "forbidden_output_roots",
    )}
    forbidden_extensions = {item.casefold() for item in require_string_list(
        policy.get("forbidden_output_extensions"), "forbidden_output_extensions",
    )}
    for relative in files:
        path = PurePosixPath(relative)
        if path.parts[0].casefold() in forbidden_roots:
            raise PublicationError(f"Forbidden output root: {relative}")
        if path.suffix.casefold() in forbidden_extensions:
            raise PublicationError(f"Forbidden raw file in deployed output: {relative}")

    chapter_html = {path for path in files if re.fullmatch(r"chapters/chapter_[0-9]+\.html", path)}
    expected_html = {
        str(PurePosixPath(module["chapter"]["source"]).with_suffix(".html"))
        for module in model["modules"]
    }
    if chapter_html != expected_html:
        raise PublicationError("Rendered chapter HTML inventory is not exactly Chapters 01–04")
    pdfs = {
        path for path in files if PurePosixPath(path).suffix.casefold() == ".pdf"
    }
    if pdfs != set(model["approved_binaries"]):
        raise PublicationError("Public PDF inventory differs from the five approved PDFs")
    for relative, approved in model["approved_binaries"].items():
        current = sha256_bytes(
            (site / Path(*PurePosixPath(relative).parts)).read_bytes()
        )
        if current != approved:
            raise PublicationError(f"Public PDF bytes differ from approval: {relative}")
    for relative, approved in model["approved_rendered_assets"].items():
        current = sha256_bytes(
            (site / Path(*PurePosixPath(relative).parts)).read_bytes()
        )
        if current != approved:
            raise PublicationError(f"Rendered chapter asset differs from approval: {relative}")

    pdf_paths = sorted(model["approved_binaries"], key=str.casefold)
    expected_checksum = "\n".join(
        f"{model['approved_binaries'][path]}  {path}" for path in pdf_paths
    ) + "\n"
    checksum_path = site / str(release["checksum_name"])
    if checksum_path.read_text(encoding="utf-8") != expected_checksum:
        raise PublicationError("Release checksum index does not match the approved PDFs")

    try:
        release_record = json.loads((site / "release.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicationError(f"Invalid release.json: {exc}") from exc
    release_record = require_mapping(release_record, "release.json")
    expected_manifest_hash = sha256_bytes(yaml_bytes(
        manifest_document(model),
        "Generated by website/tools/manage.py; do not edit by hand.",
    ))
    expected_artifacts = {
        path: model["approved_binaries"][path] for path in pdf_paths
    }
    expected_inventory = {
        path: sha256_bytes((site / Path(*PurePosixPath(path).parts)).read_bytes())
        for path in files if path != "release.json"
    }
    expected_inventory_payload = "".join(
        f"{path}\t{digest}\n" for path, digest in expected_inventory.items()
    ).encode("utf-8")
    expected_release_values = {
        "schema_version": 1,
        "release_id": release["release_id"],
        "planned_release_id": release["planned_release_id"],
        "release_tag": release["release_tag"],
        "mode": release["mode"],
        "nondeployable": release["nondeployable"],
        "quarto_version": model["quarto_version"],
        "r_version": model["r_version"],
        "pyyaml_version": PY_YAML_VERSION,
        "publication_manifest_sha256": expected_manifest_hash,
        "website_inputs": current_website_input_hashes(model),
        "output_inventory": expected_inventory,
        "output_inventory_sha256": sha256_bytes(expected_inventory_payload),
        "artifact_checksums": expected_artifacts,
        "modules": model["module_ids"],
        "classroom_note_examples": model["note_ids"],
        "supplements": [],
    }
    variable_release_keys = {
        "built_at_utc", "materials_commit", "materials_dirty",
        "website_commit", "website_dirty", "python_version",
    }
    expected_release_keys = set(expected_release_values) | variable_release_keys
    if set(release_record) != expected_release_keys:
        missing_keys = sorted(expected_release_keys - set(release_record))
        unexpected_keys = sorted(set(release_record) - expected_release_keys)
        details = []
        if missing_keys:
            details.append("missing: " + ", ".join(missing_keys))
        if unexpected_keys:
            details.append("unexpected: " + ", ".join(unexpected_keys))
        raise PublicationError(
            "release.json has a noncanonical top-level schema; " + "; ".join(details)
        )
    for key, expected in expected_release_values.items():
        if release_record.get(key) != expected:
            raise PublicationError(f"release.json has stale or invalid field: {key}")
    if release_record["python_version"] != platform.python_version():
        raise PublicationError("release.json has a stale or invalid python_version")
    try:
        datetime.fromisoformat(str(release_record.get("built_at_utc", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublicationError("release.json has an invalid built_at_utc") from exc
    if release["built_at_utc"] is not None and release_record["built_at_utc"] != release["built_at_utc"]:
        raise PublicationError("Production release.json has a non-reproducible built_at_utc")
    materials_revision, materials_dirty = git_state(model["materials_root"])
    website_revision, website_dirty = git_state(WEBSITE_ROOT)
    current_provenance = {
        "materials_commit": materials_revision,
        "materials_dirty": materials_dirty,
        "website_commit": website_revision,
        "website_dirty": website_dirty,
    }
    for key, expected in current_provenance.items():
        if release_record[key] != expected:
            raise PublicationError(f"release.json has stale provenance: {key}")

    for relative in (
        "CITATION.cff", "LICENSE", "NOTICE", "LICENSES/CC-BY-4.0.txt",
        "LICENSES/CC-BY-SA-3.0.txt", "LICENSES/CC0-1.0.txt", "LICENSES/MIT.txt",
    ):
        expected = copy_snapshot(WEBSITE_ROOT, relative)
        current = (site / Path(*PurePosixPath(relative).parts)).read_bytes()
        if current != expected:
            raise PublicationError(f"Deployed website resource is stale: {relative}")
    for relative in ("assets/favicon.svg", "assets/social-preview.png"):
        expected = copy_snapshot(WEBSITE_ROOT / "src", relative)
        current = (site / Path(*PurePosixPath(relative).parts)).read_bytes()
        if current != expected:
            raise PublicationError(f"Deployed website resource is stale: {relative}")

    leak_needles = {"publication-legacy.yml"}
    for local_root in (model["materials_root"], UMBRELLA_ROOT, WEBSITE_ROOT):
        windows = str(local_root)
        posix = windows.replace("\\", "/")
        leak_needles.update({windows.casefold(), posix.casefold()})
    for relative in files:
        if PurePosixPath(relative).suffix.casefold() not in {
            "", ".cff", ".css", ".html", ".js", ".json", ".map", ".svg", ".txt", ".xml",
        }:
            continue
        text = (site / Path(*PurePosixPath(relative).parts)).read_text(
            encoding="utf-8", errors="replace",
        ).casefold()
        decoded = unquote(unquote(text))
        found = [
            needle for needle in leak_needles
            if needle and (needle in text or needle in decoded)
        ]
        if found:
            raise PublicationError(f"Private render input leaked into output text: {relative}")
    check_links(site)
    print(f"Rendered output OK: {len(files)} files; four chapters, five PDFs, no supplements.")


def promote_site(candidate: Path) -> None:
    verify_work_descendant_directory(candidate, "site promotion candidate")
    backup = WORK_ROOT / "site-previous"
    safe_remove_tree(backup)
    if SITE_ROOT.exists():
        if is_link_or_junction(SITE_ROOT) or not SITE_ROOT.is_dir():
            raise PublicationError(f"Existing site output must be an ordinary directory: {SITE_ROOT}")
        os.replace(SITE_ROOT, backup)
    try:
        os.replace(candidate, SITE_ROOT)
    except BaseException:
        if backup.exists() and not SITE_ROOT.exists():
            os.replace(backup, SITE_ROOT)
        raise
    safe_remove_tree(backup)


def verify_live_model(model: dict[str, Any]) -> None:
    fresh = load_model(model["materials_root"])
    if manifest_document(fresh) != manifest_document(model):
        raise PublicationError("Publication catalogue, approvals, or output policy changed during build")


def build_site(
    materials_root: Path, *, explicit_quarto: str | None,
    release_id: str | None = None,
) -> None:
    ensure_work_root()
    validate_boundaries(materials_root)
    model = load_model(materials_root)
    sync_manifest_model(model, check=True)
    release = release_specification(model, release_id)
    if release_id is not None:
        validate_production_gate(model, release)
    check_r_environment(model)
    executable = quarto_executable(model, explicit_quarto)
    website_hashes, staged_hashes = assemble_project(model)
    try:
        run_quarto(model, executable)
        verify_staged_inputs(staged_hashes)
        verify_live_model(model)
        if release_id is not None:
            validate_production_gate(model, release)
        add_public_resources(model, website_hashes, release)
        candidate = PROJECT_ROOT / "_site"
        validate_output(candidate, model, release)
        verify_staged_inputs(staged_hashes)
        verify_live_model(model)
        if current_website_input_hashes(model) != website_hashes:
            raise PublicationError("Website source inputs changed during build")
        validate_output(candidate, model, release)
        promote_site(candidate)
    finally:
        safe_remove_tree(PROJECT_ROOT)
    print(f"Built validated site at {SITE_ROOT}")


def bootstrap_quarto(materials_root: Path) -> None:
    model = load_model(materials_root)
    if os.name != "nt" or model["quarto_version"] != "1.10.18":
        raise PublicationError("The bundled bootstrap currently supports Windows Quarto 1.10.18 only")
    ensure_work_root()
    tools_directory = ensure_work_directory("tools")
    target = tools_directory / "quarto-1.10.18"
    executable = target / "bin/quarto.exe"
    if executable.is_file():
        executable = checked_file(
            WORK_ROOT, "tools/quarto-1.10.18/bin/quarto.exe",
            "managed Quarto executable",
        )
        found = subprocess.run(
            [str(executable), "--version"], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, check=False,
        )
        if found.returncode == 0 and found.stdout.strip() == "1.10.18":
            print(f"Quarto 1.10.18 is already available at {executable}")
            return
    downloads = ensure_work_directory("downloads")
    archive = downloads / "quarto-1.10.18-win.zip"
    if archive.exists():
        if is_link_or_junction(archive) or not archive.is_file():
            raise PublicationError(f"Quarto download target must be an ordinary file: {archive}")
        archive.unlink()
    request = Request(QUARTO_WINDOWS_URL, headers={"User-Agent": "QMSBR-publisher/1"})
    digest = hashlib.sha256()
    size = 0
    print("Downloading official Quarto 1.10.18 portable archive...")
    with urlopen(request, timeout=60) as response, archive.open("wb") as stream:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            stream.write(block)
            digest.update(block)
            size += len(block)
    if size != QUARTO_WINDOWS_SIZE or digest.hexdigest() != QUARTO_WINDOWS_SHA256:
        archive.unlink(missing_ok=True)
        raise PublicationError("Downloaded Quarto archive failed its pinned size/SHA-256 check")
    staging = tools_directory / "quarto-1.10.18-staging"
    safe_remove_tree(staging)
    staging.mkdir()
    try:
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                path = PurePosixPath(member.filename)
                mode = (member.external_attr >> 16) & 0o170000
                if path.is_absolute() or ".." in path.parts or mode == stat.S_IFLNK:
                    raise PublicationError(f"Unsafe path in Quarto archive: {member.filename}")
            bundle.extractall(staging)
        staged_executable = staging / "bin/quarto.exe"
        result = subprocess.run(
            [str(staged_executable), "--version"], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, check=False,
        )
        if result.returncode or result.stdout.strip() != "1.10.18":
            raise PublicationError("Extracted Quarto executable failed its version check")
        signature_environment = os.environ.copy()
        signature_environment["QMSBR_QUARTO_SIGNATURE_TARGET"] = str(staged_executable)
        signature = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "$signature = Get-AuthenticodeSignature -LiteralPath "
                "$env:QMSBR_QUARTO_SIGNATURE_TARGET; $signature.Status.ToString()",
            ],
            env=signature_environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        signature_status = signature.stdout.strip()
        if signature.returncode == 0 and signature_status and signature_status != "Valid":
            raise PublicationError(
                f"Extracted quarto.exe has unexpected Authenticode status: {signature_status}"
            )
        if signature.returncode or not signature_status:
            print(
                "Warning: Windows could not load Authenticode verification; "
                "the pinned official archive size and SHA-256 were verified.",
                file=sys.stderr,
            )
        safe_remove_tree(target)
        os.replace(staging, target)
    finally:
        safe_remove_tree(staging)
        archive.unlink(missing_ok=True)
    print(f"Installed verified portable Quarto at {executable}")


def resolve_materials_root(value: str | None) -> Path:
    selected = value or os.environ.get("QMSBR_MATERIALS_ROOT")
    path = Path(selected) if selected else DEFAULT_MATERIALS_ROOT
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise PublicationError(f"Materials repository does not exist: {path}") from exc
    if not resolved.is_dir():
        raise PublicationError(f"Materials repository is not a directory: {resolved}")
    return resolved


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--materials-root", help="Private materials repository (default: ../materials)")
    result.add_argument("--quarto", help="Exact Quarto executable to use")
    subparsers = result.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync", help="Generate the exact private publication manifest")
    sync_parser.add_argument("--check", action="store_true", help="Fail instead of updating a stale manifest")
    check_parser = subparsers.add_parser("check", help="Validate hashes and repository boundaries")
    check_parser.add_argument("--site", action="store_true", help="Also validate the existing rendered site")
    subparsers.add_parser(
        "build", help="Assemble, render, validate, and promote a nondeployable local preview",
    )
    release_parser = subparsers.add_parser(
        "release-build", help="Build a production release inside the protected GitHub workflow",
    )
    release_parser.add_argument("--release", required=True, help="Exact approved release ID")
    subparsers.add_parser("bootstrap-quarto", help="Install the pinned portable Quarto under .qmsbr")
    serve_parser = subparsers.add_parser("serve", help="Serve the validated local output")
    serve_parser.add_argument("--port", type=int, default=8765)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        check_python_environment()
        materials_root = resolve_materials_root(args.materials_root)
        if args.command == "sync":
            sync_manifest(materials_root, check=args.check)
        elif args.command == "check":
            validate_boundaries(materials_root)
            model = load_model(materials_root)
            sync_manifest_model(model, check=True)
            check_r_environment(model)
            if args.site:
                validate_output(SITE_ROOT, model)
            print("Publication approvals and split-repository boundary are valid.")
        elif args.command == "build":
            build_site(materials_root, explicit_quarto=args.quarto)
        elif args.command == "release-build":
            build_site(
                materials_root, explicit_quarto=args.quarto,
                release_id=args.release,
            )
        elif args.command == "bootstrap-quarto":
            bootstrap_quarto(materials_root)
        elif args.command == "serve":
            model = load_model(materials_root)
            validate_output(SITE_ROOT, model)
            from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
            handler = lambda *values, **kwargs: SimpleHTTPRequestHandler(
                *values, directory=str(SITE_ROOT), **kwargs,
            )
            print(f"Serving {SITE_ROOT} at http://127.0.0.1:{args.port}/")
            ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()
        return 0
    except (PublicationError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
