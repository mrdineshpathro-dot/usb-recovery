from __future__ import annotations

from pathlib import Path

from usb_recovery.cli.main import main
from usb_recovery.constants import EXIT_OK
from usb_recovery.forensics.dashboard import evidence_dashboard
from usb_recovery.forensics.inject import FailureInjector, malformed_image, simulate_disk_full
from usb_recovery.forensics.isolate import isolate_validate
from usb_recovery.forensics.manifest import provenance_chain, sign_manifest, verify_manifest
from usb_recovery.forensics.pipeline import run_pipeline, save_pipeline
from usb_recovery.forensics.plugin_caps import check_plugin_capabilities
from usb_recovery.forensics.regression import differential_results, golden_regression
from usb_recovery.forensics.validate import independent_validate
from usb_recovery.devices.image import ImageSource
from usb_recovery.exceptions import DestinationError, SourceAccessError
from usb_recovery.models import Candidate, RecoveryResult
from tests.fixtures.builder import minimal_jpeg


def _c(**kwargs) -> Candidate:
    base = dict(
        id="1",
        name="a.jpg",
        size=100,
        file_type="jpeg",
        mime="image/jpeg",
        method="carved",
        status="carved",
        source_offset=0,
        confidence=40,
    )
    base.update(kwargs)
    return Candidate(**base)  # type: ignore[arg-type]


def test_manifest_pipeline_validate_regression(tmp_path, fat_image):
    jpeg = minimal_jpeg()
    cand = _c(extra={"content": jpeg})
    path = sign_manifest({"image": "x.img", "files": [cand.name]}, tmp_path / "m.json", key=b"secret")
    check = verify_manifest(path, key=b"secret")
    assert check["ok"] is True
    assert check["hmac_match"] is True
    chain = provenance_chain(
        source_path="x.img",
        candidates=[cand],
        results=[RecoveryResult("1", "/tmp/a.jpg", "recovered", len(jpeg), "abc")],
        operations=[{"id": "scan", "profile": "quick"}],
    )
    assert chain["links"][0]["output"] == "/tmp/a.jpg"
    spec = save_pipeline(tmp_path / "p.json", params={"profile": "quick"})
    assert spec.is_file()
    summary = run_pipeline(fat_image["path"], tmp_path / "pipe", params={"profile": "quick"})
    assert summary["steps"]
    vals = independent_validate([cand, _c(id="2", extra={"content": b"xx"})])
    assert vals[0]["ok"] is True
    diff = differential_results([cand], [_c(id="z", name="z.jpg", source_offset=99)])
    assert diff["only_a"] and diff["only_b"]
    corpus = tmp_path / "corpus"
    from usb_recovery.devtools.corpus import Corpus

    c = Corpus(corpus)
    sample = tmp_path / "hello.bin"
    sample.write_bytes(b"hi")
    c.add_file(sample, label="hello", expected={"names": ["hello.bin"]})
    recovered = tmp_path / "rec"
    recovered.mkdir()
    (recovered / "hello.bin").write_bytes(b"hi")
    gold = golden_regression(corpus, recovered)
    assert gold["ok"] is True


def test_inject_isolate_plugins_dashboard(tmp_path, fat_image, capsys):
    bad = malformed_image(tmp_path / "bad.img", kind="truncated-fat")
    assert bad.stat().st_size < 512
    try:
        simulate_disk_full(tmp_path, needed=100, free=1)
        raised = False
    except DestinationError:
        raised = True
    assert raised
    with ImageSource(str(fat_image["path"])) as src:
        inj = FailureInjector(src, fail_offsets={0}, disconnect_after=5)
        try:
            inj.read(0, 512)
            failed = False
        except OSError:
            failed = True
        assert failed
        inj2 = FailureInjector(src, disconnect_after=0)
        try:
            inj2.read(512, 8)
            disconnected = False
        except SourceAccessError:
            disconnected = True
        assert disconnected
    jpeg = minimal_jpeg()
    isolated = isolate_validate("jpeg", jpeg)
    assert isolated.get("ok") is True
    assert isolated.get("isolated") is True
    plugin = tmp_path / "p.py"
    plugin.write_text('PLUGIN_API = "1.0"\nimport math\n')
    caps = check_plugin_capabilities(plugin, requested=["validate", "socket"])
    assert caps["compatible"] is True
    assert caps["allowed"] is False
    plugin.write_text('PLUGIN_API = "1.0"\nfrom usb_recovery.carving.validators import run_validator\n')
    caps2 = check_plugin_capabilities(plugin, requested=["validate"])
    assert caps2["allowed"] is True
    board = evidence_dashboard()
    assert board["features"]["total"] >= 200
    assert "jpeg" in board["validators"]
    code = main(["--json", "plan-scan", "--goal", "photos", "--size", "1000"])
    assert code == EXIT_OK
    code = main(["--json", "evidence-dashboard"])
    assert code == EXIT_OK
    expect = tmp_path / "exp.json"
    rec = tmp_path / "out"
    rec.mkdir()
    (rec / "a.bin").write_bytes(b"x")
    expect.write_text('[{"name": "a.bin"}]', encoding="utf-8")
    code = main(["--json", "scorecard", str(rec), "--expect-json", str(expect)])
    assert code == EXIT_OK
    img = tmp_path / "i.dd"
    img.write_bytes(b"\x00" * 64)
    man = tmp_path / "man.json"
    code = main(["sign-manifest", str(img), "--dest", str(man), "--key", "abc"])
    assert code == EXIT_OK
    assert Path(man).is_file()
    iso = tmp_path / "j.jpg"
    iso.write_bytes(jpeg)
    code = main(["--json", "isolate-parse", str(iso), "--type", "jpeg"])
    assert code == EXIT_OK
