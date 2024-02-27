from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading, Markdown, MarkdownContext
from rich.text import Text


class SlimHeading(Heading):
    def on_enter(self, context: MarkdownContext) -> None:
        heading_level = int(self.tag[1:])  # e.g. self.tag == 'h1'

        context.enter_style(self.style_name)
        self.text = Text("#" * heading_level + " ", context.current_style)

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        yield self.text


class MarkdownWithSlimHeadings(Markdown):
    elements = Markdown.elements
    elements["heading_open"] = SlimHeading
