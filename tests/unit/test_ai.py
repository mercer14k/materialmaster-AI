import json

import pytest

from materialmaster.ai.explanations import explain, validate_local_url
from materialmaster.domain.engine import analyze
from materialmaster.domain.generator import generate
from materialmaster.domain.validation import validate_rows


def evidence():
    rows = validate_rows(generate(40)[0]).records
    finding = analyze(rows)[0][0]
    return finding, [row.model_dump(mode="json") for row in rows if row.material_id in finding.material_ids]


def test_no_model_abstains():
    item, sources = evidence()
    answer, telemetry = explain(item, sources, None)
    assert answer.status == "abstained"
    assert telemetry["runtime"] == "disabled"


def test_missing_evidence_does_not_call_runtime():
    class Never:
        name, model = "test", "test"

        def complete(self, *_):
            pytest.fail("Runtime must not receive incomplete evidence")

    answer, _ = explain(evidence()[0], [], Never())
    assert answer.status == "abstained"


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        '{"status":"merged"}',
        json.dumps({"status": "explained", "summary": "See evidence", "evidence_ids": ["FAKE-ID"]}),
        json.dumps({"status": "explained", "summary": "No citation", "evidence_ids": []}),
    ],
)
def test_invalid_model_output_abstains_and_preserves_finding(response):
    class Bad:
        name, model = "test", "test"

        def complete(self, *_):
            return response, {}

    item, sources = evidence()
    before = item.model_dump_json()
    answer, telemetry = explain(item, sources, Bad())
    assert answer.status == "abstained"
    assert telemetry["retry_count"] == 1
    assert len(telemetry["validation_failures"]) == 2
    assert before == item.model_dump_json()


def test_valid_structured_output_and_telemetry():
    item, sources = evidence()

    class Good:
        name, model = "fixture", "fixture-v1"

        def complete(self, payload, schema):
            assert payload["allowed_evidence_ids"] == item.material_ids
            assert schema["additionalProperties"] is False
            return json.dumps(
                {
                    "status": "explained",
                    "summary": "Review the cited conflict.",
                    "evidence_ids": item.material_ids,
                }
            ), {"tokens": 25}

    answer, telemetry = explain(item, sources, Good())
    assert answer.status == "explained"
    assert telemetry["tokens"] == 25
    assert telemetry["tool_calls"] == []


def test_runtime_outage_abstains():
    class Unavailable:
        name, model = "fixture", "offline"

        def complete(self, *_):
            raise TimeoutError()

    assert explain(*evidence(), Unavailable())[0].status == "abstained"


@pytest.mark.parametrize(
    "url",
    ["https://api.example.com", "http://169.254.169.254", "file:///etc/passwd", "http://localhost.evil.test"],
)
def test_runtime_cannot_target_non_local_hosts(url):
    with pytest.raises(ValueError):
        validate_local_url(url)
