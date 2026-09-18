from uuid import uuid4

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_jwt_round_trip() -> None:
    password = "a-strong-demo-password"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)

    user_id = uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id
