import pytest
from pydantic import ValidationError

from tessera.main import create_app


@pytest.mark.parametrize("value", [None, ""], ids=["unset", "empty"])
def test_startup_fails_fast_without_jwt_secret_key(env, value):
    if value is None:
        env.delenv("JWT_SECRET_KEY")
    else:
        env.setenv("JWT_SECRET_KEY", value)

    with pytest.raises(ValidationError, match="jwt_secret_key") as error:
        create_app()

    # The error must not echo the other settings' values: they can be secrets.
    assert "input_value" not in str(error.value)
