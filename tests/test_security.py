from security import hash_pin, session_token_hash, verify_pin


def test_pin_hash_round_trip():
    d = hash_pin("1234", "pepper")
    assert verify_pin("1234", "pepper", d.salt_b64, d.hash_b64)
    assert not verify_pin("1235", "pepper", d.salt_b64, d.hash_b64)
    assert not verify_pin("1234", "wrong", d.salt_b64, d.hash_b64)


def test_pin_salts_are_unique():
    a = hash_pin("1234", "pepper")
    b = hash_pin("1234", "pepper")
    assert a.salt_b64 != b.salt_b64
    assert a.hash_b64 != b.hash_b64


def test_session_hash_is_stable_and_peppered():
    assert session_token_hash("abc", "p") == session_token_hash("abc", "p")
    assert session_token_hash("abc", "p") != session_token_hash("abc", "q")
