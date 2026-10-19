import json
import time

import pytest
from PySide6.QtWidgets import QApplication

from supermenu_core.api import lmstudio_provenance as provenance
from supermenu_core.api.model_capabilities import parse_lmstudio_model_catalog
from supermenu_core.ui.controls import ChoiceBox
from supermenu_core.ui.model_catalog import (
    clear_model_provenance,
    model_summary,
    populate_model_catalog,
    selected_model_id,
    selected_model_target,
    restore_model_target,
    target_key,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_same_model_on_two_devices_keeps_both_origins_and_loaded_snapshot():
    models = parse_lmstudio_model_catalog(
        {
            "models": [
                {
                    "key": "qwen",
                    "display_name": "Qwen",
                    "loaded_instances": [{"id": "qwen-mac"}, {"id": "qwen-pc"}],
                }
            ]
        }
    )
    available = [
        {"modelKey": "qwen", "deviceIdentifier": None},
        {"modelKey": "qwen", "deviceIdentifier": "mac-studio"},
        {"modelKey": "unrelated", "displayName": "Qwen", "deviceIdentifier": "other"},
    ]
    loaded = [
        {
            "modelKey": "qwen",
            "identifier": "qwen-mac",
            "deviceIdentifier": "mac-studio",
        },
        {"modelKey": "qwen", "identifier": "qwen-pc", "deviceIdentifier": None},
    ]
    provenance.enrich_provenance(models, available, loaded)
    assert [model["id"] for model in models] == ["qwen", "qwen-mac", "qwen-pc"]
    assert models[0]["sources"] == [None, "mac-studio"]
    assert models[1]["loaded_sources"] == ["mac-studio"]
    assert models[2]["loaded_sources"] == [None]
    assert "Qwen" not in models[0]["identifiers"]
    assert "LM Studio choisit" in model_summary(models[0], lmstudio=True)


@pytest.mark.parametrize(
    "field, expected",
    [
        ({}, []),
        ({"deviceIdentifier": None}, [None]),
        ({"deviceIdentifier": "pc"}, ["pc"]),
        ({"deviceIdentifier": False}, []),
        ({"deviceIdentifier": ""}, []),
    ],
)
def test_only_explicit_device_metadata_confirms_local_or_remote(field, expected):
    details = [{"id": "qwen"}]
    provenance.enrich_provenance(details, [{"modelKey": "qwen", **field}], [])
    assert details[0]["sources"] == expected


def test_openai_compatible_instance_id_matches_sdk_model_key():
    models = [{"id": "my-instance"}]
    provenance.enrich_provenance(
        models,
        [],
        [
            {
                "identifier": "my-instance",
                "modelKey": "qwen",
                "deviceIdentifier": "mac",
            },
        ],
    )
    assert models[0]["sources"] == ["mac"]


def test_picker_preserves_exact_api_id_across_refresh_manual_entry_and_disconnect(app):
    combo = ChoiceBox()
    combo.setEditable(True)
    combo.setPlaceholderText("Sélectionnez ou entrez un modèle")
    combo.setEditText("remote-qwen")
    models = [
        {"id": "local-qwen", "sources": [None]},
        {"id": "remote-qwen", "sources": ["mac"]},
    ]
    populate_model_catalog(combo, models, lmstudio=True)
    assert "Choix automatique" in combo.currentText()
    combo.setCurrentIndex(1)
    assert selected_model_target(combo)["device"] == "mac"
    assert "LM Link" in combo.currentText()
    assert selected_model_id(combo) == "remote-qwen"
    populate_model_catalog(combo, models[:1], lmstudio=True)
    assert selected_model_id(combo) == "remote-qwen"  # Never switch to local silently.
    populate_model_catalog(combo, models, lmstudio=True)
    assert "LM Link" in combo.currentText()
    clear_model_provenance(combo)
    assert combo.currentText() == selected_model_id(combo) == "remote-qwen"
    combo.setEditText("manual-model")
    assert selected_model_id(combo) == "manual-model"


def test_duplicate_route_ids_offer_independent_devices(app):
    combo = ChoiceBox()
    combo.setEditable(True)
    result = populate_model_catalog(
        combo,
        [
            {"id": "qwen", "sources": [None]},
            {"id": "qwen", "sources": ["mac"]},
        ],
        lmstudio=True,
    )
    assert combo.count() == 2
    assert "LM Link" not in combo.itemText(0)
    assert "LM Link" in combo.itemText(1)
    assert selected_model_target(combo)["device"] is None
    combo.setCurrentIndex(1)
    assert selected_model_target(combo)["device"] == "mac"
    assert len(result) == 2


def test_older_server_does_not_claim_models_are_local(app):
    combo = ChoiceBox()
    combo.setEditable(True)
    populate_model_catalog(combo, [{"id": "qwen"}], lmstudio=True)
    assert "Choix automatique" in combo.currentText()
    assert "LM Studio choisit" in model_summary({"id": "qwen"}, lmstudio=True)
    assert model_summary({"id": "qwen"}, lmstudio=False) == ""


def test_sdk_read_protocol_uses_configured_host_token_and_closes(monkeypatch):
    import websocket

    class Socket:
        sent = []
        closed = False
        replies = iter(
            [
                {"success": True},
                {"type": "notice"},
                {
                    "type": "rpcResult",
                    "callId": 1,
                    "result": [{"deviceIdentifier": None}],
                },
            ]
        )

        def send(self, message):
            self.sent.append(json.loads(message))

        def recv(self):
            return json.dumps(next(self.replies))

        def settimeout(self, timeout):
            assert 0 < timeout <= 3

        def shutdown(self):
            self.closed = True

    socket = Socket()
    connections = []

    def connect(url, **kwargs):
        connections.append((url, kwargs))
        return socket

    monkeypatch.setattr(websocket, "create_connection", connect)
    token = "sk-lm-abcdefgh:abcdefghijklmnopqrst"
    result = provenance._read_catalog(
        "https://server:1234/prefix",
        "system",
        "listDownloadedModels",
        provenance._auth_message(token),
        time.monotonic() + 3,
    )
    assert result == [{"deviceIdentifier": None}]
    assert connections[0][0] == "wss://server:1234/prefix/system"
    assert connections[0][1]["redirect_limit"] == 0
    assert socket.sent[0] == dict(
        authVersion=1, clientIdentifier="abcdefgh", clientPasskey="abcdefghijklmnopqrst"
    )
    assert socket.sent[1] == dict(
        type="rpcCall", endpoint="listDownloadedModels", callId=1
    )
    assert socket.closed


def test_metadata_failure_preserves_rest_and_partial_results(monkeypatch):
    def read(_base, namespace, *_args):
        if namespace == "system":
            return [{"modelKey": "qwen", "deviceIdentifier": "pc"}]
        raise TimeoutError()

    monkeypatch.setattr(provenance, "_read_catalog", read)
    monkeypatch.setattr(
        "supermenu_core.api.lmstudio_transport.device_names", lambda *_a: {}
    )
    available, loaded = provenance.fetch_provenance("http://localhost:1234")
    assert available[0]["deviceIdentifier"] == "pc"
    assert loaded == []
    assert provenance.fetch_provenance(
        "http://localhost:1234", "unsupported-token"
    ) == ([], [])


def test_catalog_discovery_enriches_without_changing_routing_id(monkeypatch):
    from supermenu_core.api import openai_client

    class Response:
        status_code = 200

        def json(self):
            return {"models": [{"key": "qwen"}]}

    monkeypatch.setattr(openai_client._session(), "get", lambda *_a, **_kw: Response())
    monkeypatch.setattr(
        provenance,
        "fetch_provenance",
        lambda *_a, **_kw: (
            [{"modelKey": "qwen", "deviceIdentifier": "mac"}],
            [],
        ),
    )
    ok, models = openai_client.OpenAIClient.fetch_available_model_details(
        "http://localhost:1234",
        endpoint_type="lmstudio",
    )
    assert ok
    assert models[0]["id"] == "qwen"
    assert models[0]["sources"] == ["mac"]


def test_named_remote_selection_survives_refresh_and_offline(app):
    combo = ChoiceBox()
    combo.setEditable(True)
    combo.addItem("gemma", "gemma")
    target = {"provider": "custom", "model": "gemma", "device": "opaque-device-id"}
    restore_model_target(combo, target)
    models = [
        {
            "id": "gemma",
            "sources": [None, "opaque-device-id"],
            "device_names": {"opaque-device-id": "Serveur Apple"},
        }
    ]
    catalog = populate_model_catalog(combo, models, lmstudio=True)
    assert "Serveur Apple" in combo.currentText()
    assert "opaque-device-id" not in combo.currentText()
    assert target_key(selected_model_target(combo)) == target_key(target)
    assert catalog[target_key(target)]["device"] == "opaque-device-id"
    populate_model_catalog(combo, [{"id": "gemma", "sources": [None]}], lmstudio=True)
    assert "indisponible" in combo.currentText()
    assert selected_model_target(combo)["device"] == "opaque-device-id"
