"""A valid account cannot read a workspace that still has another active member."""
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app.core.cloud_auth import resolve_user


class MembershipConnection:
    def __init__(self, members: int):
        self.members = members
        self.calls = 0

    def execute(self, _query, _params):
        self.calls += 1
        return self

    def fetchall(self):
        return [("11111111-1111-1111-1111-111111111111",)]

    def fetchone(self):
        return (self.members,)


@pytest.mark.parametrize("members,allowed", [(1, True), (2, False), (0, False)])
def test_personal_workspace_requires_one_active_member(members, allowed):
    connection = MembershipConnection(members)

    @contextmanager
    def connect():
        yield connection

    with patch("app.core.cloud_auth.connect", connect):
        if allowed:
            owner = resolve_user("22222222-2222-2222-2222-222222222222")
            assert owner.tenant_id == "11111111-1111-1111-1111-111111111111"
        else:
            with pytest.raises(PermissionError):
                resolve_user("22222222-2222-2222-2222-222222222222")
    assert connection.calls == 2
