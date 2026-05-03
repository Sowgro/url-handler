#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
import json
import os
import re

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
MATCHERS = ["startswith", "contains", "endswith"]


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def app_info_to_exec(app_info):
    cmdline = app_info.get_commandline() or (app_info.get_executable() + ' %U')
    # Replace desktop-file URL/file field codes with the {} placeholder url-handler.py expects
    cmdline = re.sub(r'\s*%[uUfF]\s*', ' {}', cmdline)
    cmdline = re.sub(r'%[a-zA-Z]', '', cmdline).strip()
    if '{}' not in cmdline:
        cmdline += ' {}'
    return cmdline


def open_app_chooser(parent_win, on_chosen):
    dialog = Gtk.AppChooserDialog.new_for_content_type(
        parent_win,
        Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        "x-scheme-handler/https",
    )

    def on_response(dlg, response):
        if response == Gtk.ResponseType.OK:
            info = dlg.get_app_info()
            if info:
                on_chosen(app_info_to_exec(info))
        dlg.destroy()

    dialog.connect("response", on_response)
    dialog.present()


class HandlerRow(Adw.ExpanderRow):
    def __init__(self, handler, on_delete):
        super().__init__()
        self._on_delete = on_delete
        self._setup(handler)

    def _setup(self, handler):
        self._matcher_row = Adw.ComboRow(title="Match type")
        self._matcher_row.set_model(Gtk.StringList.new(MATCHERS))
        self._matcher_row.set_selected(MATCHERS.index(handler.get("matcher", "startswith")))
        self._matcher_row.connect("notify::selected", self._sync_title)
        self.add_row(self._matcher_row)

        self._pattern_row = Adw.EntryRow(title="URL pattern")
        self._pattern_row.set_text(handler.get("string", ""))
        self._pattern_row.connect("changed", self._sync_title)
        self.add_row(self._pattern_row)

        self._exec_row = Adw.EntryRow(title="Command")
        self._exec_row.set_text(handler.get("exec", ""))
        self._exec_row.connect("changed", self._sync_title)
        pick_btn = Gtk.Button(icon_name="application-x-executable-symbolic")
        pick_btn.set_valign(Gtk.Align.CENTER)
        pick_btn.add_css_class("flat")
        pick_btn.set_tooltip_text("Choose application")
        pick_btn.connect("clicked", lambda _: open_app_chooser(
            self.get_root(), self._exec_row.set_text
        ))
        self._exec_row.add_suffix(pick_btn)
        self.add_row(self._exec_row)

        del_btn = Gtk.Button(icon_name="user-trash-symbolic")
        del_btn.set_valign(Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        del_btn.connect("clicked", lambda _: self._on_delete(self))
        self.add_suffix(del_btn)

        self._sync_title()

    def _sync_title(self, *_):
        matcher = MATCHERS[self._matcher_row.get_selected()]
        pattern = self._pattern_row.get_text()
        self.set_title(f"{matcher}: {pattern}" if pattern else "(new rule)")
        self.set_subtitle(self._exec_row.get_text())

    def get_data(self):
        return {
            "matcher": MATCHERS[self._matcher_row.get_selected()],
            "string": self._pattern_row.get_text(),
            "exec": self._exec_row.get_text(),
        }


class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.set_title("URL Handler Settings")
        self.set_default_size(640, 560)
        self._handler_rows = []
        self._build(config)

    def _build(self, config):
        self._toast_overlay = Adw.ToastOverlay()
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        page = Adw.PreferencesPage()

        default_group = Adw.PreferencesGroup(
            title="Default Handler",
            description="Used when no URL rule matches",
        )
        self._default_exec_row = Adw.EntryRow(title="Command")
        self._default_exec_row.set_text(config.get("default", {}).get("exec", ""))
        pick_btn = Gtk.Button(icon_name="application-x-executable-symbolic")
        pick_btn.set_valign(Gtk.Align.CENTER)
        pick_btn.add_css_class("flat")
        pick_btn.set_tooltip_text("Choose application")
        pick_btn.connect("clicked", lambda _: open_app_chooser(
            self, self._default_exec_row.set_text
        ))
        self._default_exec_row.add_suffix(pick_btn)
        default_group.add(self._default_exec_row)
        page.add(default_group)

        self._rules_group = Adw.PreferencesGroup(
            title="URL Rules",
            description="Rules are evaluated in order; the first match wins",
        )
        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.add_css_class("flat")
        add_btn.set_tooltip_text("Add rule")
        add_btn.connect("clicked", lambda _: self._append_row())
        self._rules_group.set_header_suffix(add_btn)

        for h in config.get("handlers", []):
            self._append_row(h)

        page.add(self._rules_group)
        scroll.set_child(page)
        toolbar_view.set_content(scroll)
        self._toast_overlay.set_child(toolbar_view)
        self.set_content(self._toast_overlay)

    def _append_row(self, handler=None):
        row = HandlerRow(
            handler or {"matcher": "startswith", "string": "", "exec": ""},
            self._remove_row,
        )
        self._handler_rows.append(row)
        self._rules_group.add(row)

    def _remove_row(self, row):
        self._handler_rows.remove(row)
        self._rules_group.remove(row)

    def _on_save(self, *_):
        config = {
            "default": {"exec": self._default_exec_row.get_text()},
            "handlers": [r.get_data() for r in self._handler_rows],
        }
        save_config(config)
        self._toast_overlay.add_toast(Adw.Toast.new("Settings saved"))


class URLHandlerSettingsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.sowgro.URLHandlerSettings")
        self.connect("activate", self._on_activate)

    def _on_activate(self, _):
        SettingsWindow(config=load_config(), application=self).present()


if __name__ == "__main__":
    URLHandlerSettingsApp().run()
