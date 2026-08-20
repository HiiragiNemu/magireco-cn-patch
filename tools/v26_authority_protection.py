#!/usr/bin/env python3
"""Build and verify the v26 high-authority translation protection snapshot.

The snapshot is deliberately field based.  Most runtime dictionaries contain a
mixture of authority tiers, so locking an entire JSON file would also freeze
lower-authority text.  Each protected value is instead addressed by a stable
business key and field name.  The all-Wiki glossary is additionally protected
by a whole-file digest.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


AUDIT_REL = Path("magica/i18n_audit/release_v26_authority")
REVIEW_REL = AUDIT_REL / "machine_translation_review"
MASTER_REL = REVIEW_REL / "full_machine_translation_review.tsv"
SUMMARY_REL = REVIEW_REL / "summary.json"
PROTECTION_REL = AUDIT_REL / "protected_authority"
PROTECTED_TSV_REL = PROTECTION_REL / "protected_translation_fields.tsv"
MANIFEST_REL = PROTECTION_REL / "protection_manifest.json"
GLOSSARY_REL = Path("i18n/glossary.tsv")
PASS16_REL = Path("magica/i18n_audit/manual_cn_pass16")
PASS16_CHANGE_LOG_REL = PASS16_REL / "runtime_change_log.tsv"
PASS16_TRANSLATION_MAP_REL = PASS16_REL / "runtime_translation_map.tsv"
PASS19_REL = AUDIT_REL / "pass19_official_static_corrections.tsv"
VISIBLE_TERM_CLOSURE_REL = REVIEW_REL / "visible_term_closure_3136.tsv"

SCHEMA = "magireco-cn-v26-authority-protection/v4"
EXPECTED_MASTER_TOTAL = 3310
EXPECTED_MASTER_BUCKETS = {"official": 1912, "wiki": 1094, "new-root-human": 304}
EXPECTED_PASS16_APPLIED_FIELDS = 855
EXPECTED_PASS16_PROTECTED_FIELDS = 827
EXPECTED_PASS16_SUPERSEDED_FIELDS = 27
EXPECTED_PASS16_SUPERSEDED_SOURCE_TIERS = {
    "2_wiki_component": 1,
    "2_wiki_explicit_pair": 26,
}
EXPECTED_PASS16_ADDITIONS = 145
EXPECTED_TOTAL = 3455
EXPECTED_BUCKETS = {"official": 1959, "wiki": 1181, "new-root-human": 315}
EXPECTED_PASS19_CONTRACTS = 6
EXPECTED_PASS19_APPLIED_CHANGES = 11
EXPECTED_PASS19_FINAL_OCCURRENCES = 15
EXPECTED_TOTAL_WITH_PASS19 = 3466
EXPECTED_BUCKETS_WITH_PASS19 = {"official": 1965, "wiki": 1186, "new-root-human": 315}
EXPECTED_CANDIDATE_ONLY_METADATA = 1
EXPECTED_OFFLINE_AUTHORITY_OVERLAYS = 61
EXPECTED_VISIBLE_TERM_CLOSURE_ROWS = 3136

# Pass19 was applied while its preimage was still available.  These ordinals
# record which final ``after`` occurrences are the eleven actual replacements,
# as opposed to the four identical authority literals already present in the
# product files.  The mapping is deliberately explicit: guessing "first N"
# would misidentify P19-00004 and P19-00005 after the preimage is committed.
# Each selected occurrence is additionally bound to a value-independent local
# context anchor below, while the six source contracts continue to require the
# complete file-level before/after counts (0/15 in aggregate).
PASS19_APPLIED_OCCURRENCE_ORDINALS = {
    "P19-00001": (1,),
    "P19-00002": (1, 2),
    "P19-00003": (1, 2),
    "P19-00004": (2,),
    "P19-00005": (1, 2, 4),
    "P19-00006": (1, 2),
}
PASS19_ANCHOR_CONTEXT_CHARS = 48
EXPECTED_PASS16_ACTIONS = {
    "authority_preserved": 2,
    "official_same_record_alignment": 200,
    "punctuation_harmonization": 1,
    "replaced": 652,
}
EXPECTED_PASS16_TRANSLATION_TIERS = {
    "1_official_cn_dump_component": 30,
    "1_official_cn_dump_exact": 16,
    "1_official_cn_dump_same_record": 3,
    "2_wiki_component": 32,
    "2_wiki_exact_equivalent": 2,
    "2_wiki_explicit_pair": 56,
    "3_manual_translation": 1,
    "3_manual_verified": 8,
}
HELD_WIKI_IDENTITIES = {
    ("data/memoria.json", "BM-NR-001", "candidate_cn"),
    ("data/memoria.json", "BM-NR-002", "candidate_cn"),
    ("data/memoria.json", "BM-NR-003", "candidate_cn"),
}

PROTECTED_COLUMNS = [
    "protected_id",
    "master_record_id",
    "protection_origin",
    "authority_rank",
    "source_bucket",
    "source_tier",
    "scope",
    "file",
    "business_key_type",
    "business_key",
    "source_locator",
    "locator_sha256",
    "field",
    "protected_value",
    "value_sha256",
    "identity_sha256",
    "review_status",
    "authority_status",
    "evidence_path_or_key",
    "expected_count",
    "record_sha256",
]

# Keep this in sync with tools/build-v26-machine-review.py.  Only the protected
# runtime files are used here, but the complete map avoids an accidental fallback
# to line or array position if the protected set grows.
LIST_KEYS = {
    "arenaClassList": ("arenaClass", "id"),
    "cardList": ("cardId", "id"),
    "chapterList": ("chapterId", "id"),
    "charaList": ("id", "charaNo"),
    "charaMessageList": ("charaNo_messageId",),
    "doppelList": ("id",),
    "enemyList": ("enemyId", "id"),
    "eventList": ("eventId", "id"),
    "eventStoryList": ("storyIds",),
    "formationSheetList": ("formationSheetId", "id"),
    "giftList": ("id", "giftId"),
    "itemList": ("itemCode", "id", "itemId"),
    "live2dList": ("charaId_live2dId",),
    "patrolAreaList": ("patrolAreaId", "id"),
    "pieceList": ("pieceId", "id"),
    "sectionList": ("sectionId", "id"),
    "shopItemList": ("shopItemId", "id"),
}


class ProtectionError(RuntimeError):
    """Raised when a protected field, source tier, or manifest drifts."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_product_file_sha256(path: Path) -> str:
    """Hash UTF-8 product text in Git's LF form; keep binary byte-exact."""

    data = path.read_bytes()
    if b"\0" not in data:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=PROTECTED_COLUMNS,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def row_identity(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["file"], row["stable_key_or_line"], row["field"])


def candidate_only_metadata(row: dict[str, str]) -> bool:
    """Identify an authority *candidate* that is not a current product value.

    A machine-review record may document a high-authority replacement for a
    legacy extraction row while deliberately retaining the original blank
    candidate field.  Such rows are vital audit evidence, but protecting their
    empty ``current_cn`` would both freeze the wrong object and bypass the
    applied-product contract.  Applied static corrections are instead carried
    by the explicit Pass19 manifest below.
    """

    return (
        not row.get("current_cn", "")
        and row.get("source_bucket") == "official"
        and row.get("scope") == "frontend_i18n_input"
        and row.get("field") == "candidate_cn"
        and row.get("source_stage") == "migrated_frontend_input_exact_node_closure"
        and row.get("runtime_consumed") == "visible exact runtime node; offline candidate remains unselected"
    )


def offline_authority_overlay_metadata(row: dict[str, str]) -> bool:
    """Identify reviewed authority overlays for offline i18n maintenance rows.

    These records keep the old low-tier value in ``current_cn`` so the machine
    review remains a literal before/after comparison.  Their selected official
    replacement is stored in ``highest_authority_match`` / ``suggested_cn`` and
    is applied to the actual ``magica/`` product by the Pass20 correction
    manifest.  Treating the offline row itself as a protected product value
    would freeze the pre-replacement translation and create an unsupported
    business key, so it is deliberately excluded from the product protection
    set while its exact cohort size is fail-closed here.
    """

    return (
        row.get("scope", "")
        in {"frontend_i18n_input", "frontend_i18n_override", "frontend_i18n_fragment"}
        and row.get("field") == "candidate_cn"
        and row.get("authority_status") == "explicit-higher-authority-selected"
        and row.get("manual_review_status") == "authority-resolved"
        and row.get("runtime_consumed", "").startswith("false;")
        and bool(row.get("highest_authority_match", ""))
    )


