import flet as ft

from flet_gpt_markdown import FletGptMarkdown


def main(page: ft.Page):
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    page.add(

                ft.Container(height=150, width=300, alignment = ft.Alignment.CENTER, bgcolor=ft.Colors.PURPLE_200, content=FletGptMarkdown(
                    tooltip="My new FletGptMarkdown Control tooltip",
                    value = "My new FletGptMarkdown Flet Control",
                ),),

    )


ft.run(main)
