from pathlib import Path

from sqlalchemy.engine import make_url

from hoophigher.app import HoopHigherApp
from hoophigher.config import settings


def test_app_metadata() -> None:
    app = HoopHigherApp(database_url="sqlite://")
    sqlite_path = Path(make_url(settings.database_url).database)

    assert app.TITLE == "Hoop Higher"
    assert "sqlite:///" in settings.database_url
    assert sqlite_path.parent.name == "var"
    assert sqlite_path.name == "hoophigher.db"
