def test_deliberately_failing():
    """Temporary (TESS-11): proves a failing test turns CI red. Reverted right after."""
    assert 1 == 2
