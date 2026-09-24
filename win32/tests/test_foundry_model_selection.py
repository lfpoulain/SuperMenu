from types import SimpleNamespace

from src.api.foundry_model_selection import select_variant


def variant(alias, version, provider, cached):
    result = SimpleNamespace(
        alias=alias,
        id=f"{alias}-{provider}:{version}",
        is_cached=cached,
        info=SimpleNamespace(
            runtime=SimpleNamespace(
                execution_provider=provider,
                device_type="CPU" if provider == "CPUExecutionProvider" else "GPU",
            )
        ),
    )
    result.variants = [result]
    return result


def test_new_catalog_revision_reuses_cached_cuda_for_text_and_voice():
    for alias in ("qwen3.5-4b", "qwen3.5-9b", "nemotron-3.5-asr-streaming-0.6b"):
        old = variant(alias, 3, "CUDAExecutionProvider", True)
        latest = variant(alias, 4, "CUDAExecutionProvider", False)
        cpu = variant(alias, 3, "CPUExecutionProvider", True)
        catalog = SimpleNamespace(get_cached_models=lambda: [old, cpu])
        model = SimpleNamespace(alias=alias, variants=[latest, cpu])
        for _restart in range(2):
            assert select_variant(catalog, model) is old
            assert select_variant(catalog, model, "cpu") is cpu
        assert model.variants == [latest, cpu]


def test_cached_cpu_never_overrides_available_cuda():
    gpu = variant("qwen", 4, "CUDAExecutionProvider", False)
    cpu = variant("qwen", 3, "CPUExecutionProvider", True)
    model = SimpleNamespace(alias="qwen", variants=[gpu, cpu])
    catalog = SimpleNamespace(get_cached_models=lambda: [cpu])
    assert select_variant(catalog, model) is gpu


def test_cached_revision_of_another_alias_is_ignored():
    gpu = variant("qwen", 4, "CUDAExecutionProvider", False)
    unrelated = variant("nemotron", 3, "CUDAExecutionProvider", True)
    catalog = SimpleNamespace(get_cached_models=lambda: [unrelated])
    assert select_variant(catalog, SimpleNamespace(alias="qwen", variants=[gpu])) is gpu


def test_cached_hardware_no_longer_available_is_not_selected():
    cpu = variant("qwen", 3, "CPUExecutionProvider", True)
    gpu = variant("qwen", 3, "CUDAExecutionProvider", True)
    catalog = SimpleNamespace(get_cached_models=lambda: [gpu, cpu])
    assert select_variant(catalog, SimpleNamespace(alias="qwen", variants=[cpu])) is cpu
