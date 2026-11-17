def test_protection_probe_fails_on_purpose():
    """Temporary (TESS-10): a red CI run must block merging. This PR is closed, never merged."""
    expected_meetings = 3
    assert len(["mon", "wed"]) == expected_meetings
