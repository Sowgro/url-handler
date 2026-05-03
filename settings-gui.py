#!/usr/bin/env python3

# NOTE: this entire file was generated with claude

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GObject
import json
import os
import re

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
MATCHERS = ["startswith", "contains", "endswith"]
MATCHER_LABELS = ["Starts with", "Contains", "Ends with"]


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
    def __init__(self, handler, on_delete, on_reorder, on_change):
        super().__init__()
        self._on_delete = on_delete
        self._on_reorder = on_reorder
        self._on_change = on_change
        self._setup(handler)

    def _setup(self, handler):
        handle = Gtk.Image(icon_name="list-drag-handle-symbolic")
        handle.add_css_class("dim-label")
        handle.set_margin_start(2)
        handle.set_cursor_from_name("grab")
        drag_src = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        drag_src.connect("prepare", self._on_drag_prepare)
        handle.add_controller(drag_src)
        self.add_prefix(handle)

        # Drop target covers the whole row
        drop_tgt = Gtk.DropTarget.new(GObject.TYPE_OBJECT, Gdk.DragAction.MOVE)
        drop_tgt.connect("drop", self._on_drop)
        self.add_controller(drop_tgt)

        # Match type — values set before signals are connected so they don't fire _on_change
        self._matcher_row = Adw.ComboRow(title="Match type")
        self._matcher_row.set_model(Gtk.StringList.new(MATCHER_LABELS))
        self._matcher_row.set_selected(MATCHERS.index(handler.get("matcher", "startswith")))
        self._matcher_row.connect("notify::selected", self._on_field_changed)
        self.add_row(self._matcher_row)

        self._pattern_row = Adw.EntryRow(title="URL pattern")
        self._pattern_row.set_text(handler.get("string", ""))
        self._pattern_row.connect("changed", self._on_field_changed)
        self.add_row(self._pattern_row)

        self._exec_row = Adw.EntryRow(title="Command")
        self._exec_row.set_text(handler.get("exec", ""))
        self._exec_row.connect("changed", self._on_field_changed)
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

    def _on_drag_prepare(self, src, x, y):
        val = GObject.Value()
        val.init(GObject.TYPE_OBJECT)
        val.set_object(self)
        return Gdk.ContentProvider.new_for_value(val)

    def _on_drop(self, tgt, value, x, y):
        if isinstance(value, HandlerRow) and value is not self:
            self._on_reorder(value, self)
        return True

    def _on_field_changed(self, *_):
        self._sync_title()
        self._on_change()

    def _sync_title(self, *_):
        idx = self._matcher_row.get_selected()
        label = MATCHER_LABELS[idx] if idx < len(MATCHER_LABELS) else ""
        pattern = self._pattern_row.get_text()
        self.set_title(f'{label} "{pattern}"' if pattern else "(new rule)")
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
        self._save_btn = Gtk.Button(label="Save")
        self._save_btn.add_css_class("suggested-action")
        self._save_btn.set_sensitive(False)
        self._save_btn.connect("clicked", self._on_save)
        header.pack_end(self._save_btn)
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
        # Connect after set_text so initial population doesn't mark dirty
        self._default_exec_row.connect("changed", self._mark_dirty)
        default_group.add(self._default_exec_row)
        page.add(default_group)

        self._rules_group = Adw.PreferencesGroup(
            title="URL Rules",
            description="Rules are evaluated in order; the first match will be used.",
        )
        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.add_css_class("flat")
        add_btn.set_tooltip_text("Add rule")
        add_btn.connect("clicked", self._on_add_rule)
        self._rules_group.set_header_suffix(add_btn)

        for h in config.get("handlers", []):
            self._append_row(h)

        page.add(self._rules_group)
        scroll.set_child(page)
        toolbar_view.set_content(scroll)
        self._toast_overlay.set_child(toolbar_view)
        self.set_content(self._toast_overlay)

    def _mark_dirty(self, *_):
        self._save_btn.set_sensitive(True)

    def _append_row(self, handler=None):
        row = HandlerRow(
            handler or {"matcher": "startswith", "string": "", "exec": ""},
            self._remove_row,
            self._reorder_row,
            self._mark_dirty,
        )
        self._handler_rows.append(row)
        self._rules_group.add(row)

    def _on_add_rule(self, _):
        self._append_row()
        self._mark_dirty()

    def _remove_row(self, row):
        self._handler_rows.remove(row)
        self._rules_group.remove(row)
        self._mark_dirty()

    def _reorder_row(self, dragged, target):
        src_idx = self._handler_rows.index(dragged)
        dst_idx = self._handler_rows.index(target)
        self._handler_rows.insert(dst_idx, self._handler_rows.pop(src_idx))
        for row in list(self._handler_rows):
            self._rules_group.remove(row)
        for row in self._handler_rows:
            self._rules_group.add(row)
        self._mark_dirty()

    def _on_save(self, *_):
        config = {
            "default": {"exec": self._default_exec_row.get_text()},
            "handlers": [r.get_data() for r in self._handler_rows],
        }
        save_config(config)
        self._save_btn.set_sensitive(False)
        self._toast_overlay.add_toast(Adw.Toast.new("Settings saved"))


class URLHandlerSettingsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.sowgro.URLHandlerSettings")
        self.connect("activate", self._on_activate)

    def _on_activate(self, _):
        SettingsWindow(config=load_config(), application=self).present()


if __name__ == "__main__":
    URLHandlerSettingsApp().run()
