from app.core.product_config import list_product_configs, load_product_config


def test_load_vxvue_product_config():
    config = load_product_config("vxvue")
    assert config is not None
    assert config.product == "VXvue"
    assert config.specification.source == "alm_crawler"
    assert "(사양서) VXvue 사양서*.pdf" in config.specification.filename_patterns
    assert config.testcase.source == "manual"


def test_load_missing_product_config_returns_none():
    assert load_product_config("does-not-exist") is None


def test_list_product_configs_includes_vxvue():
    configs = list_product_configs()
    assert any(c.product == "VXvue" for c in configs)
