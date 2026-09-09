from app.vision.perception import PerceptionSnapshot, state_changed


def test_snapshot_difference_is_structured():
    before = PerceptionSnapshot(1.0, active_window="One", confidence="high")
    after = PerceptionSnapshot(2.0, active_window="Two", confidence="high")
    assert state_changed(before, after)
    assert after.as_dict()["active_window"] == "Two"
