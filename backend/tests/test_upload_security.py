"""Hostile and malformed uploads."""
import io
import zipfile

import pytest

from bvc import config
from bvc.safe_upload import UploadError, check_audio, check_pdf, load_score_upload
from conftest import fixture_bytes

GOOD = fixture_bytes()


def mxl(members: dict, compression=zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


CONTAINER = (b'<?xml version="1.0"?><container><rootfiles><rootfile full-path="score.musicxml"/>'
             b"</rootfiles></container>")


def test_valid_musicxml_and_mxl_accepted():
    assert load_score_upload("a.musicxml", GOOD) == GOOD
    assert load_score_upload("a.mxl", mxl({"META-INF/container.xml": CONTAINER, "score.musicxml": GOOD})) == GOOD


def test_public_doctype_is_allowed():
    doc = GOOD.replace(b"<score-partwise", b'<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 '
                       b'Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\n<score-partwise', 1)
    assert load_score_upload("a.xml", doc)


def test_external_entity_rejected():
    xxe = (b'<?xml version="1.0"?><!DOCTYPE s [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
           b"<score-partwise><work><work-title>&x;</work-title></work></score-partwise>")
    with pytest.raises(UploadError, match="safety"):
        load_score_upload("a.musicxml", xxe)


def test_billion_laughs_rejected():
    bomb = (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "lol"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">'
            b"]><score-partwise>&b;</score-partwise>")
    with pytest.raises(UploadError, match="safety"):
        load_score_upload("a.musicxml", bomb)


def test_zip_bomb_rejected(monkeypatch):
    big = b"0" * (config.MXL_MAX_UNCOMPRESSED + 10)
    with pytest.raises(UploadError):
        load_score_upload("a.mxl", mxl({"score.musicxml": big}))


def test_high_compression_ratio_rejected():
    with pytest.raises(UploadError, match="ratio"):
        load_score_upload("a.mxl", mxl({"score.musicxml": b"<a>" + b" " * 2_000_000 + b"</a>"}))


@pytest.mark.parametrize("evil", ["../score.musicxml", "/etc/score.musicxml", "a/../../score.musicxml",
                                  "C:\\score.musicxml", "a\\..\\score.musicxml"])
def test_path_traversal_member_rejected(evil):
    with pytest.raises(UploadError, match="unsafe"):
        load_score_upload("a.mxl", mxl({evil: GOOD}))


def test_container_pointing_outside_rejected():
    bad = CONTAINER.replace(b"score.musicxml", b"../../etc/passwd")
    with pytest.raises(UploadError):
        load_score_upload("a.mxl", mxl({"META-INF/container.xml": bad, "score.musicxml": GOOD}))


def test_wrong_types_rejected():
    for name, data in [("a.pdf", GOOD), ("a.musicxml", b"<html></html>"), ("a.musicxml", b"not xml"),
                       ("a.xml", b""), ("a.musicxml", b"<score-timewise/>"),
                       ("a.musicxml", mxl({"score.musicxml": GOOD}))]:
        with pytest.raises(UploadError):
            load_score_upload(name, data)


def test_oversized_score_rejected():
    with pytest.raises(UploadError, match="larger"):
        load_score_upload("a.musicxml", b" " * (config.MAX_SCORE_UPLOAD + 1))


def test_audio_and_pdf_checked_by_content():
    assert check_audio("t.mp3", b"ID3\x04" + b"\x00" * 100) == "mp3"
    with pytest.raises(UploadError):
        check_audio("t.mp3", b"%PDF-1.4 not audio")
    with pytest.raises(UploadError):
        check_audio("t.exe", b"MZ")
    check_pdf(b"%PDF-1.7\n...")
    with pytest.raises(UploadError):
        check_pdf(b"<html>")


def test_shell_metacharacters_in_filename_are_never_used(client):
    """Uploaded names are not used for storage or commands; files get random server names."""
    from conftest import login
    from bvc import worker
    login(client, "director")
    r = client.post("/api/songs", files={"score": ("$(rm -rf ~); `x`.musicxml", GOOD, "application/xml")},
                    data={"rights_note": "test"})
    assert r.status_code == 200
    stored = [p.name for p in config.STORAGE_DIR.rglob("*") if p.is_file()]
    assert all("rm" not in n and "$" not in n for n in stored)
    worker.run_once()
