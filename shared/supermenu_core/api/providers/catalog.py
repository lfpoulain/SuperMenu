#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Model discovery for custom endpoints: Ollama, LM Studio or OpenAI-compatible."""

import logging

import requests

from supermenu_core.api.model_capabilities import parse_lmstudio_model_catalog
from supermenu_core.api.providers.common import log, models_base_url
from supermenu_core.api.providers.ollama import looks_like_ollama_endpoint


def basic_model_details(model_id):
    return {
        "id": model_id,
        "identifiers": [model_id],
        "reasoning_supported": None,
        "reasoning_options": [],
        "reasoning_default": None,
    }


def fetch_model_details(
    session, endpoint_url, api_key=None, timeout=10, endpoint_type=None
):
    """Fetch a catalog with an optional custom-endpoint credential."""
    try:
        headers = {"Content-Type": "application/json"}
        endpoint_api_key = str(api_key or "").strip()
        if endpoint_api_key:
            headers["Authorization"] = f"Bearer {endpoint_api_key}"
        endpoint_type = (endpoint_type or "").strip().lower()
        is_ollama = endpoint_type == "ollama" or (
            endpoint_type != "lmstudio"
            and looks_like_ollama_endpoint(endpoint_url)
        )
        candidates = []
        base_url = models_base_url(
            endpoint_url, is_ollama, lmstudio=endpoint_type == "lmstudio"
        )
        if is_ollama:
            candidates.append(f"{base_url}/api/tags")
        elif endpoint_type == "lmstudio":
            candidates.append(f"{base_url}/api/v1/models")
        candidates.append(f"{base_url}/v1/models")
        if not is_ollama:
            candidates.append(f"{base_url}/api/tags")

        last_error = None
        for models_url in candidates:
            response = session.get(
                models_url, headers=headers, timeout=timeout
            )

            if response.status_code != 200:
                last_error = f"Erreur {response.status_code}: {response.text}"
                continue

            data = response.json()
            model_details = []

            if models_url.endswith("/api/v1/models"):
                model_details = parse_lmstudio_model_catalog(data)

            if (
                not model_details
                and "data" in data
                and isinstance(data["data"], list)
            ):
                for model_info in data["data"]:
                    if isinstance(model_info, dict):
                        model_id = model_info.get("id") or model_info.get("name")
                        if model_id:
                            model_details.append(
                                basic_model_details(model_id)
                            )

            if (
                not model_details
                and "models" in data
                and isinstance(data["models"], list)
            ):
                for model_info in data["models"]:
                    if isinstance(model_info, dict):
                        model_id = (
                            model_info.get("key")
                            or model_info.get("name")
                            or model_info.get("id")
                        )
                        if model_id:
                            model_details.append(
                                basic_model_details(model_id)
                            )

            if model_details:
                if endpoint_type == "lmstudio":
                    # Resolved at call time, as before: the LM Link catalog is
                    # read over a WebSocket and tests patch it on its module.
                    from ..lmstudio_provenance import (
                        enrich_provenance, fetch_provenance,
                    )
                    available, loaded = fetch_provenance(
                        base_url, endpoint_api_key or None, timeout=timeout,
                    )
                    enrich_provenance(model_details, available, loaded)
                model_ids = [model["id"] for model in model_details]
                log(f"Modèles récupérés avec succès: {model_ids}", logging.INFO)
                return True, model_details

            last_error = "Aucun modèle trouvé dans la réponse de l'API"

        return False, last_error or "Aucun modèle trouvé dans la réponse de l'API"

    except requests.exceptions.Timeout:
        return False, "Timeout lors de la connexion au serveur"
    except requests.exceptions.ConnectionError:
        return False, "Impossible de se connecter au serveur"
    except Exception as e:
        return False, f"Erreur: {str(e)}"
