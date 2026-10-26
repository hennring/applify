from applify_analytics.definitions import defs


def test_asset_graph_covers_raw_to_intermediate() -> None:
    keys = {key.to_user_string() for key in defs.resolve_asset_graph().get_all_asset_keys()}
    assert {"raw/job_sightings", "staging/stg_raw__job_sightings"} <= keys
    assert "intermediate/int_job_lifespans" in keys
