import flet as ft


@ft.control("FletGptMarkdown")
class FletGptMarkdown(ft.LayoutControl):
    """
    Markdown control with LaTeX rendering support,
    powered by the gpt_markdown Flutter package.
    """

    value: str = ""
    selectable: bool = True
    use_dollar_signs_for_latex: bool = True
