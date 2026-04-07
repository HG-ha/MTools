import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';

import 'flet_gpt_markdown.dart';

class Extension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) {
    switch (control.type) {
      case "FletGptMarkdown":
        return FletGptMarkdownControl(control: control);
      default:
        return null;
    }
  }
}
