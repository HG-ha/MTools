import 'package:flet/flet.dart';
import 'package:flutter/material.dart';
import 'package:gpt_markdown/gpt_markdown.dart';

class FletGptMarkdownControl extends StatelessWidget {
  final Control control;

  const FletGptMarkdownControl({
    super.key,
    required this.control,
  });

  @override
  Widget build(BuildContext context) {
    final String text = control.getString("value", "")!;
    final bool selectable = control.getBool("selectable", true)!;
    final bool useDollarSignsForLatex =
        control.getBool("use_dollar_signs_for_latex", true)!;

    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    final mdThemeData = GptMarkdownThemeData(
      brightness: theme.brightness,
      highlightColor: isDark
          ? Colors.yellow.shade700.withValues(alpha: 0.3)
          : Colors.yellow.shade100,
      linkColor: theme.colorScheme.primary,
      linkHoverColor: theme.colorScheme.primary.withValues(alpha: 0.7),
      hrLineColor: theme.dividerColor,
    );

    final codeBlockBuilder = (
      BuildContext ctx,
      String name,
      String code,
      bool closed,
    ) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        margin: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: isDark ? Colors.grey.shade900 : Colors.grey.shade100,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isDark
                ? Colors.grey.shade700
                : Colors.grey.shade300,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (name.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      name,
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark
                            ? Colors.grey.shade400
                            : Colors.grey.shade600,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    Icon(
                      Icons.code,
                      size: 14,
                      color: isDark
                          ? Colors.grey.shade500
                          : Colors.grey.shade500,
                    ),
                  ],
                ),
              ),
            SelectableText(
              code,
              style: TextStyle(
                fontFamily: 'Consolas, Monaco, monospace',
                fontSize: 13,
                height: 1.5,
                color: isDark ? Colors.grey.shade200 : Colors.grey.shade800,
              ),
            ),
          ],
        ),
      );
    };

    Widget mdWidget = GptMarkdownTheme(
      data: mdThemeData,
      child: GptMarkdown(
        text,
        style: theme.textTheme.bodyMedium?.copyWith(
          color: theme.colorScheme.onSurface,
          height: 1.6,
        ),
        useDollarSignsForLatex: useDollarSignsForLatex,
        codeBuilder: codeBlockBuilder,
      ),
    );

    if (selectable) {
      mdWidget = SelectionArea(child: mdWidget);
    }

    return LayoutControl(
      control: control,
      child: mdWidget,
    );
  }
}
