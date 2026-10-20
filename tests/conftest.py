from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

from grizzl_e_local.client.versions import Version_01 as Client


@pytest.fixture
def session():
    post_mock = AsyncMock()
    post_mock.return_value.raise_for_status = MagicMock()
    post_mock.return_value.json = AsyncMock(return_value={})
    session_mock = AsyncMock()
    session_mock.post = post_mock
    session_mock.closed = False
    return session_mock


@pytest.fixture
async def client() -> AsyncGenerator[Client, None]:
    host = os.environ.get("GRIZZL_E_HOST", "http://192.168.4.1")
    async with Client(host) as c:
        await c.get_data()
        yield c
