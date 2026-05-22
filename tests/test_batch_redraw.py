"""Phase 4: batch redraw mock-mode end-to-end."""
import json
import pathlib

from src.transcribe import RedrawEngine, RedrawParams, run_quality_loop, export_batch_zip


def test_redraw_3_items_in_mock_mode(tmp_path: pathlib.Path):
    work = tmp_path / "work"
    engine = RedrawEngine(work)

    # Source files: 3 fake PNGs (any bytes, redraw engine just copies in mock mode)
    sources: list[str] = []
    for i in range(3):
        s = tmp_path / f"src_{i}.png"
        s.write_bytes(b"\x89PNG\r\n\x1a\nFAKE" + bytes([i]))
        sources.append(str(s))

    params = RedrawParams(style="ancient_3d_guoman", genre="ancient", aspect_ratio="9:16")
    params.refs.text_prompt = "保留主体，画风转为古风 3D 国漫"

    records = []
    for i, src in enumerate(sources):
        rec = run_quality_loop(engine, i + 1, src, params)
        records.append(rec)

    assert len(records) == 3
    for rec in records:
        assert pathlib.Path(rec.final_output).exists()
        assert rec.overall > 0
        assert set(rec.final_scores.keys()) >= {"structure", "style"}
        # Mock backend never improves, so passed status is honest about it
        # (still must produce a valid file)


def test_export_zip_contains_items(tmp_path: pathlib.Path):
    work = tmp_path / "work"
    engine = RedrawEngine(work)
    params = RedrawParams()
    items = []
    for i in range(2):
        s = tmp_path / f"s{i}.png"
        s.write_bytes(b"\x89PNG\r\n\x1a\nX")
        rec = run_quality_loop(engine, i + 1, str(s), params)
        items.append(rec.to_dict())

    zip_path = tmp_path / "out.zip"
    export_batch_zip(99, items, zip_path)
    assert zip_path.exists()
    import zipfile

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "manifest.json" in names
    assert any(n.startswith("items/item_0001") for n in names)
