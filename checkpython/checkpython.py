# -*- coding: utf-8 -*-

from gi.repository import GLib, GObject, Gedit, Gtk, GdkPixbuf, Gio, Pango

from checkpython import checkers


UI_XML = """<ui>
<menubar name="MenuBar">
    <menu name="ToolsMenu" action="Tools">
      <placeholder name="ToolsOps_3">
        <menu name="PEP8menu" action="PEP8menu">
            <menuitem name="Pep8ConformanceCheckAction"
                action="Pep8ConformanceCheckAction"/>
            <menuitem name="Pep8ConformanceAutoCheckEnabled"
                action="Pep8ConformanceAutoCheckEnabled"/>
        </menu>
      </placeholder>
    </menu>
</menubar>
</ui>"""


class CheckpythonAppActivatable(GObject.Object, Gedit.AppActivatable):

    app = GObject.property(type=Gedit.App)

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate(self):
        self.app.add_accelerator("<Primary><Shift>E", "win.checkpython", None)

        self.menu_ext = self.extend_menu("tools-section")
        item = Gio.MenuItem.new(_("Check Python"), "win.checkpython")
        self.menu_ext.append_menu_item(item)

    def do_deactivate(self):
        self.app.remove_accelerator("win.checkpython", None)
        self.menu_ext = None


class CheckpythonWindowActivatable(GObject.Object, Gedit.WindowActivatable):
    __gtype_name = 'CheckpythonWindowActivatable'
    window = GObject.property(type=Gedit.Window)
    default_autocheck = False

    def do_activate(self):
        # TODO: make this configurable
        self.checkers = [checkers.Pep8Checker(), checkers.PyFlakesChecker()]

        action = Gio.SimpleAction(name="checkpython")
        action.connect('activate', self.check_all)
        self.window.add_action(action)

        for view in self.window.get_views():
            self.add_helper(view, self.window)

        self.doc_handlers = []
        self.handlers = [
            self.window.connect("tab-added", self.on_tab_added),
            self.window.connect("active-tab-changed", self.on_tab_added1),
        ]

        self._init_menu()
        self._init_error_list()

    def activate_toggle(self, action, parameter):
        state = action.get_state()
        action.change_state(GLib.Variant.new_boolean(not state.get_boolean()))

    def on_tab_added(self, window, tab, data=None):
        self._watch_doc(tab.get_document())

    def on_tab_added1(self, window, tab, data=None):
        self._watch_doc(tab.get_document())

    def _watch_doc(self, doc):
        handler = doc.connect("save", self.on_document_save)
        handler = doc.connect("loaded", self.on_document_save)
        self.doc_handlers.append((doc, handler))

    def do_deactivate(self):
        for h in self.handlers:
            self.window.disconnect(h)
        for doc, h in self.doc_handlers:
            doc.disconnect(h)

    def do_update_states(self):
        pass

    def toggle_autocheck(self, action):
        pass

    def _init_menu(self):
        self._actions = Gtk.ActionGroup('Pep8Actions')
        self._actions.add_actions([
            ('PEP8menu', Gtk.STOCK_INFO, "Python check", None,
             "This is a submenu", None),
            ('Pep8ConformanceCheckAction', Gtk.STOCK_INFO,
                'Check now', "<control><shift>e",
                'Check pep8 conformance of the current document',
                self.check_all)])

        self.autocheck = Gtk.ToggleAction(
            "Pep8ConformanceAutoCheckEnabled",
            "Check automatically", None, None,
        )
        self.autocheck.set_active(self.default_autocheck)
        self.autocheck.connect("toggled", self.toggle_autocheck)
        self._actions.add_action(self.autocheck)
        # self._ui_merge_id = manager.add_ui_from_string(UI_XML)

    def _init_error_list(self):
        self.error_list = ErrorListView()
        panel = self.window.get_side_panel()
        panel.add_titled(
            self.error_list,
            "Checkpython",
            "Checkpython",
        )

        self.error_list.connect("row-activated", self.on_row_click)
        self.error_list.show_all()

    def on_document_save(self, document, *args, **kwargs):
        if self.autocheck.get_active():
            lang = document.get_language()
            if lang and lang.get_name() == 'Python':
                self.check_all(None)

    def check_all(self, action, data=None):
        self.error_list.clear()
        name, content = self._get_all_text()
        self.window.get_side_panel().set_property('visible', True)
        for checker in self.checkers:
            for message in checker.check(name, content):
                self.error_list.append_message(message)
        panel = self.window.get_side_panel()
        panel.set_visible_child(panel.get_child_by_name('Checkpython'))

    def _get_all_text(self):
        view = self.window.get_active_view()
        if view:
            doc = self.window.get_active_document()
            begin = doc.get_start_iter()
            end = doc.get_end_iter()
            content = view.get_buffer().get_text(begin, end, False)
            name = view.get_buffer().\
                get_short_name_for_display()

            return name, content

    def on_row_click(self, tree_view, path, view=None):
        doc = self.window.get_active_document()
        lineno = self.error_list.props.model[path.get_indices()[0]]
        line_iter = doc.get_iter_at_line(int(lineno[2]) - 1)
        self.window.get_active_view().get_buffer().place_cursor(line_iter)
        self.window.get_active_view().scroll_to_iter(
            line_iter, 0, False, 0, 0.3)


class ErrorListView(Gtk.TreeView):

    def __init__(self):
        Gtk.TreeView.__init__(self)
        self.icontheme = Gtk.IconTheme.get_default()
        self.model = Gtk.ListStore(
            GdkPixbuf.Pixbuf,  # type
            GObject.TYPE_STRING,  # code
            GObject.TYPE_STRING,  # line
            GObject.TYPE_STRING,  # message
        )

        type_renderer = Gtk.CellRendererPixbuf()
        type_column = Gtk.TreeViewColumn('', type_renderer, pixbuf=0)
        self.append_column(type_column)

        code_renderer = Gtk.CellRendererText()
        code_column = Gtk.TreeViewColumn('Code', code_renderer, text=1)
        self.append_column(code_column)
        self.set_common_column_properties(code_column, 1)

        lineno_renderer = Gtk.CellRendererText()
        lineno_column = Gtk.TreeViewColumn('Line', lineno_renderer, text=2)
        self.append_column(lineno_column)
        self.set_common_column_properties(lineno_column, 2)

        message_renderer = Gtk.CellRendererText()
        message_renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        message_column = Gtk.TreeViewColumn(
            'Message',
            message_renderer,
            text=3,
        )
        self.append_column(message_column)
        self.set_common_column_properties(message_column, 3)

        self.set_headers_visible(True)
        self.set_model(self.model)

        self._icons = {
            checkers.ERROR: self._get_icon_as_pixbuf('dialog-error'),
            checkers.WARNING: self._get_icon_as_pixbuf('dialog-warning'),
            checkers.STYLE: self._get_icon_as_pixbuf('dialog-information')
        }

    def _get_icon_as_pixbuf(self, icon):
        return Gtk.IconTheme.load_icon(
            Gtk.IconTheme.get_default(),
            icon, 16, 0,
        )

    def set_common_column_properties(self, column, idx):
        column.set_resizable(True)
        column.set_reorderable(True)
        column.set_sort_column_id(idx)

    def append_message(self, message):
        self.model.append([
            self._icons[message.err_type],
            message.err_code,
            "{:0>4}".format(message.line),
            message.message])

    def clear(self):
        self.model.clear()
