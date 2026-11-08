import config


def test_mode_is_saved_and_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv(config.MODE_ENV, raising=False)

    assert config.get_mode() is None
    assert config.get_mode("production") == "production"

    config.save_mode("kiosk")
    assert config.get_mode() == "kiosk"

    path = tmp_path / "config" / "xun-pos" / "config.json"
    assert path.exists()
    assert (path.stat().st_mode & 0o777) == 0o600


def test_env_var_overrides_saved_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    config.save_mode("production")
    monkeypatch.setenv(config.MODE_ENV, "demo")
    assert config.get_mode() == "demo"


def test_demo_uses_its_own_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert config.data_dir("demo") != config.data_dir("production")
    assert config.data_dir("demo").name == "demo"


def test_seed_demo_data(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    directory = config.seed_demo_data()
    assert (directory / "productos.csv").exists()
    assert (directory / "settings.json").exists()
    assert (directory / "ventas.csv").read_text(encoding="utf-8").startswith(
        "fecha_hora"
    )
    assert not (directory / ".credentials").exists()


def test_copy_legacy_data_skips_demo(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "productos.csv").write_text(
        "codigo,nombre,precio,inventario\n", encoding="utf-8"
    )
    monkeypatch.setattr(config, "app_dir", lambda: legacy)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    copied = config.copy_legacy_data("production")
    assert copied == ["productos.csv"]
    assert (config.data_dir("production") / "productos.csv").exists()
    assert config.copy_legacy_data("demo") == []
