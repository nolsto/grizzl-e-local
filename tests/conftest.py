from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def session():
    post_mock = AsyncMock()
    post_mock.return_value.raise_for_status = MagicMock()
    post_mock.return_value.json = AsyncMock(return_value={})
    session_mock = AsyncMock()
    session_mock.post = post_mock
    session_mock.closed = False
    return session_mock
