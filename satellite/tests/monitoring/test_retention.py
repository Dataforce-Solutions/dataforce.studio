"""Retention: the monitoring tables must not grow forever."""

import httpx
import respx

from agent.monitoring.greptime import (
    ALERTS_TABLE,
    INFERENCE_EVENTS_TABLE,
    LEGACY_METRIC_TABLES,
    OTEL_TRACES_TABLE,
    RESULTS_TABLE,
    GreptimeMonitoringStore,
)

_URL = "http://gt:4000/v1/sql"


def _statements(route: respx.Route) -> list[str]:
    """The SQL each call carried, url-decoded back into something readable."""
    from urllib.parse import unquote_plus

    return [
        unquote_plus(call.request.content.decode()) if call.request.content else ""
        for call in route.calls
    ]


@respx.mock
async def test_tables_are_created_with_their_retention() -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"output": []}))
    store = GreptimeMonitoringStore(
        host="gt", port=4000, events_ttl="7d", results_ttl="30d", alerts_ttl="30d"
    )

    await store._ensure_tables()

    sql = " ".join(_statements(route))
    # the fresh table declares it, the one that already exists is altered into it
    assert f"CREATE TABLE IF NOT EXISTS {RESULTS_TABLE}" in sql
    assert "WITH (ttl = '30d')" in sql
    assert f"ALTER TABLE {RESULTS_TABLE} SET 'ttl' = '30d'" in sql
    await store.aclose()


@respx.mock
async def test_raw_events_are_kept_shortest() -> None:
    """The traces table holds the model's own inputs and predictions."""
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"output": []}))
    store = GreptimeMonitoringStore(
        host="gt", port=4000, events_ttl="7d", results_ttl="30d", alerts_ttl="30d"
    )

    await store._ensure_tables()

    sql = " ".join(_statements(route))
    assert f"ALTER TABLE {INFERENCE_EVENTS_TABLE} SET 'ttl' = '7d'" in sql
    assert f"ALTER TABLE {ALERTS_TABLE} SET 'ttl' = '30d'" in sql
    await store.aclose()


@respx.mock
async def test_every_collector_table_gets_its_retention() -> None:
    """The collector's own tables were the gap: traces and the legacy metric tables grew
    forever while the docstring claimed otherwise. Now every table is covered."""
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"output": []}))
    store = GreptimeMonitoringStore(
        host="gt",
        port=4000,
        events_ttl="30d",
        results_ttl="30d",
        alerts_ttl="30d",
        traces_ttl="30d",
        metrics_ttl="7d",
    )

    await store._ensure_tables()

    sql = " ".join(_statements(route))
    assert f"ALTER TABLE {OTEL_TRACES_TABLE} SET 'ttl' = '30d'" in sql
    for table in LEGACY_METRIC_TABLES:
        # nothing writes these any more; a short TTL drains what a stand accumulated
        assert f"ALTER TABLE {table} SET 'ttl' = '7d'" in sql
    await store.aclose()


@respx.mock
async def test_a_failing_alter_does_not_stop_the_worker() -> None:
    """Retention is best-effort: an old GreptimeDB or a missing table must not block writes."""
    calls = {"n": 0}

    def answer(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 4:  # the first ALTER of the run
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"output": []})

    respx.post(_URL).mock(side_effect=answer)
    store = GreptimeMonitoringStore(
        host="gt", port=4000, results_ttl="30d", alerts_ttl="30d", traces_ttl="30d"
    )

    await store._ensure_tables()  # must not raise

    await store.aclose()


@respx.mock
async def test_without_a_setting_nothing_is_altered() -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"output": []}))
    store = GreptimeMonitoringStore(host="gt", port=4000)

    await store._ensure_tables()

    sql = " ".join(_statements(route))
    assert "ALTER" not in sql.upper()
    await store.aclose()
