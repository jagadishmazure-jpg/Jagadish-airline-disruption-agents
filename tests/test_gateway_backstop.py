"""Gateway gaps found in review.

The regex gateway blocked writes but had no view allowlist, so base tables
(including passenger names) and the schema table were readable, and a
caller-supplied LIMIT skipped the 100-row cap. Both are now enforced.
"""
import pytest

from airops import telemetry, views


@pytest.fixture()
def conn():
    c = telemetry.build_db()
    views.create_views(c)
    yield c
    c.close()


@pytest.mark.parametrize("sql", [
    "SELECT name FROM passengers",
    "SELECT name FROM sqlite_master",
    'SELECT * FROM v_disrupted_flights, "passengers"',
    "SELECT * FROM/**/baggage",
])
def test_non_view_reads_are_denied(conn, sql):
    with pytest.raises(views.GatewayError, match=r"SEC-SELECT-04"):
        views.run_query(conn, sql)


def test_caller_limit_cannot_exceed_cap(conn):
    rows = views.run_query(conn, "SELECT * FROM v_disrupted_flights a, v_crew_status b LIMIT 100000")
    assert len(rows) <= 100


def test_authorizer_is_removed_after_the_query(conn):
    views.run_query(conn, "SELECT * FROM v_crew_status")
    assert conn.execute("SELECT count(*) FROM passengers").fetchone()[0] > 0
