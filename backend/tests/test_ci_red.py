def test_deliberately_failing():
    """Temporary (TESS-11): proves a failing test turns CI red. Reverted right after."""
    expected_meetings = 3
    assert len(["mon", "wed"]) == expected_meetings
