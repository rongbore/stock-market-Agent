"""Verify research ZIP byte integrity offline without extracting or executing files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import struct
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile
import zlib

MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_MEMBERS = 128
MAX_CENTRAL_DIRECTORY_BYTES = 256 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024
CHUNK_BYTES = 64 * 1024
BASE_FIELDS = {"schema_version", "status", "batch_input_sha256", "batch_result_payload_sha256",
               "item_count", "generated_count", "calendar_blocked_count", "failed_count",
               "source_content_verified", "historical_point_in_time_verified",
               "exchange_calendar_verified", "files"}
STATUS_VALUES = {"ALL_RESEARCH_GENERATED_UNVERIFIED", "PARTIAL_RESEARCH_UNVERIFIED", "NO_RESEARCH_GENERATED"}
MESSAGES = {
    "invalid_zip": "无法读取完整的 ZIP 文件。",
    "limit_exceeded": "研究包超过离线校验的体积或文件数量限额。",
    "unsafe_member": "研究包包含不安全路径、特殊文件、加密或不支持的压缩方式。",
    "duplicate_member": "研究包包含重复文件名。",
    "invalid_manifest": "校验清单缺失或结构无效。",
    "path_set_mismatch": "包内文件集合与校验清单不一致。",
    "size_mismatch": "文件字节数与校验清单不一致。",
    "hash_mismatch": "文件 SHA-256 与校验清单不一致。",
    "invalid_expected_sha256": "预期 SHA-256 必须是 64 位十六进制字符。",
    "archive_hash_mismatch": "整个 ZIP 的 SHA-256 与预期值不一致。",
}


class PackageError(ValueError):
    pass


def _require(condition, code):
    if not condition:
        raise PackageError(code)


def _safe_path(name):
    return (type(name) is str and len(name) <= 240 and
            re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", name) is not None and
            all(part not in (".", "..") for part in name.split("/")))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "invalid_manifest")
        result[key] = value
    return result


def _manifest(data):
    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                            parse_constant=lambda value: (_ for _ in ()).throw(PackageError("invalid_manifest")))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise PackageError("invalid_manifest") from error
    _require(type(result) is dict, "invalid_manifest")
    fields = set(result)
    allowed = (BASE_FIELDS, BASE_FIELDS | {"collection_request_sha256"},
               BASE_FIELDS | {"collection_request_sha256", "calendar_source_file"})
    _require(fields in allowed and result["schema_version"] == "0.1", "invalid_manifest")
    _require(type(result["status"]) is str and result["status"] in STATUS_VALUES, "invalid_manifest")
    for key in ("batch_input_sha256", "batch_result_payload_sha256", "collection_request_sha256"):
        if key in result:
            _require(type(result[key]) is str and re.fullmatch(r"[0-9a-f]{64}", result[key]), "invalid_manifest")
    for key in ("item_count", "generated_count", "calendar_blocked_count", "failed_count"):
        _require(type(result[key]) is int and 0 <= result[key] <= 20, "invalid_manifest")
    _require(1 <= result["item_count"] == sum(result[k] for k in
             ("generated_count", "calendar_blocked_count", "failed_count")), "invalid_manifest")
    for key in ("source_content_verified", "historical_point_in_time_verified", "exchange_calendar_verified"):
        _require(type(result[key]) is bool, "invalid_manifest")
    _require(type(result["files"]) is list and 1 <= len(result["files"]) < MAX_MEMBERS, "invalid_manifest")
    entries = {}
    for entry in result["files"]:
        _require(type(entry) is dict and set(entry) == {"path", "size_bytes", "sha256"}, "invalid_manifest")
        name = entry["path"]
        _require(_safe_path(name) and name != "manifest.json" and name not in entries, "invalid_manifest")
        _require(type(entry["size_bytes"]) is int and 0 <= entry["size_bytes"] <= MAX_MEMBER_BYTES,
                 "invalid_manifest")
        _require(type(entry["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), "invalid_manifest")
        entries[name] = entry
    _require({"index.html", "summary.md", "batch-result.json"} <= set(entries), "invalid_manifest")
    _require(("collection_request_sha256" in result) == ("collection.json" in entries), "invalid_manifest")
    _require(("calendar_source_file" in result) == ("calendar-source.json" in entries), "invalid_manifest")
    if "calendar_source_file" in result:
        _require(result["calendar_source_file"] == "calendar-source.json", "invalid_manifest")
    return entries


def _read_member(archive, info, limit, *, retain=False):
    size, digest, chunks = 0, hashlib.sha256(), []
    with archive.open(info) as stream:
        while True:
            chunk = stream.read(min(CHUNK_BYTES, limit - size + 1))
            if not chunk:
                break
            size += len(chunk)
            _require(size <= limit, "limit_exceeded")
            digest.update(chunk)
            if retain:
                chunks.append(chunk)
    _require(size == info.file_size, "size_mismatch")
    return size, digest.hexdigest(), b"".join(chunks)


def _preflight_directory(stream, archive_size):
    # Standard EOCD has at most a 65535-byte comment. Bound metadata before
    # ZipFile allocates one ZipInfo per central-directory entry; ZIP64 is outside
    # this small research-package format.
    stream.seek(max(0, archive_size - 65557))
    tail = stream.read(65557)
    offset = tail.rfind(b"PK\x05\x06")
    _require(offset >= 0 and len(tail) - offset >= 22, "invalid_zip")
    _, disk, directory_disk, disk_count, count, size, start, comment = struct.unpack(
        "<4s4H2LH", tail[offset:offset + 22])
    _require(len(tail) - offset == 22 + comment and disk == directory_disk == 0 and
             disk_count == count and count != 65535 and size != 0xffffffff and start != 0xffffffff,
             "invalid_zip")
    _require(count <= MAX_MEMBERS and size <= MAX_CENTRAL_DIRECTORY_BYTES, "limit_exceeded")
    footer_start = archive_size - len(tail) + offset
    _require(start + size == footer_start, "invalid_zip")
    if footer_start >= 20:
        stream.seek(footer_start - 20)
        _require(stream.read(4) != b"PK\x06\x07", "invalid_zip")
    stream.seek(0)


def _verify(path, expected_sha256):
    with Path(path).open("rb") as stream:
        stream.seek(0, 2)
        archive_size = stream.tell()
        _require(archive_size <= MAX_ARCHIVE_BYTES, "limit_exceeded")
        if expected_sha256 is not None:
            stream.seek(0)
            digest = hashlib.sha256()
            remaining = archive_size
            while remaining:
                chunk = stream.read(min(CHUNK_BYTES, remaining))
                _require(bool(chunk), "archive_hash_mismatch")
                digest.update(chunk)
                remaining -= len(chunk)
            _require(not stream.read(1) and digest.hexdigest() == expected_sha256.lower(),
                     "archive_hash_mismatch")
        _preflight_directory(stream, archive_size)
        with ZipFile(stream) as archive:
            infos = archive.infolist()
            _require(len(infos) <= MAX_MEMBERS, "limit_exceeded")
            members, total = {}, 0
            for info in infos:
                _require(info.filename == info.orig_filename and _safe_path(info.filename) and
                         not info.is_dir() and stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG) and
                         not info.flag_bits & 1 and info.compress_type in (ZIP_STORED, ZIP_DEFLATED), "unsafe_member")
                _require(info.filename not in members, "duplicate_member")
                limit = MAX_MANIFEST_BYTES if info.filename == "manifest.json" else MAX_MEMBER_BYTES
                _require(0 <= info.file_size <= limit, "limit_exceeded")
                total += info.file_size
                _require(total <= MAX_TOTAL_BYTES, "limit_exceeded")
                members[info.filename] = info
            _require("manifest.json" in members, "invalid_manifest")
            _, _, manifest_bytes = _read_member(archive, members["manifest.json"], MAX_MANIFEST_BYTES, retain=True)
            entries = _manifest(manifest_bytes)
            _require(set(entries) == set(members) - {"manifest.json"}, "path_set_mismatch")
            checked_bytes = 0
            for name, entry in entries.items():
                _require(entry["size_bytes"] == members[name].file_size, "size_mismatch")
                size, digest, _ = _read_member(archive, members[name], MAX_MEMBER_BYTES)
                _require(digest == entry["sha256"], "hash_mismatch")
                checked_bytes += size
            return len(entries), checked_bytes


def verify_research_package(path, *, expected_sha256=None):
    """Return a JSON-compatible integrity result; never trust source verification labels."""
    result = {"schema_version": "0.1", "status": "INVALID_PACKAGE", "integrity_verified": False,
              "source_content_verified": False, "historical_point_in_time_verified": False,
              "exchange_calendar_verified": False, "independent_source_verified": False,
              "checked_file_count": 0, "checked_bytes": 0,
              "limitation": "仅校验文件与包内清单的字节一致性；不认证来源、金融内容或清单真实性。"}
    try:
        if expected_sha256 is not None:
            _require(isinstance(expected_sha256, str) and re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256),
                     "invalid_expected_sha256")
        count, size = _verify(path, expected_sha256)
    except PackageError as error:
        result.update(reason=str(error), message=MESSAGES[str(error)])
    except (OSError, BadZipFile, RuntimeError, NotImplementedError, EOFError, ValueError, zlib.error):
        result.update(reason="invalid_zip", message=MESSAGES["invalid_zip"])
    else:
        result.update(status="INTEGRITY_VERIFIED_UNVERIFIED_SOURCE", integrity_verified=True,
                      reason=None, message="文件完整性校验通过；来源仍未核验。",
                      checked_file_count=count, checked_bytes=size)
        if expected_sha256 is not None:
            result["archive_sha256_matched"] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Existing research ZIP; read only")
    parser.add_argument("--expected-sha256", help="SHA-256 of the entire ZIP from the original run summary")
    args = parser.parse_args(argv)
    result = verify_research_package(args.input, expected_sha256=args.expected_sha256)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["integrity_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
