from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import CodeBlock, Heading, Markdown, MarkdownContext
from rich.syntax import Syntax
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


# inspired by https://github.com/Textualize/rich/issues/3154
class NonWrappingCodeBlock(CodeBlock):
    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        # re-enable non-wrapping options locally for code blocks
        render_options = options.update(no_wrap=True, overflow="ignore")

        code = str(self.text).rstrip()
        syntax = Syntax(
            code,
            self.lexer_name,
            theme=self.theme,
            word_wrap=False,
            padding=0,
        )
        return syntax.highlight(code).__rich_console__(console, render_options)


class RuyiStyledMarkdown(Markdown):
    elements = Markdown.elements
    elements["fence"] = NonWrappingCodeBlock
    elements["heading_open"] = SlimHeading

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        # we have to undo the ruyi-global console's non-wrapping setting
        # for proper CLI rendering of long lines
        render_options = options.update(no_wrap=False, overflow="fold")
        return super().__rich_console__(console, render_options)
