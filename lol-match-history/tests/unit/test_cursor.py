import pytest

from app.services.cursor import InvalidCursor, decode_cursor, encode_cursor


def test_cursor_roundtrip_and_tamper_detection():
    secret = "test-secret"
    token = encode_cursor(1763712000000, "VN2_492817261", secret)
    assert decode_cursor(token, secret) == (1763712000000, "VN2_492817261")

    with pytest.raises(InvalidCursor):
        decode_cursor(token, "other-secret")
    with pytest.raises(InvalidCursor):
        decode_cursor(token[:-2] + "AA", secret)
    with pytest.raises(InvalidCursor):
        decode_cursor("not-valid", secret)
