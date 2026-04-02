from textual.app import App
from textual.screen import Screen
from textual.widgets import Footer, Header, Label


class HomeScreen(Screen[None]):
    """Initial placeholder screen for the MVP scaffold."""

    def compose(self):
        yield Header(show_clock=False)
        yield Label("Hoop Higher scaffold is ready.")
        yield Footer()


class HoopHigherApp(App[None]):
    """Base Textual application for the project scaffold."""

    CSS_PATH = "tui/styles.tcss"
    TITLE = "Hoop Higher"
    SUB_TITLE = "Project scaffold"

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())