def select_protected_master_rows(
    master: Iterable[dict[str, str]], *, enforce_contract: bool = True
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return protected rows and the three explicitly held Wiki candidates."""

    master_rows = list(master)
    candidate_only = [row for row in master_rows if candidate_only_metadata(row)]
    if len(candidate_only) != EXPECTED_CANDIDATE_ONLY_METADATA:
        raise ProtectionError(
            "candidate-only metadata contract drift: "
            f"{len(candidate_only)} != {EXPECTED_CANDIDATE_ONLY_METADATA}"
        )
    offline_overlays = [
        row for row in master_rows if offline_authority_overlay_metadata(row)
    ]
    if enforce_contract and len(offline_overlays) != EXPECTED_OFFLINE_AUTHORITY_OVERLAYS:
        raise ProtectionError(
            "offline authority-overlay contract drift: "
            f"{len(offline_overlays)} != {EXPECTED_OFFLINE_AUTHORITY_OVERLAYS}"
        )
    held = [row for row in master_rows if row_identity(row) in HELD_WIKI_IDENTITIES]
    held_identities = {row_identity(row) for row in held}
    if held_identities != HELD_WIKI_IDENTITIES:
        missing = sorted(HELD_WIKI_IDENTITIES - held_identities)
        extra = sorted(held_identities - HELD_WIKI_IDENTITIES)
        raise ProtectionError(f"held Wiki identity drift: missing={missing}, extra={extra}")
    for row in held:
        if row.get("source_bucket") != "wiki" or row.get("review_status") != "needs-review/root-translation-required":
            raise ProtectionError(
                f"held Wiki row unexpectedly closed or reclassified: {row_identity(row)}"
            )

    selected: list[dict[str, str]] = []
    for row in master_rows:
        bucket = row.get("source_bucket", "")
        identity = row_identity(row)
        if candidate_only_metadata(row) or offline_authority_overlay_metadata(row):
            continue
        if bucket == "official":
            selected.append(row)
        elif bucket == "wiki" and identity not in HELD_WIKI_IDENTITIES:
            selected.append(row)
        elif bucket == "new-root-human" and row.get("review_status") in {
            "authority-verified",
            "confirmed-human-verified",
        }:
            selected.append(row)

    identities = [row_identity(row) for row in selected]
    duplicates = [key for key, count in Counter(identities).items() if count != 1]
    if duplicates:
        raise ProtectionError(f"duplicate protected identities: {duplicates[:10]}")
    if any(not row.get("current_cn", "") for row in selected):
        raise ProtectionError("protected set contains an empty current_cn value")

    if enforce_contract:
        buckets = Counter(row["source_bucket"] for row in selected)
        if len(selected) != EXPECTED_MASTER_TOTAL or dict(buckets) != EXPECTED_MASTER_BUCKETS:
            raise ProtectionError(
                "protected selection count drift: "
                f"total={len(selected)} buckets={dict(sorted(buckets.items()))}; "
                f"expected total={EXPECTED_MASTER_TOTAL} buckets={EXPECTED_MASTER_BUCKETS}"
            )
    return selected, held


def runtime_business_key(root: Path, row: dict[str, str]) -> str:
    path = root / row["file"]
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    base = path.stem
    source_key = row["stable_key_or_line"]
    if isinstance(data, dict):
        if source_key not in data or not isinstance(data[source_key], dict):
            raise ProtectionError(f"runtime business key missing: {row['file']}#{source_key}")
        return source_key
    if not isinstance(data, list):
        raise ProtectionError(f"unsupported runtime root type: {row['file']}")
    index = {
        stable_key(base, obj): obj
        for obj in data
        if isinstance(obj, dict) and stable_key(base, obj)
    }
    if source_key in index:
        return source_key
    # Some Pass18 corrections recorded the list index as their source locator.
    # Convert it once into the real composite/stable ID and verify both the
    # field and value before accepting it as a protected business key.
    try:
        source_index = int(source_key)
        obj = data[source_index]
    except (ValueError, IndexError, TypeError):
        obj = None
    if isinstance(obj, dict):
        derived = stable_key(base, obj)
        if derived and obj.get(row["field"]) == row["current_cn"]:
            return derived
    raise ProtectionError(
        f"cannot derive stable runtime business key: {row['file']}#{source_key}/{row['field']}"
    )


def business_key(root: Path, row: dict[str, str]) -> tuple[str, str]:
    scope = row["scope"]
    if scope == "runtime_dictionary":
        return "runtime-stable-id", runtime_business_key(root, row)
    if scope == "offline_authority_support":
        return "source-term", row["original_text"]
    if scope == "native_engine_i18n":
        return "engine-source-literal", row["original_text"]
    if scope == "static_js_html":
        return "replaced-source-literal", row["original_text"]
    raise ProtectionError(f"unsupported protected scope: {scope}")


def authority_rank(row: dict[str, str]) -> str:
    if row["source_bucket"] == "official":
        return "1-official-cn"
    if row["source_bucket"] == "wiki":
        return "2-wiki"
    return "3-confirmed-human"


def canonical_record_payload(row: dict[str, str]) -> str:
    fields = [
        row["protection_origin"],
        row["source_bucket"],
        row["source_tier"],
        row["scope"],
        row["file"],
        row["business_key_type"],
        row["business_key"],
        row["source_locator"],
        row["locator_sha256"],
        row["field"],
        row["value_sha256"],
        row["review_status"],
        row["authority_status"],
        row["evidence_path_or_key"],
        row.get("expected_count", ""),
    ]
    return "\x1f".join(fields)


JS_STRING = r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')'''


def static_literal_candidates(
    path: Path, source_locator: str, field: str
) -> list[tuple[str, str]]:
    """Return ``(container-anchor-sha256, complete field literal)`` pairs."""

    match = re.fullmatch(r"line(\d+)", source_locator)
    if not match:
        raise ProtectionError(f"unsupported static source locator: {source_locator}")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    line_number = int(match.group(1))
    if line_number < 1 or line_number > len(lines):
        raise ProtectionError(f"static source locator is out of range: {path}#{source_locator}")
    line = lines[line_number - 1]
    field_pattern = re.compile(rf"{re.escape(field)}\s*:\s*{JS_STRING}")
    result: list[tuple[str, str]] = []
    # The protected static record is an object literal on one minified line.
    # Hashing the containing object with only the value replaced creates a
    # locator that remains stable when precisely that value is corrupted.
    for container in re.finditer(r"\{[^{}]*\}", line):
        body = container.group(0)
        for literal in field_pattern.finditer(body):
            canonical = body[: literal.start()] + f"{field}:<PROTECTED_VALUE>" + body[literal.end() :]
            result.append((sha256_text(canonical), literal.group(0)))
    return result


def protected_rows_from_master(
    master: Iterable[dict[str, str]], *, root: Path | None = None
) -> list[dict[str, str]]:
    selected, _held = select_protected_master_rows(master)
    result: list[dict[str, str]] = []
    for source in selected:
        if root is None:
            raise ProtectionError("root is required to build protected business keys")
        key_type, key = business_key(root, source)
        source_locator = source["stable_key_or_line"]
        locator_sha256 = ""
        if source["scope"] == "static_js_html":
            if root is None:
                raise ProtectionError("root is required to build a static protected locator")
            candidates = static_literal_candidates(root / source["file"], source_locator, source["field"])
            matching = [anchor for anchor, literal in candidates if literal == source["current_cn"]]
            if len(matching) != 1:
                raise ProtectionError(
                    f"static protected literal locator is ambiguous: {source['file']}#{source_locator}/{source['field']}"
                )
            locator_sha256 = matching[0]
        identity_payload = "\x1f".join(
            [source["file"], key_type, key, source["field"]]
        )
        item = {
            "protected_id": "",
            "master_record_id": source["record_id"],
            "protection_origin": "machine-review-master",
            "authority_rank": authority_rank(source),
            "source_bucket": source["source_bucket"],
            "source_tier": source["source_tier"],
            "scope": source["scope"],
            "file": source["file"],
            "business_key_type": key_type,
            "business_key": key,
            "source_locator": source_locator,
            "locator_sha256": locator_sha256,
            "field": source["field"],
            "protected_value": source["current_cn"],
            "value_sha256": sha256_text(source["current_cn"]),
            "identity_sha256": sha256_text(identity_payload),
            "review_status": source["review_status"],
            "authority_status": source["authority_status"],
            "evidence_path_or_key": source["evidence_path_or_key"],
            "record_sha256": "",
        }
        item["record_sha256"] = sha256_text(canonical_record_payload(item))
        result.append(item)

    result.sort(
        key=lambda row: (
            row["file"],
            row["business_key_type"],
            row["business_key"],
            row["field"],
            row["record_sha256"],
        )
    )
    for number, row in enumerate(result, 1):
        row["protected_id"] = f"AUTH-{number:05d}"
    return result


def pass16_source_bucket(source_tier: str) -> str:
    if source_tier.startswith("1_"):
        return "official"
    if source_tier.startswith("2_"):
        return "wiki"
    if source_tier.startswith("3_"):
        return "new-root-human"
    raise ProtectionError(f"unsupported Pass16 source tier: {source_tier}")


def pass16_runtime_location(
    root: Path, row: dict[str, str], *, allow_superseded: bool = False
) -> tuple[str, str, str, str]:
    """Resolve a Pass16 JSON pointer to a stable product business key."""

    dictionary = row["dictionary"]
    relative = Path("magica/js/libs") / dictionary
    path = root / relative
    if not path.is_file():
        raise ProtectionError(f"Pass16 runtime dictionary is missing: {relative.as_posix()}")
    parts = row["pointer"].strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise ProtectionError(
            f"unsupported Pass16 runtime pointer: {dictionary}#{row['pointer']}"
        )
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    container, field = parts
    if isinstance(data, list):
        try:
            obj = data[int(container)]
        except (ValueError, IndexError, TypeError) as exc:
            raise ProtectionError(
                f"Pass16 runtime pointer is out of range: {dictionary}#{row['pointer']}"
            ) from exc
        if not isinstance(obj, dict):
            raise ProtectionError(
                f"Pass16 runtime pointer does not address an object: {dictionary}#{row['pointer']}"
            )
        key = stable_key(path.stem, obj)
        if not key:
            raise ProtectionError(
                f"Pass16 runtime object has no stable business key: {dictionary}#{row['pointer']}"
            )
    elif isinstance(data, dict):
        if container not in data or not isinstance(data[container], dict):
            raise ProtectionError(
                f"Pass16 runtime key is missing: {dictionary}#{row['pointer']}"
            )
        obj = data[container]
        key = container
    else:
        raise ProtectionError(f"unsupported Pass16 runtime root type: {dictionary}")
    if field not in obj or not isinstance(obj[field], str):
        raise ProtectionError(
            f"Pass16 runtime field is missing or non-text: {dictionary}#{row['pointer']}"
        )
    if obj[field] != row["final_cn"] and not allow_superseded:
        raise ProtectionError(
            f"Pass16 protected product value drift: {dictionary}#{key}/{field}"
        )
    return relative.as_posix(), key, field, obj[field]


def visible_term_closure_index(root: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    """Load the exact product-addressed visible-term closure contract.

    The closure includes official, Wiki, and root-reviewed terminology rows.
    This helper does not promote the latter to authority.  It only gives the
    Pass16 merge an exact, fail-closed explanation for historical Wiki values
    that are no longer the current product bytes.
    """

    path = root / VISIBLE_TERM_CLOSURE_REL
    rows = read_tsv(path)
    required = {
        "closure_id",
        "path",
        "stable_key",
        "field",
        "before",
        "after",
        "source_tier",
        "review_status",
        "machine_translated",
        "current_product_cn",
        "inventory_component",
    }
    if len(rows) != EXPECTED_VISIBLE_TERM_CLOSURE_ROWS:
        raise ProtectionError(
            "visible-term closure row-count drift: "
            f"{len(rows)} != {EXPECTED_VISIBLE_TERM_CLOSURE_ROWS}"
        )
    if not rows or not required.issubset(rows[0]):
        raise ProtectionError("visible-term closure has missing required columns")
    result: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        identity = (row["path"], row["stable_key"], row["field"])
        if identity in result:
            raise ProtectionError(
                f"duplicate visible-term closure identity: {identity}"
            )
        result[identity] = row
    return result


def protected_rows_from_pass16(root: Path) -> list[dict[str, str]]:
    """Build the 827 still-current protected fields from Pass16.

    The translation map proves the 137 authority + 2 equivalence + 9 confirmed
    human type contract.  The change log expands those types to every concrete
    product occurrence and includes the separately recorded official-CN
    punctuation harmonization.  Twenty-seven historical Wiki-valued fields
    were later changed by the root-reviewed terminology closure.  Those exact
    supersessions are verified here, but are excluded rather than mislabeled
    as confirmed-human or frozen as high authority.
    """

    change_log = read_tsv(root / PASS16_CHANGE_LOG_REL)
    translation_map = read_tsv(root / PASS16_TRANSLATION_MAP_REL)
    actions = counts_by(change_log, "action")
    translation_tiers = counts_by(translation_map, "source_tier")
    if len(change_log) != EXPECTED_PASS16_APPLIED_FIELDS or actions != EXPECTED_PASS16_ACTIONS:
        raise ProtectionError(
            "Pass16 applied-field contract drift: "
            f"total={len(change_log)} actions={actions}; "
            f"expected total={EXPECTED_PASS16_APPLIED_FIELDS} actions={EXPECTED_PASS16_ACTIONS}"
        )
    if len(translation_map) != 148 or translation_tiers != EXPECTED_PASS16_TRANSLATION_TIERS:
        raise ProtectionError(
            "Pass16 translation-type contract drift: "
            f"total={len(translation_map)} tiers={translation_tiers}"
        )
    authority_replacements = sum(
        count
        for tier, count in translation_tiers.items()
        if tier.startswith("1_") or tier in {"2_wiki_component", "2_wiki_explicit_pair"}
    )
    equivalences = translation_tiers.get("2_wiki_exact_equivalent", 0)
    confirmed_human_map_types = translation_tiers.get("3_manual_verified", 0)
    excluded_unreviewed_types = translation_tiers.get("3_manual_translation", 0)
    confirmed_human_fields = sum(
        1
        for row in change_log
        if row["source_tier"] == "3_manual_verified"
    )
    punctuation_fields = sum(
        1 for row in change_log if row["action"] == "punctuation_harmonization"
    )
    if (
        authority_replacements,
        equivalences,
        confirmed_human_map_types,
        excluded_unreviewed_types,
        confirmed_human_fields,
        punctuation_fields,
    ) != (137, 2, 8, 1, 11, 1):
        raise ProtectionError(
            "Pass16 authority/manual type contract drift: "
            f"replacements={authority_replacements} equivalences={equivalences} "
            f"confirmed_map_types={confirmed_human_map_types} "
            f"excluded_unreviewed_types={excluded_unreviewed_types} "
            f"human_fields={confirmed_human_fields} "
            f"punctuation_fields={punctuation_fields}"
        )

    closure = visible_term_closure_index(root)
    result: list[dict[str, str]] = []
    superseded: list[dict[str, str]] = []
    for index, source in enumerate(change_log, 1):
        # `3_manual_translation` is a low-confidence candidate, not confirmed
        # human work.  In particular 永遠的刻 -> 永远之刻 remains reviewable
        # and must not be frozen as high-authority product text.
        if source["source_tier"] == "3_manual_translation":
            continue
        relative, key, field, value = pass16_runtime_location(
            root, source, allow_superseded=True
        )
        if value != source["final_cn"]:
            closure_row = closure.get((relative, key, field))
            if (
                closure_row is None
                or closure_row["before"] != source["final_cn"]
                or closure_row["after"] != value
                or closure_row["current_product_cn"] != value
                or closure_row["source_tier"]
                != "root-reviewed-official-cn-terminology"
                or closure_row["review_status"] != "root-reviewed-approved"
                or closure_row["machine_translated"] != "false"
                or closure_row["inventory_component"]
                != "runtime_visible_term_closure_root_reviewed"
            ):
                raise ProtectionError(
                    "Pass16 value drift is not an exact non-authority "
                    "visible-term supersession: "
                    f"{relative}#{key}/{field}"
                )
            superseded.append(source)
            continue
        bucket = pass16_source_bucket(source["source_tier"])
        rank = (
            "1-official-cn"
            if bucket == "official"
            else "2-wiki"
            if bucket == "wiki"
            else "3-confirmed-human"
        )
        identity_payload = "\x1f".join(
            [relative, "runtime-stable-id", key, field]
        )
        evidence = (
            f"{PASS16_CHANGE_LOG_REL.as_posix()}:{index + 1};"
            f"source_tier={source['source_tier']};"
            f"recorded_source_sha256={sha256_text(source['source_path'])}"
        )
        item = {
            "protected_id": "",
            "master_record_id": f"PASS16-{index:05d}",
            "protection_origin": "pass16-runtime-change-log",
            "authority_rank": rank,
            "source_bucket": bucket,
            "source_tier": source["source_tier"],
            "scope": "runtime_dictionary",
            "file": relative,
            "business_key_type": "runtime-stable-id",
            "business_key": key,
            "source_locator": source["pointer"],
            "locator_sha256": "",
            "field": field,
            "protected_value": value,
            "value_sha256": sha256_text(value),
            "identity_sha256": sha256_text(identity_payload),
            "review_status": (
                "confirmed-human-protected"
                if bucket == "new-root-human"
                else "authority-protected"
            ),
            "authority_status": f"pass16-{source['action']}",
            "evidence_path_or_key": evidence,
            "record_sha256": "",
        }
        item["record_sha256"] = sha256_text(canonical_record_payload(item))
        result.append(item)

    identities = [row["identity_sha256"] for row in result]
    duplicates = [key for key, count in Counter(identities).items() if count != 1]
    if duplicates:
        raise ProtectionError(f"duplicate Pass16 protected identities: {duplicates[:10]}")
    superseded_tiers = counts_by(superseded, "source_tier")
    if (
        len(superseded) != EXPECTED_PASS16_SUPERSEDED_FIELDS
        or superseded_tiers != EXPECTED_PASS16_SUPERSEDED_SOURCE_TIERS
        or len(result) != EXPECTED_PASS16_PROTECTED_FIELDS
        or len(result) + len(superseded) + excluded_unreviewed_types
        != EXPECTED_PASS16_APPLIED_FIELDS
    ):
        raise ProtectionError(
            "Pass16 current/superseded protection contract drift: "
            f"protected={len(result)} superseded={len(superseded)} "
            f"superseded_tiers={superseded_tiers}"
        )
    return result


PASS19_REQUIRED_COLUMNS = {
    "change_id",
    "file",
    "locator",
    "before",
    "after",
    "source_tier",
    "source_locator",
    "source_sha256",
    "match_method",
    "machine_translated",
    "confidence",
    "review_status",
    "evidence",
    "expected_count",
    "expected_after_count",
}


def pass19_source_file(source_locator: str) -> Path:
    """Return the source file part of an authority locator.

    A fragment after ``#`` identifies a DOM node or Wiki term and is evidence
    metadata, not part of the Windows path.
    """

    return Path(source_locator.split("#", 1)[0])


def verify_pass19_authority_evidence(
    rows: Iterable[dict[str, str]], *, require_available: bool = False
) -> dict[str, int]:
    """Hash-check locally available official/Wiki evidence.

    The external source trees are not checked into this patch repository, so a
    clean CI checkout may only validate their recorded SHA-256 contracts.  On
    the authority workstation (where the paths exist), every row is also bound
    to the exact source bytes and the selected Chinese literal is required to
    occur while the rejected literal is absent.
    """

    checked_rows = 0
    checked_files: set[Path] = set()
    unavailable_rows = 0
    for row in rows:
        source_path = pass19_source_file(row["source_locator"])
        if not source_path.is_file():
            unavailable_rows += 1
            if require_available:
                raise ProtectionError(
                    f"{row['change_id']}: Pass19 authority source is unavailable: {source_path}"
                )
            continue
        if sha256_file(source_path) != row["source_sha256"]:
            raise ProtectionError(
                f"{row['change_id']}: Pass19 authority source digest drift"
            )
        try:
            source_text = source_path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            raise ProtectionError(
                f"{row['change_id']}: Pass19 authority source is not UTF-8"
            ) from exc
        if row["after"] not in source_text or row["before"] in source_text:
            raise ProtectionError(
                f"{row['change_id']}: Pass19 authority source term evidence drift"
            )
        if row["source_tier"] == "official_cn_dump":
            normalized_source = source_path.as_posix().lower()
            if not normalized_source.endswith(row["file"].lower()):
                raise ProtectionError(
                    f"{row['change_id']}: official same-path evidence no longer matches product path"
                )
        else:
            fragment = row["source_locator"].split("#", 1)[1] if "#" in row["source_locator"] else ""
            if row["after"] not in fragment or "→" not in fragment:
                raise ProtectionError(
                    f"{row['change_id']}: Wiki source-key evidence fragment drift"
                )
        checked_rows += 1
        checked_files.add(source_path.resolve())
    return {
        "checked_rows": checked_rows,
        "checked_files": len(checked_files),
        "unavailable_rows": unavailable_rows,
    }


def read_pass19_manifest(root: Path) -> list[dict[str, str]]:
    """Read and validate the applied Pass19 static authority contract.

    Unlike a frontend candidate row, every Pass19 row is a concrete product
    transformation.  The contract binds the exact target file, its authority
    evidence, the final literal, and the number of final occurrences allowed
    in that file.  It intentionally protects only these six change contracts,
    not their whole JS/HTML files.
    """

    path = root / PASS19_REL
    rows = read_tsv(path)
    if len(rows) != EXPECTED_PASS19_CONTRACTS:
        raise ProtectionError(
            f"Pass19 contract count drift: {len(rows)} != {EXPECTED_PASS19_CONTRACTS}"
        )
    if not rows or not PASS19_REQUIRED_COLUMNS.issubset(rows[0]):
        raise ProtectionError("Pass19 manifest has missing required columns")
    ids = [row.get("change_id", "") for row in rows]
    if len(set(ids)) != len(ids) or any(not value for value in ids):
        raise ProtectionError("Pass19 manifest has duplicate or blank change_id")
    evidence_contracts = {
        "official_cn_dump": {
            "match_methods": {"exact-path-dom-match", "exact-path-term-match"},
            "review_status": "official-source-verified",
            "bucket": "official",
            "rank": "1-official-cn",
        },
        "wiki": {
            "match_methods": {"exact-wiki-term-with-official-same-path-absence"},
            "review_status": "wiki-source-verified",
            "bucket": "wiki",
            "rank": "2-wiki",
        },
    }
    total_applied_changes = 0
    total_final_occurrences = 0
    for row in rows:
        contract = evidence_contracts.get(row.get("source_tier", ""))
        if contract is None:
            raise ProtectionError(f"{row['change_id']}: unsupported Pass19 source tier")
        if (
            row.get("machine_translated") != "false"
            or row.get("match_method") not in contract["match_methods"]
            or row.get("review_status") != contract["review_status"]
            or not re.fullmatch(r"[0-9a-f]{64}", row.get("source_sha256", ""))
            or not row.get("source_locator")
            or not row.get("file", "").startswith("magica/")
            or not row.get("before")
            or not row.get("after")
            or row["before"] == row["after"]
        ):
            raise ProtectionError(f"{row['change_id']}: Pass19 authority evidence contract failed")
        try:
            expected_count = int(row["expected_count"])
            expected_after_count = int(row["expected_after_count"])
        except ValueError as exc:
            raise ProtectionError(f"{row['change_id']}: invalid Pass19 expected count") from exc
        if expected_count < 1 or expected_after_count < expected_count:
            raise ProtectionError(f"{row['change_id']}: invalid Pass19 expected count")
        total_applied_changes += expected_count
        total_final_occurrences += expected_after_count
    if total_applied_changes != EXPECTED_PASS19_APPLIED_CHANGES:
        raise ProtectionError(
            "Pass19 expected applied-change count drift: "
            f"{total_applied_changes} != {EXPECTED_PASS19_APPLIED_CHANGES}"
        )
    if total_final_occurrences != EXPECTED_PASS19_FINAL_OCCURRENCES:
        raise ProtectionError(
            "Pass19 expected final-occurrence count drift: "
            f"{total_final_occurrences} != {EXPECTED_PASS19_FINAL_OCCURRENCES}"
        )
    rows = sorted(rows, key=lambda row: row["change_id"])
    if set(PASS19_APPLIED_OCCURRENCE_ORDINALS) != set(ids):
        raise ProtectionError("Pass19 applied-occurrence contract ID drift")
    for row in rows:
        ordinals = PASS19_APPLIED_OCCURRENCE_ORDINALS[row["change_id"]]
        if (
            len(ordinals) != int(row["expected_count"])
            or len(set(ordinals)) != len(ordinals)
            or any(value < 1 or value > int(row["expected_after_count"]) for value in ordinals)
        ):
            raise ProtectionError(
                f"{row['change_id']}: Pass19 applied-occurrence ordinal contract drift"
            )
    verify_pass19_authority_evidence(rows)
    return rows


def pass19_literal_occurrences(text: str, literal: str) -> list[dict[str, Any]]:
    """Return stable, value-independent local anchors for exact occurrences."""

    result: list[dict[str, Any]] = []
    start = 0
    while True:
        position = text.find(literal, start)
        if position < 0:
            break
        end = position + len(literal)
        prefix = text[max(0, position - PASS19_ANCHOR_CONTEXT_CHARS) : position]
        suffix = text[end : min(len(text), end + PASS19_ANCHOR_CONTEXT_CHARS)]
        canonical = prefix + "<PASS19_PROTECTED_LITERAL>" + suffix
        result.append(
            {
                "ordinal": len(result) + 1,
                "position": position,
                "anchor_sha256": sha256_text(canonical),
            }
        )
        start = end
    anchors = [row["anchor_sha256"] for row in result]
    if len(set(anchors)) != len(anchors):
        raise ProtectionError("Pass19 local occurrence anchors are ambiguous")
    return result


def verify_pass19_applied_rows(root: Path, rows: Iterable[dict[str, str]]) -> None:
    """Verify every explicit final literal and its minimum occurrence scope."""

    for row in rows:
        path = root / row["file"]
        if not path.is_file():
            raise ProtectionError(f"{row['change_id']}: Pass19 product file is missing")
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf") or b"\r\n" in raw:
            raise ProtectionError(f"{row['change_id']}: Pass19 product file is not UTF-8/LF without BOM")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtectionError(f"{row['change_id']}: Pass19 product file is not UTF-8") from exc
        expected_after_count = int(row["expected_after_count"])
        before_count = text.count(row["before"])
        after_count = text.count(row["after"])
        if before_count != 0 or after_count != expected_after_count:
            raise ProtectionError(
                f"{row['change_id']}: Pass19 applied value/count drift "
                f"before={before_count} after={after_count} expected_after={expected_after_count}"
            )


def protected_rows_from_pass19(root: Path) -> list[dict[str, str]]:
    """Turn the eleven applied Pass19 occurrences into protected rows."""

    source_rows = read_pass19_manifest(root)
    verify_pass19_applied_rows(root, source_rows)
    result: list[dict[str, str]] = []
    for source in source_rows:
        bucket = "official" if source["source_tier"] == "official_cn_dump" else "wiki"
        rank = "1-official-cn" if bucket == "official" else "2-wiki"
        text = (root / source["file"]).read_text(encoding="utf-8")
        occurrences = pass19_literal_occurrences(text, source["after"])
        if len(occurrences) != int(source["expected_after_count"]):
            raise ProtectionError(
                f"{source['change_id']}: Pass19 final occurrence enumeration drift"
            )
        by_ordinal = {row["ordinal"]: row for row in occurrences}
        for ordinal in PASS19_APPLIED_OCCURRENCE_ORDINALS[source["change_id"]]:
            occurrence = by_ordinal[ordinal]
            business_key = f"{source['change_id']}#after-{ordinal:03d}"
            identity_payload = "\x1f".join(
                [source["file"], "pass19-applied-occurrence", business_key, "applied_literal"]
            )
            item = {
                "protected_id": "",
                "master_record_id": source["change_id"],
                "protection_origin": "pass19-applied-authority-manifest",
                "authority_rank": rank,
                "source_bucket": bucket,
                "source_tier": source["source_tier"],
                "scope": "pass19_static_literal",
                "file": source["file"],
                "business_key_type": "pass19-applied-occurrence",
                "business_key": business_key,
                "source_locator": f"{source['change_id']}:after-occurrence-{ordinal:03d}",
                "locator_sha256": occurrence["anchor_sha256"],
                "field": "applied_literal",
                "protected_value": source["after"],
                "value_sha256": sha256_text(source["after"]),
                "identity_sha256": sha256_text(identity_payload),
                "review_status": source["review_status"],
                "authority_status": "pass19-applied-authority-protected",
                "evidence_path_or_key": (
                    f"{PASS19_REL.as_posix()}#{source['change_id']};"
                    f"applied_occurrence_ordinal={ordinal};"
                    f"source_locator={source['source_locator']};"
                    f"source_sha256={source['source_sha256']};"
                    f"match_method={source['match_method']};"
                    f"expected_after_count={source['expected_after_count']}"
                ),
                "expected_count": "1",
                "record_sha256": "",
            }
            item["record_sha256"] = sha256_text(canonical_record_payload(item))
            result.append(item)
    if len(result) != EXPECTED_PASS19_APPLIED_CHANGES:
        raise ProtectionError(
            f"Pass19 protected applied-occurrence count drift: {len(result)}"
        )
    return result


def combined_protected_rows(
    master: Iterable[dict[str, str]], *, root: Path
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Merge master fields, Pass16 occurrences, and Pass19 applied contracts."""

    master_rows = protected_rows_from_master(master, root=root)
    pass16_rows = protected_rows_from_pass16(root)
    pass19_rows = protected_rows_from_pass19(root)
    combined = {row["identity_sha256"]: row for row in master_rows}
    overlap = 0
    added = 0
    for row in pass16_rows:
        identity = row["identity_sha256"]
        if identity in combined:
            before = combined[identity]
            if (
                before["protected_value"] != row["protected_value"]
                or before["source_bucket"] != row["source_bucket"]
                or before["authority_rank"] != row["authority_rank"]
            ):
                raise ProtectionError(
                    "Pass16/master authority conflict: "
                    f"{row['file']}#{row['business_key']}/{row['field']}"
                )
            overlap += 1
        else:
            combined[identity] = row
            added += 1
    if overlap + added != EXPECTED_PASS16_PROTECTED_FIELDS or added != EXPECTED_PASS16_ADDITIONS:
        raise ProtectionError(
            "Pass16 protection merge drift: "
            f"overlap={overlap} added={added}; "
            f"expected overlap={EXPECTED_PASS16_PROTECTED_FIELDS - EXPECTED_PASS16_ADDITIONS} "
            f"added={EXPECTED_PASS16_ADDITIONS}"
        )
    if len(combined) != EXPECTED_TOTAL or counts_by(
        combined.values(), "source_bucket"
    ) != EXPECTED_BUCKETS:
        raise ProtectionError(
            "master/Pass16 protected selection count drift: "
            f"total={len(combined)} "
            f"buckets={counts_by(combined.values(), 'source_bucket')}; "
            f"expected total={EXPECTED_TOTAL} buckets={EXPECTED_BUCKETS}"
        )

    for row in pass19_rows:
        identity = row["identity_sha256"]
        if identity in combined:
            raise ProtectionError(
                "Pass19 protected identity unexpectedly overlaps existing protection: "
                f"{row['file']}#{row['business_key']}"
            )
        combined[identity] = row

    result = sorted(
        combined.values(),
        key=lambda row: (
            row["file"],
            row["business_key_type"],
            row["business_key"],
            row["field"],
            row["record_sha256"],
        ),
    )
    if (
        len(result) != EXPECTED_TOTAL_WITH_PASS19
        or counts_by(result, "source_bucket") != EXPECTED_BUCKETS_WITH_PASS19
    ):
        raise ProtectionError(
            "combined protected selection count drift: "
            f"total={len(result)} buckets={counts_by(result, 'source_bucket')}; "
            f"expected total={EXPECTED_TOTAL_WITH_PASS19} buckets={EXPECTED_BUCKETS_WITH_PASS19}"
        )
    for number, row in enumerate(result, 1):
        row["protected_id"] = f"AUTH-{number:05d}"
    return result, {
        "master_fields": len(master_rows),
        "pass16_fields": len(pass16_rows),
        "pass16_superseded_non_authority_fields": EXPECTED_PASS16_SUPERSEDED_FIELDS,
        "pass16_overlap": overlap,
        "pass16_added": added,
        "pass19_contracts": EXPECTED_PASS19_CONTRACTS,
        "pass19_protected_occurrences": len(pass19_rows),
        "pass19_applied_changes": EXPECTED_PASS19_APPLIED_CHANGES,
        "pass19_final_occurrences": EXPECTED_PASS19_FINAL_OCCURRENCES,
    }


def aggregate_sha256(rows: Iterable[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["identity_sha256"].encode("ascii"))
        digest.update(b"\0")
        digest.update(row["record_sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def counts_by(rows: Iterable[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row[field] for row in rows).items()))


def build_snapshot(
    root: Path,
    *,
    output_tsv: Path | None = None,
    output_manifest: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    master_path = root / MASTER_REL
    summary_path = root / SUMMARY_REL
    output_tsv = output_tsv or root / PROTECTED_TSV_REL
    output_manifest = output_manifest or root / MANIFEST_REL
    master = read_tsv(master_path)
    protected, merge_counts = combined_protected_rows(master, root=root)
    _selected, held = select_protected_master_rows(master)
    pass19_rows = read_pass19_manifest(root)
    pass19_evidence = verify_pass19_authority_evidence(pass19_rows)
    write_tsv(output_tsv, protected)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    file_counts = counts_by(protected, "file")
    mixed_files = sorted(
        file
        for file in file_counts
        if file != GLOSSARY_REL.as_posix()
    )
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": summary["generated_at"],
        "generator": "tools/build-v26-authority-protection.py",
        "authority_order": [
            "official-cn",
            "wiki",
            "confirmed-human",
            "all-llm-or-machine-translation",
        ],
        "selection_policy": {
            "official": "protect every source_bucket=official row",
            "wiki": "protect every source_bucket=wiki row except the three explicitly held review-only candidates",
            "confirmed_human": "protect only source_bucket=new-root-human rows with review_status=authority-verified or confirmed-human-verified, plus exact Pass16 3_manual_verified occurrences; root-reviewed terminology and root-translated review candidates are not confirmed-human",
            "pass16": "from 855 runtime_change_log fields, exclude the one unreviewed 3_manual_translation candidate and 27 exact root-reviewed terminology supersessions; merge the remaining 827 high-authority/current fields by stable business key, retaining 682 identical machine-review overlaps and adding 145 omitted fields",
            "pass19": "protect all eleven applied authority replacements as independent local-context occurrences; the six source contracts also validate the rejected/final literal counts without freezing whole JS/HTML files",
            "candidate_only_metadata": "exclude high-authority frontend candidate metadata with blank current_cn; its applied product value must be protected through an explicit product authority contract",
            "root_reviewed_terminology": "never classify source_tier=root-reviewed-official-cn-terminology, review_status=root-reviewed-approved, or any Codex/LLM coarse translation as confirmed-human authority",
            "llm": "never protected as authority and never allowed to replace a protected field",
        },
        "held_wiki_review_only": [
            {
                "master_record_id": row["record_id"],
                "file": row["file"],
                "stable_key": row["stable_key_or_line"],
                "field": row["field"],
                "review_status": row["review_status"],
            }
            for row in sorted(held, key=row_identity)
        ],
        "pass16_type_contract": {
            "translation_types": 148,
            "official_or_wiki_replacement_types": 137,
            "wiki_exact_equivalence_types": 2,
            "confirmed_human_translation_types": 9,
            "confirmed_human_map_types": 8,
            "confirmed_human_punctuation_types": 1,
            "applied_product_fields": EXPECTED_PASS16_APPLIED_FIELDS,
            "protected_product_fields": EXPECTED_PASS16_PROTECTED_FIELDS,
            "superseded_non_authority_product_fields": EXPECTED_PASS16_SUPERSEDED_FIELDS,
            "superseded_source_tiers": EXPECTED_PASS16_SUPERSEDED_SOURCE_TIERS,
            "supersession_evidence": VISIBLE_TERM_CLOSURE_REL.as_posix(),
            "confirmed_human_product_fields": 11,
            "official_cn_punctuation_product_fields_included_above": 1,
            "excluded_unreviewed_manual_translation_types": 1,
            "excluded_unreviewed_product_fields": 1,
            "excluded_unreviewed_business_key": "magica/js/libs/emotionSkillMap.json#2203113/name",
            "note": "The nine confirmed-human types are eight 3_manual_verified map types plus the official-CN punctuation field. The high-risk 3_manual_translation candidate is not protected. Twenty-seven later root-reviewed terminology values are verified as exact supersessions but remain outside the authority snapshot.",
        },
        "pass19_applied_authority_contract": {
            "manifest": PASS19_REL.as_posix(),
            "contracts": EXPECTED_PASS19_CONTRACTS,
            "expected_applied_changes": EXPECTED_PASS19_APPLIED_CHANGES,
            "expected_final_occurrences": EXPECTED_PASS19_FINAL_OCCURRENCES,
            "protected_applied_occurrences": EXPECTED_PASS19_APPLIED_CHANGES,
            "applied_occurrence_ordinals": {
                key: list(value)
                for key, value in sorted(PASS19_APPLIED_OCCURRENCE_ORDINALS.items())
            },
            "anchor_context_chars": PASS19_ANCHOR_CONTEXT_CHARS,
            "external_evidence_validation": pass19_evidence,
            "rule": "Each applied replacement has a stable value-independent local-context anchor. Each source row also binds the target file, evidence SHA-256, expected change count, exact final after-literal count, and absence of the rejected literal.",
        },
        "excluded_candidate_only_metadata": [
            {
                "master_record_id": row["record_id"],
                "file": row["file"],
                "stable_key": row["stable_key_or_line"],
                "field": row["field"],
                "reason": "no current product value; protected by Pass19 applied authority contract",
            }
            for row in master
            if candidate_only_metadata(row)
        ],
        "counts": {
            "protected_fields": len(protected),
            "protected_files": len(file_counts),
            "merge": merge_counts,
            "by_source_bucket": counts_by(protected, "source_bucket"),
            "by_authority_rank": counts_by(protected, "authority_rank"),
            "by_scope": counts_by(protected, "scope"),
            "by_protection_origin": counts_by(protected, "protection_origin"),
            "by_file": file_counts,
        },
        "baseline": {
            "machine_review_master": MASTER_REL.as_posix(),
            "machine_review_master_sha256": sha256_file(master_path),
            "machine_review_summary": SUMMARY_REL.as_posix(),
            "machine_review_summary_sha256": sha256_file(summary_path),
            "pass16_runtime_change_log": PASS16_CHANGE_LOG_REL.as_posix(),
            "pass16_runtime_change_log_sha256": sha256_file(root / PASS16_CHANGE_LOG_REL),
            "pass16_runtime_translation_map": PASS16_TRANSLATION_MAP_REL.as_posix(),
            "pass16_runtime_translation_map_sha256": sha256_file(root / PASS16_TRANSLATION_MAP_REL),
            "pass19_applied_authority_manifest": PASS19_REL.as_posix(),
            "pass19_applied_authority_manifest_sha256": sha256_file(root / PASS19_REL),
            "visible_term_closure": VISIBLE_TERM_CLOSURE_REL.as_posix(),
            "visible_term_closure_sha256": sha256_file(root / VISIBLE_TERM_CLOSURE_REL),
            "protected_fields_tsv": output_tsv.relative_to(root).as_posix()
            if output_tsv.is_relative_to(root)
            else str(output_tsv),
            "protected_fields_tsv_sha256": sha256_file(output_tsv),
            "protected_fields_aggregate_sha256": aggregate_sha256(protected),
        },
        "whole_file_protections": {
            GLOSSARY_REL.as_posix(): {
                "reason": "all 955 entries are Wiki authority support",
                "sha256": sha256_file(root / GLOSSARY_REL),
            }
        },
        "mixed_file_policy": {
            "files": mixed_files,
            "rule": "validate only listed stable business-key/field/value hashes; lower-tier fields in the same file remain editable",
        },
        "freshness_gate": {
            "required_order": [
                "python tools/build-v26-machine-review.py",
                "git diff --exit-code -- magica/i18n_audit/release_v26_authority/machine_translation_review",
                "python tools/verify-v26-authority-protection.py --json",
            ],
            "summary_product_content_sha256": summary["snapshot"]["product_content_sha256"],
            "summary_product_content_file_count": summary["snapshot"]["product_content_file_count"],
        },
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def stable_key(base: str, obj: dict[str, Any]) -> str:
    if base == "charaMessageList":
        return f"{obj.get('charaNo', '')}|{obj.get('messageId', '')}"
    if base == "live2dList":
        return f"{obj.get('charaId', '')}|{obj.get('live2dId', '')}"
    if base == "eventStoryList":
        value = obj.get("storyIds", "")
        return (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if isinstance(value, list)
            else str(value)
        )
    for field in LIST_KEYS.get(base, ()):
        if field in obj:
            return str(obj[field])
    return ""


def load_two_column_tsv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                raise ProtectionError(f"{path}:{line_number}: expected exactly two TSV columns")
            key, value = parts
            if key in result:
                raise ProtectionError(f"{path}:{line_number}: duplicate source key {key!r}")
            result[key] = value
    return result


def current_values_for_file(root: Path, rows: list[dict[str, str]]) -> dict[str, str]:
    relative = rows[0]["file"]
    path = root / relative
    scope = rows[0]["scope"]
    if not path.is_file():
        raise ProtectionError(f"protected source file is missing: {relative}")
    if any(row["scope"] != scope for row in rows):
        raise ProtectionError(f"mixed scopes for protected source file: {relative}")

    if scope == "runtime_dictionary":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        base = path.stem
        index: dict[str, dict[str, Any]] = {}
        if isinstance(data, dict):
            index = {str(key): value for key, value in data.items() if isinstance(value, dict)}
        elif isinstance(data, list):
            for obj in data:
                if not isinstance(obj, dict):
                    continue
                key = stable_key(base, obj)
                if not key:
                    raise ProtectionError(f"empty runtime stable key in {relative}")
                if key in index:
                    raise ProtectionError(f"duplicate runtime stable key in {relative}: {key}")
                index[key] = obj
        else:
            raise ProtectionError(f"protected runtime dictionary has unsupported root type: {relative}")
        result: dict[str, str] = {}
        for row in rows:
            key = row["business_key"]
            if key not in index:
                raise ProtectionError(f"protected runtime key missing: {relative}#{key}")
            field = row["field"]
            if field not in index[key]:
                raise ProtectionError(f"protected runtime field missing: {relative}#{key}/{field}")
            value = index[key][field]
            if not isinstance(value, str):
                raise ProtectionError(f"protected runtime field is not text: {relative}#{key}/{field}")
            result[row["identity_sha256"]] = value
        return result

    if scope in {"offline_authority_support", "native_engine_i18n"}:
        index = load_two_column_tsv(path)
        result = {}
        for row in rows:
            key = row["business_key"]
            if key not in index:
                raise ProtectionError(f"protected TSV key missing: {relative}#{key}")
            result[row["identity_sha256"]] = index[key]
        return result

    if scope == "static_js_html":
        result = {}
        for row in rows:
            candidates = static_literal_candidates(path, row["source_locator"], row["field"])
            matching = [literal for anchor, literal in candidates if anchor == row["locator_sha256"]]
            if len(matching) != 1:
                raise ProtectionError(
                    f"protected static object locator drift: {relative}#{row['source_locator']}/{row['field']} matches={len(matching)}"
                )
            result[row["identity_sha256"]] = matching[0]
        return result

    if scope == "pass19_static_literal":
        # Re-load the authority manifest rather than trusting duplicated text
        # in the generated TSV.  This binds each applied occurrence to the
        # file/value/count contract and its value-independent context anchor.
        manifest_rows = {row["change_id"]: row for row in read_pass19_manifest(root)}
        selected: list[dict[str, str]] = []
        result = {}
        text = path.read_text(encoding="utf-8")
        for row in rows:
            source = manifest_rows.get(row["master_record_id"])
            if source is None:
                raise ProtectionError(
                    f"Pass19 protected change is missing from manifest: {row['master_record_id']}"
                )
            ordinal_match = re.fullmatch(
                rf"{re.escape(source['change_id'])}#after-(\d{{3}})",
                row["business_key"],
            )
            if ordinal_match is None:
                raise ProtectionError(
                    f"Pass19 protected occurrence key drift: {row['business_key']}"
                )
            ordinal = int(ordinal_match.group(1))
            if (
                row["file"] != source["file"]
                or row["protected_value"] != source["after"]
                or row.get("expected_count", "") != "1"
                or ordinal not in PASS19_APPLIED_OCCURRENCE_ORDINALS[source["change_id"]]
                or row["source_locator"]
                != f"{source['change_id']}:after-occurrence-{ordinal:03d}"
            ):
                raise ProtectionError(
                    f"Pass19 protected row/manifest drift: {row['business_key']}"
                )
            occurrences = pass19_literal_occurrences(text, source["after"])
            matching = [
                occurrence
                for occurrence in occurrences
                if occurrence["anchor_sha256"] == row["locator_sha256"]
            ]
            if len(matching) != 1 or matching[0]["ordinal"] != ordinal:
                raise ProtectionError(
                    f"Pass19 applied occurrence locator drift: {row['business_key']}"
                )
            if source not in selected:
                selected.append(source)
            result[row["identity_sha256"]] = source["after"]
        verify_pass19_applied_rows(root, selected)
        return result

    raise ProtectionError(f"unsupported protected source scope: {scope}")


def verify_current_product_values(
    root: Path, rows: Iterable[dict[str, str]]
) -> dict[str, int]:
    """Verify protected field values at their stable product locations.

    This is deliberately factored out of :func:`verify_snapshot` so mutation
    tests exercise the same fail-closed comparison used by the release gate,
    rather than merely reimplementing its final hash assertion.
    """

    # A product file may legitimately contain records from more than one
    # protection mechanism.  Pass19, for example, adds exact occurrence
    # anchors to JS files that already contain object-field records selected
    # from the machine-review master.  Each extractor has a scope-specific
    # addressing contract, so evaluate homogeneous (file, scope) groups while
    # still reporting the number of unique protected files.
    by_file_scope: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        by_file_scope.setdefault((row["file"], row["scope"]), []).append(row)
    checked_fields = 0
    protected_files: set[str] = set()
    for (relative, _scope), file_rows in sorted(by_file_scope.items()):
        protected_files.add(relative)
        actual = current_values_for_file(root, file_rows)
        for row in file_rows:
            identity = row["identity_sha256"]
            if identity not in actual:
                raise ProtectionError(
                    f"protected product identity missing: {relative}#{row['business_key']}/{row['field']}"
                )
            if sha256_text(actual[identity]) != row["value_sha256"]:
                raise ProtectionError(
                    f"protected product value drift: {relative}#{row['business_key']}/{row['field']}"
                )
            checked_fields += 1
    return {"protected_fields": checked_fields, "protected_files": len(protected_files)}


def validate_row_hashes(rows: list[dict[str, str]]) -> None:
    identities: set[str] = set()
    for row in rows:
        key_payload = "\x1f".join(
            [row["file"], row["business_key_type"], row["business_key"], row["field"]]
        )
        expected_identity = sha256_text(key_payload)
        expected_value = sha256_text(row["protected_value"])
        expected_record = sha256_text(canonical_record_payload(row))
        if row["identity_sha256"] != expected_identity:
            raise ProtectionError(f"identity hash mismatch: {row['protected_id']}")
        if row["value_sha256"] != expected_value:
            raise ProtectionError(f"value hash mismatch: {row['protected_id']}")
        if row["record_sha256"] != expected_record:
            raise ProtectionError(f"record hash mismatch: {row['protected_id']}")
        if expected_identity in identities:
            raise ProtectionError(f"duplicate protected identity hash: {expected_identity}")
        identities.add(expected_identity)


def compare_baseline_to_master(
    baseline_rows: list[dict[str, str]], master_rows: list[dict[str, str]], *, root: Path
) -> None:
    current_rows, _merge_counts = combined_protected_rows(master_rows, root=root)
    baseline = {row["identity_sha256"]: row for row in baseline_rows}
    current = {row["identity_sha256"]: row for row in current_rows}
    if baseline.keys() != current.keys():
        missing = sorted(baseline.keys() - current.keys())
        added = sorted(current.keys() - baseline.keys())
        raise ProtectionError(
            f"protected identity set drift: missing={missing[:10]}, added={added[:10]}"
        )
    compare_fields = [
        "protection_origin",
        "authority_rank",
        "source_bucket",
        "source_tier",
        "scope",
        "file",
        "business_key_type",
        "business_key",
        "source_locator",
        "locator_sha256",
        "field",
        "protected_value",
        "value_sha256",
        "review_status",
        "authority_status",
        "evidence_path_or_key",
        "expected_count",
        "record_sha256",
    ]
    for identity in sorted(baseline):
        before = baseline[identity]
        after = current[identity]
        changed = [
            field for field in compare_fields
            if before.get(field, "") != after.get(field, "")
        ]
        if changed:
            raise ProtectionError(
                f"protected field/provenance drift: {before['file']}#{before['business_key']}/{before['field']} changed={changed}"
            )


def product_content_snapshot(root: Path) -> tuple[int, str]:
    """Mirror the machine-review generator's stable product input aggregate."""

    archive_suffixes = {".zip", ".7z", ".tar", ".gz", ".apk"}
    stable_top_dirs = {
        "i18n",
        "madomagi",
        "magica",
    }
    stable_magica_dirs = {"css", "fonts", "js", "resource", "template"}
    stable_root_files = {
        ".gitattributes",
        ".gitignore",
        "asset_main_cn.json",
        "url_map.json",
    }
    excluded_i18n_files = {"migration-source-summary.json", "uiTextList.json"}
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if len(rel.parts) == 1 and rel.name not in stable_root_files:
            continue
        if len(rel.parts) > 1 and rel.parts[0] not in stable_top_dirs:
            continue
        if rel.parts[0] == "tools":
            continue
        if ".git" in rel.parts or "__pycache__" in rel.parts:
            continue
        if path.suffix == ".pyc" or path.suffix.lower() in archive_suffixes:
            continue
        if len(rel.parts) >= 2 and rel.parts[:2] in {
            ("magica", "i18n_audit"),
            ("magica", "research"),
            ("i18n", "generated"),
        }:
            continue
        if rel.parts[0] == "madomagi" and rel.as_posix() != "madomagi/engine_i18n.tsv":
            continue
        if rel.parts[0] == "magica" and (
            len(rel.parts) < 2 or rel.parts[1] not in stable_magica_dirs
        ):
            continue
        if rel.parts[0] == "i18n" and path.name in excluded_i18n_files:
            continue
        paths.append(path)
    paths.sort(key=lambda path: path.relative_to(root).as_posix())
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(canonical_product_file_sha256(path)))
        digest.update(b"\n")
    return len(paths), digest.hexdigest()


def verify_machine_review_freshness(root: Path, summary: dict[str, Any]) -> None:
    snapshot = summary["snapshot"]
    libs = root / "magica/js/libs"
    current_dictionary_hashes = {
        path.name: sha256_file(path) for path in sorted(libs.glob("*.json"))
    }
    if current_dictionary_hashes != snapshot["runtime_dictionary_sha256"]:
        raise ProtectionError("machine-review runtime dictionary snapshot is stale")
    engine_hash = sha256_file(root / "madomagi/engine_i18n.tsv")
    if engine_hash != snapshot["engine_i18n_sha256"]:
        raise ProtectionError("machine-review engine_i18n snapshot is stale")
    file_count, aggregate = product_content_snapshot(root)
    if file_count != snapshot["product_content_file_count"] or aggregate != snapshot["product_content_sha256"]:
        raise ProtectionError(
            "machine-review product-content snapshot is stale: "
            f"current=({file_count},{aggregate}) "
            f"recorded=({snapshot['product_content_file_count']},{snapshot['product_content_sha256']})"
        )


def verify_snapshot(root: Path, *, require_freshness: bool = True) -> dict[str, Any]:
    root = root.resolve()
    master_path = root / MASTER_REL
    summary_path = root / SUMMARY_REL
    tsv_path = root / PROTECTED_TSV_REL
    manifest_path = root / MANIFEST_REL
    for path in (
        master_path,
        summary_path,
        tsv_path,
        manifest_path,
        root / GLOSSARY_REL,
        root / PASS16_CHANGE_LOG_REL,
        root / PASS16_TRANSLATION_MAP_REL,
        root / PASS19_REL,
        root / VISIBLE_TERM_CLOSURE_REL,
    ):
        if not path.is_file():
            raise ProtectionError(f"required authority-protection input is missing: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ProtectionError(f"unexpected protection manifest schema: {manifest.get('schema')}")
    baseline = manifest["baseline"]
    if sha256_file(tsv_path) != baseline["protected_fields_tsv_sha256"]:
        raise ProtectionError("protected TSV digest does not match manifest")
    if sha256_file(master_path) != baseline["machine_review_master_sha256"]:
        raise ProtectionError("machine-review master digest does not match protection baseline")
    if sha256_file(summary_path) != baseline["machine_review_summary_sha256"]:
        raise ProtectionError("machine-review summary digest does not match protection baseline")
    if sha256_file(root / PASS16_CHANGE_LOG_REL) != baseline["pass16_runtime_change_log_sha256"]:
        raise ProtectionError("Pass16 runtime change-log digest does not match protection baseline")
    if sha256_file(root / PASS16_TRANSLATION_MAP_REL) != baseline["pass16_runtime_translation_map_sha256"]:
        raise ProtectionError("Pass16 runtime translation-map digest does not match protection baseline")
    if sha256_file(root / PASS19_REL) != baseline["pass19_applied_authority_manifest_sha256"]:
        raise ProtectionError("Pass19 applied authority manifest digest does not match protection baseline")
    if sha256_file(root / VISIBLE_TERM_CLOSURE_REL) != baseline["visible_term_closure_sha256"]:
        raise ProtectionError("visible-term closure digest does not match protection baseline")

    rows = read_tsv(tsv_path)
    if len(rows) != EXPECTED_TOTAL_WITH_PASS19:
        raise ProtectionError(
            f"protected TSV count drift: {len(rows)} != {EXPECTED_TOTAL_WITH_PASS19}"
        )
    validate_row_hashes(rows)
    if aggregate_sha256(rows) != baseline["protected_fields_aggregate_sha256"]:
        raise ProtectionError("protected field aggregate digest does not match manifest")
    manifest_counts = manifest["counts"]
    if manifest_counts["protected_fields"] != len(rows):
        raise ProtectionError("manifest protected_fields count is inconsistent")
    if manifest_counts["protected_files"] != len(counts_by(rows, "file")):
        raise ProtectionError("manifest protected_files count is inconsistent")
    if manifest_counts["by_source_bucket"] != counts_by(rows, "source_bucket"):
        raise ProtectionError("manifest source-bucket counts are inconsistent")
    if manifest_counts["by_source_bucket"] != EXPECTED_BUCKETS_WITH_PASS19:
        raise ProtectionError("manifest source-bucket contract drift")
    if manifest_counts["by_authority_rank"] != counts_by(rows, "authority_rank"):
        raise ProtectionError("manifest authority-rank counts are inconsistent")
    if manifest_counts["by_scope"] != counts_by(rows, "scope"):
        raise ProtectionError("manifest scope counts are inconsistent")
    if manifest_counts["by_protection_origin"] != counts_by(rows, "protection_origin"):
        raise ProtectionError("manifest protection-origin counts are inconsistent")
    if manifest_counts["by_file"] != counts_by(rows, "file"):
        raise ProtectionError("manifest file counts are inconsistent")
    expected_merge = {
        "master_fields": EXPECTED_MASTER_TOTAL,
        "pass16_fields": EXPECTED_PASS16_PROTECTED_FIELDS,
        "pass16_superseded_non_authority_fields": EXPECTED_PASS16_SUPERSEDED_FIELDS,
        "pass16_overlap": EXPECTED_PASS16_PROTECTED_FIELDS - EXPECTED_PASS16_ADDITIONS,
        "pass16_added": EXPECTED_PASS16_ADDITIONS,
        "pass19_contracts": EXPECTED_PASS19_CONTRACTS,
        "pass19_protected_occurrences": EXPECTED_PASS19_APPLIED_CHANGES,
        "pass19_applied_changes": EXPECTED_PASS19_APPLIED_CHANGES,
        "pass19_final_occurrences": EXPECTED_PASS19_FINAL_OCCURRENCES,
    }
    if manifest_counts["merge"] != expected_merge:
        raise ProtectionError("manifest Pass16 merge counts are inconsistent")

    master_rows = read_tsv(master_path)
    compare_baseline_to_master(rows, master_rows, root=root)

    checked = verify_current_product_values(root, rows)

    glossary_record = manifest["whole_file_protections"][GLOSSARY_REL.as_posix()]
    if sha256_file(root / GLOSSARY_REL) != glossary_record["sha256"]:
        raise ProtectionError("whole-file Wiki glossary digest drift")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if require_freshness:
        verify_machine_review_freshness(root, summary)

    pass19_evidence = verify_pass19_authority_evidence(read_pass19_manifest(root))

    return {
        "schema": "magireco-cn-v26-authority-protection-verification/v3",
        "status": "PASS",
        "protected_fields": len(rows),
        "protected_files": checked["protected_files"],
        "by_source_bucket": counts_by(rows, "source_bucket"),
        "by_authority_rank": counts_by(rows, "authority_rank"),
        "by_scope": counts_by(rows, "scope"),
        "by_protection_origin": counts_by(rows, "protection_origin"),
        "pass16_merge": manifest_counts["merge"],
        "pass19_external_evidence_validation": pass19_evidence,
        "protected_fields_aggregate_sha256": baseline["protected_fields_aggregate_sha256"],
        "protected_fields_tsv_sha256": baseline["protected_fields_tsv_sha256"],
        "glossary_sha256": glossary_record["sha256"],
        "machine_review_fresh": require_freshness,
    }
