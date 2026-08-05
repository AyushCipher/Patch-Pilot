from textutils import last_n_chars


def test_last_three():
    assert last_n_chars("hello world", 3) == "rld"


def test_last_one():
    assert last_n_chars("python", 1) == "n"


def test_last_five():
    assert last_n_chars("patchpilot", 5) == "pilot"
