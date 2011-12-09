import os

from gi.repository import GObject, Gedit, Gtk, GdkPixbuf

from .checkers import Pep8Checker, PyFlakesChecker
from . import checkers


UI_XML = """<ui>
<menubar name="MenuBar">
    <menu name="ToolsMenu" action="Tools">
      <placeholder name="ToolsOps_3">
        <menuitem name="Pep8ConformanceCheckAction"
        action="Pep8ConformanceCheckAction"/>
      </placeholder>
    </menu>
</menubar>
</ui>"""


class Pep8Plugin(GObject.Object, Gedit.WindowActivatable):
    __gtype_name = 'Pep8Plugin'
    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        super(Pep8Plugin, self).__init__()
        self.handlers = []

    def do_activate(self):
        # TODO: make this configurable
        self.checkers = [Pep8Checker(), PyFlakesChecker()]
        self.init_ui()
        handler = self.window.connect("tab-added", self.on_tab_added)
        handler = self.window.connect("active-tab-changed", self.on_tab_added)
        self.handlers.append((self.window, handler))
        [self._watch_doc(doc) for doc in self.window.get_documents()]

    def on_tab_added(self, window, tab, data=None):
        self._watch_doc(tab.get_document())

    def _watch_doc(self, doc):
        handler = doc.connect("save", self.on_document_save)
        handler = doc.connect("loaded", self.on_document_save)
        self.handlers.append((doc, handler))

    def do_deactivate(self):
        self.remove_ui()
        for obj, handler in self.handlers:
            obj.disconnect(handler)

    def do_update_states(self):
        pass

    def remove_ui(self):
        manager = self.window.get_ui_manager()
        manager.remove_ui(self._ui_merge_id)
        manager.remove_action_group(self._actions)
        manager.ensure_update()

    def init_ui(self):
        self._init_menu()
        self._init_error_list()

    def _init_menu(self):
        manager = self.window.get_ui_manager()
        self._actions = Gtk.ActionGroup('Pep8Actions')
        self._actions.add_actions([
            ('Pep8ConformanceCheckAction', Gtk.STOCK_INFO,
                'Check pep8 conformance', None,
                'Check pep8 conformance of the current document',
                self.check_all)])
        manager.insert_action_group(self._actions)
        self._ui_merge_id = manager.add_ui_from_string(UI_XML)
        manager.ensure_update()

    def _init_error_list(self):
        self.error_list = ErrorListView()
        icon = Gtk.Image.new_from_stock(Gtk.STOCK_YES, Gtk.IconSize.MENU)
        panel = self.window.get_side_panel()
        sw = Gtk.ScrolledWindow()
        sw.add(self.error_list)
        self.error_list.connect("row-activated", self.on_row_click)
        panel.add_item(sw, "Pep 8 conformance", "Pep8 conformance",
                icon)
        panel.activate_item(sw)
        self.error_list.show_all()

    def on_document_save(self, document, *args, **kwargs):
        lang = document.get_language()
        if lang and lang.get_name() == 'Python':
            self.check_all(None)

    def check_all(self, action, data=None):
        self.error_list.clear()
        name, content = self._get_all_text()
        for checker in self.checkers:
            for message in checker.check(name, content):
                self.error_list.append_message(message)

    def _get_all_text(self):
        view = self.window.get_active_view()
        if view:
            doc = self.window.get_active_document()
            begin = doc.get_iter_at_line(0)
            end = doc.get_iter_at_line(doc.get_line_count())
            content = view.get_buffer().get_text(begin, end, False)
            name = view.get_buffer().\
                get_short_name_for_display()

            return name, content

    def on_row_click(self, tree_view, path, view=None):
        doc = self.window.get_active_document()
        lineno = self.error_list.props.model[path.get_indices()[0]]
        line_iter = doc.get_iter_at_line(lineno[2] - 1)
        self.window.get_active_view().get_buffer().place_cursor(line_iter)
        self.window.get_active_view().scroll_to_iter(
                line_iter, 0, False, 0, 0.3)


class ErrorListView(Gtk.TreeView):

    def __init__(self):
        super(ErrorListView, self).__init__()
        self.set_model(Gtk.ListStore(GdkPixbuf.Pixbuf,  # type
                                    GObject.TYPE_STRING,  # code
                                    GObject.TYPE_INT,  # line
                                    GObject.TYPE_STRING))  # message

        self.set_headers_visible(True)

        type_column = Gtk.TreeViewColumn('type')
        typecell = Gtk.CellRendererPixbuf()
        type_column.pack_start(typecell, False)
        self.append_column(type_column)
        type_column.add_attribute(typecell, "pixbuf", 0)

        code_column = Gtk.TreeViewColumn('code')
        codecell = Gtk.CellRendererText()
        code_column.pack_start(codecell, False)
        self.append_column(code_column)
        code_column.add_attribute(codecell, "text", 1)
        self.set_common_column_properties(code_column, 1)

        lineno_column = Gtk.TreeViewColumn('Line')
        lineno_cell = Gtk.CellRendererText()
        lineno_column.pack_start(lineno_cell, False)
        self.append_column(lineno_column)
        lineno_column.add_attribute(lineno_cell, "text", 2)
        self.set_common_column_properties(lineno_column, 2)

        message_column = Gtk.TreeViewColumn('Message')
        message_cell = Gtk.CellRendererText()
        message_column.pack_start(message_cell, False)
        self.append_column(message_column)
        message_column.add_attribute(message_cell, "text", 3)
        self.set_common_column_properties(message_column, 3)
        self._icons = {
                checkers.ERROR: self._get_icon_as_pixbuf('dialog-error'),
                checkers.WARNING: self._get_icon_as_pixbuf('dialog-warning'),
                checkers.STYLE: self._get_icon_as_pixbuf('dialog-information')
        }

    def _get_icon_as_pixbuf(self, icon):
        return Gtk.IconTheme.load_icon(Gtk.IconTheme.get_default(),
                icon, 16, 0)

    def set_common_column_properties(self, column, idx):
        column.set_resizable(True)
        column.set_reorderable(True)
        column.set_sort_column_id(idx)

    def append_message(self, message):
        self.props.model.append((
            self._icons[message.err_type],
            message.err_code,
            message.line,
            message.message))

    def clear(self):
        self.props.model.clear()
