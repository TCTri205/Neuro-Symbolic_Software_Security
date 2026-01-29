import json
from pathlib import Path

from src.core.interop import export_stub_ir


def test_export_stub_ir_writes_json(tmp_path: Path) -> None:
    input_path = tmp_path / "sample.c"
    input_path.write_text("int main(void) { return 0; }", encoding="utf-8")

    output_path = tmp_path / "ir.json"
    result = export_stub_ir(str(input_path), str(output_path))

    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data == result
    assert data["metadata"]["parser"] == "joern-stub"
