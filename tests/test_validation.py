from validation import nickname_key, normalize_nickname, validate_nickname, validate_player_pin, validate_single_emoji


def test_nickname_normalization_and_case_key():
    assert normalize_nickname("  Teal   Duck ") == "Teal Duck"
    assert nickname_key("TEAL duck") == "teal duck"


def test_nickname_rules():
    assert validate_nickname("TealDuck")[0]
    assert validate_nickname("A" * 16)[0] is False
    assert validate_nickname("bad/route")[0] is False


def test_pin_is_exactly_four_digits():
    assert validate_player_pin("0918")[0]
    assert not validate_player_pin("918")[0]
    assert not validate_player_pin("abcd")[0]


def test_single_emoji():
    assert validate_single_emoji("🏈")[0]
    assert validate_single_emoji("👨‍👩‍👧‍👦")[0]
    assert not validate_single_emoji("🏈🏆")[0]
    assert not validate_single_emoji("T")[0]
