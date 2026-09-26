import pandas as pd

from mirsad.adapter import load, schema_report


def test_adapter_schema_report(tmp_path, cfg):
    df = pd.DataFrame({"sgd.id": ["A1", "A2"], "sgd.date": ["13-01-02", "13-01-09"], "importer.id": ["I1", "I2"],
                       "tariff.code": ["870323", "90111000"], "cif.value": ["100", "250"], "quantity": ["1", "5"]})
    f = tmp_path / "organiser.csv"
    df.to_csv(f, index=False)
    d = load(cfg, path=str(f))
    assert d.hs10.tolist() == ["0000870323", "0090111000"]  # zero-padded to 10 digits
    rep = schema_report(d, verbose=False)
    assert rep["mode"].startswith("unsupervised")
    assert rep["modules"]["features.unit_value (uv)"] is True
    assert rep["modules"]["model.classifier P(fraude)"] is False
    assert rep["modules"]["features.unit_value_kg (uv_kg)"] is False
    assert d.week.tolist() == [1, 2]
