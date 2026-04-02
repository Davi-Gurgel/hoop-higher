from hoophigher.app import HoopHigherApp
from hoophigher.config import settings


def test_app_metadata() -> None:
    app = HoopHigherApp()

    assert app.TITLE == "Hoop Higher"
    assert "sqlite:///" in settings.database_url
