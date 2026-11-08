import pytest

import store
from login import UserManager


@pytest.fixture
def repo(tmp_path):
    instance = store.Store(
        mode="production", db_path=tmp_path / "xun.db", data_dir=tmp_path / "data"
    )
    yield instance
    instance.close()


def make_manager(repo):
    return UserManager(repo)


def test_create_user_and_authenticate(repo):
    manager = make_manager(repo)
    ok, message = manager.create_user("admin", "password123", "admin")
    assert ok
    assert message == "Usuario creado exitosamente."

    assert manager.authenticate("admin", "password123") == "admin"
    assert manager.authenticate("admin", "wrongpass") is None
    assert manager.authenticate("ghost", "password123") is None


def test_create_user_rejects_duplicate(repo):
    manager = make_manager(repo)
    assert manager.create_user("admin", "password123", "admin")[0]
    assert not manager.create_user("admin", "other12345", "cashier")[0]


def test_change_password_and_delete(repo):
    manager = make_manager(repo)
    assert manager.create_user("cajero", "oldpass1234", "cashier")[0]

    ok, _ = manager.change_password("cajero", "newpass1234")
    assert ok
    assert manager.authenticate("cajero", "newpass1234") == "cashier"
    assert manager.authenticate("cajero", "oldpass1234") is None

    ok, _ = manager.delete_user("cajero")
    assert ok
    assert manager.authenticate("cajero", "newpass1234") is None
    assert manager.list_users() == {}


def test_cannot_delete_last_admin(repo):
    manager = make_manager(repo)
    assert manager.create_user("admin", "password123", "admin")[0]

    ok, message = manager.delete_user("admin")
    assert not ok
    assert "último" in message
    assert manager.authenticate("admin", "password123") == "admin"
