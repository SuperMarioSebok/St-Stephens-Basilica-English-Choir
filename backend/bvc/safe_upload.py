"""Validation of untrusted uploads: MusicXML, MXL (zip), audio and PDF.

Nothing here writes user-supplied names to disk. MXL archives are read in memory
only, never extracted, so path traversal names cannot reach the filesystem; they
are still rejected so a hostile archive fails loudly.
"""
from __future__ import annotations

import io
import posixpath
import zipfile

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from . import config


class UploadError(ValueError):
    """A user-facing validation failure (HTTP 400)."""


def check_size(data: bytes, limit: int, what: str) -> None:
    if len(data) == 0:
        raise UploadError(f"{what} is empty")
    if len(data) > limit:
        raise UploadError(f"{what} is larger than {limit // (1024 * 1024)} MB")


def parse_xml_safely(data: bytes):
    """Parse XML refusing entity declarations and external references.

    MusicXML files normally carry a public DOCTYPE, which is allowed; any
    <!ENTITY> (billion laughs, XXE) or external resolution is refused.
    """
    try:
        return SafeET.fromstring(data, forbid_dtd=False, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as exc:
        raise UploadError(f"XML rejected for safety: {type(exc).__name__}") from exc
    except SafeET.ParseError as exc:
        raise UploadError(f"Not well-formed XML: {exc}") from exc


def _safe_member_name(name: str) -> bool:
    if not name or name.startswith("/") or "\\" in name or ":" in name:
        return False
    norm = posixpath.normpath(name)
    return not (norm.startswith("..") or "/../" in f"/{norm}/")


def read_mxl(data: bytes) -> bytes:
    """Return the root MusicXML document bytes from a compressed .mxl archive."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise UploadError("MXL file is not a valid zip archive") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) > config.MXL_MAX_MEMBERS:
            raise UploadError("MXL archive has too many files")
        total = 0
        for info in infos:
            if not _safe_member_name(info.filename):
                raise UploadError(f"MXL archive contains an unsafe path: {info.filename!r}")
            if info.flag_bits & 0x1:
                raise UploadError("Encrypted MXL archives are not supported")
            total += info.file_size
            if info.file_size > config.MXL_MAX_UNCOMPRESSED or total > config.MXL_MAX_UNCOMPRESSED:
                raise UploadError("MXL archive expands to more than the allowed size")
            if info.compress_size and info.file_size / info.compress_size > config.MXL_MAX_RATIO:
                raise UploadError("MXL archive compression ratio is suspicious (possible zip bomb)")
        names = {i.filename for i in infos}
        root_name = None
        if "META-INF/container.xml" in names:
            container = parse_xml_safely(_read_member(zf, "META-INF/container.xml"))
            for el in container.iter():
                if el.tag.endswith("rootfile") and el.get("full-path"):
                    root_name = el.get("full-path")
                    break
        if root_name is None:
            candidates = [n for n in names if n.endswith((".xml", ".musicxml")) and not n.startswith("META-INF/")]
            if len(candidates) != 1:
                raise UploadError("Could not identify the score inside the MXL archive")
            root_name = candidates[0]
        if root_name not in names or not _safe_member_name(root_name):
            raise UploadError("MXL container points to a missing or unsafe score file")
        return _read_member(zf, root_name)


def _read_member(zf: zipfile.ZipFile, name: str) -> bytes:
    # Read with a hard cap regardless of what the header claims.
    with zf.open(name) as fh:
        out = fh.read(config.MXL_MAX_UNCOMPRESSED + 1)
    if len(out) > config.MXL_MAX_UNCOMPRESSED:
        raise UploadError("MXL member expands to more than the allowed size")
    return out


def load_score_upload(filename: str, data: bytes) -> bytes:
    """Validate a MusicXML/MXL upload and return plain MusicXML bytes."""
    check_size(data, config.MAX_SCORE_UPLOAD, "Score file")
    lower = (filename or "").lower()
    if data[:4] == b"PK\x03\x04":
        if not lower.endswith(".mxl"):
            raise UploadError("Compressed scores must use the .mxl extension")
        xml = read_mxl(data)
    elif lower.endswith((".musicxml", ".xml")):
        xml = data
    else:
        raise UploadError("Upload a MusicXML file (.musicxml, .xml or .mxl)")
    root = parse_xml_safely(xml)
    if root.tag == "score-timewise":
        raise UploadError("score-timewise MusicXML is not supported yet; export as partwise")
    if root.tag != "score-partwise":
        raise UploadError("File is XML but not a MusicXML score")
    return xml


AUDIO_SIGNATURES = {
    "mp3": lambda d: d[:3] == b"ID3" or (len(d) > 1 and d[0] == 0xFF and (d[1] & 0xE0) == 0xE0),
    "wav": lambda d: d[:4] == b"RIFF" and d[8:12] == b"WAVE",
    "ogg": lambda d: d[:4] == b"OggS",
    "m4a": lambda d: d[4:8] == b"ftyp",
}
AUDIO_MIME = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg", "m4a": "audio/mp4"}


def check_audio(filename: str, data: bytes) -> str:
    check_size(data, config.MAX_AUDIO_UPLOAD, "Audio file")
    ext = (filename or "").lower().rsplit(".", 1)[-1]
    if ext not in AUDIO_SIGNATURES:
        raise UploadError("Audio must be .mp3, .m4a, .ogg or .wav")
    if not AUDIO_SIGNATURES[ext](data):
        raise UploadError("Audio file content does not match its extension")
    return ext


def check_pdf(data: bytes) -> None:
    check_size(data, config.MAX_PDF_UPLOAD, "PDF")
    if data[:5] != b"%PDF-":
        raise UploadError("File is not a PDF")
