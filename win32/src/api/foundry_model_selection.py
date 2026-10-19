"""Preserve downloaded model revisions without sacrificing the chosen hardware."""


def provider_priority(variant):
    runtime = variant.info.runtime
    if runtime.execution_provider == "CUDAExecutionProvider":
        return 0
    return {"GPU": 1, "NPU": 2, "CPU": 3}.get(str(runtime.device_type), 4)


def select_variant(catalog, model, device="auto"):
    variants = list(model.variants)
    # The alias generally exposes the newest revision. Older installed
    # revisions remain accessible through the SDK's public cache API.
    compatible_runtimes = {
        (str(v.info.runtime.device_type), v.info.runtime.execution_provider)
        for v in variants
    }
    cached_ids = set()
    cached_models = (
        catalog.get_cached_models() if hasattr(catalog, "get_cached_models") else []
    )
    for cached in cached_models:
        if cached.alias != model.alias:
            continue
        for variant in cached.variants:
            runtime = variant.info.runtime
            if (
                str(runtime.device_type),
                runtime.execution_provider,
            ) not in compatible_runtimes:
                continue
            if variant.is_cached:
                cached_ids.add(variant.id)
                if all(v.id != variant.id for v in variants):
                    variants.append(variant)
    if device == "cpu":
        variants = [v for v in variants if str(v.info.runtime.device_type) == "CPU"]
    if not variants:
        return None
    # Do not silently switch a CUDA user to a cached CPU model. Within the
    # same hardware tier, keep an installed revision before requesting a new one.
    best = min(provider_priority(v) for v in variants)
    candidates = [v for v in variants if provider_priority(v) == best]
    return next(
        (v for v in candidates if v.id in cached_ids or v.is_cached), candidates[0]
    )
