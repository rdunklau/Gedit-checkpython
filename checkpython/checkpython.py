# -*- coding: utf-8 -*-

from gi.repository import GObject, Gedit, Gtk, GdkPixbuf, Gio, Pango

from checkpython import checkers


class CheckpythonAppActivatable(GObject.Object, Gedit.AppActivatable):

    app = GObject.property(type=Gedit.App)

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

    def do_activate(self):
        # TODO: make this configurable
        self.checkers = [checkers.Pep8Checker(), checkers.PyFlakesChecker()]

        action = Gio.SimpleAction(name="checkpython")
        action.connect('activate', self.check_all)
        self.window.add_action(action)

        self._init_error_list()

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

    def check_all(self, action, data=None):
        self.error_list.clear()
        name, content = self._get_all_text()
        self.window.get_side_panel().set_property('visible', True)
        for checker in self.checkers:
            for message in checker.check(name, content):
                self.error_list.append_message(message)
        panel = self.window.get_side_panel()
        try:
            child = panel.get_child_by_name('Checkpython')
        except AttributeError:
            child = [
                i
                for i in panel.get_children()
                if i.get_name() == 'checkpython+checkpython+ErrorListView'
            ][0]
        panel.set_visible_child(child)

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

    def append_column(self, name, **opts):
        if 'text' in opts:
            renderer = Gtk.CellRendererText()
            if 'ellipsize' in opts:
                renderer.set_property('ellipsize', opts['ellipsize'])
                del opts['ellipsize']
        elif 'pixbuf' in opts:
            renderer = Gtk.CellRendererPixbuf()
        else:
            raise Exception('Unknown renderer for opts={}'.format(opts))

        column = Gtk.TreeViewColumn(name, renderer, **opts)
        super().append_column(column)
        if 'text' in opts:
            column.set_resizable(True)
            column.set_reorderable(True)
            column.set_sort_column_id(opts['text'])

    def __init__(self):
        Gtk.TreeView.__init__(self)
        self.model = Gtk.ListStore(
            GdkPixbuf.Pixbuf,  # type
            GObject.TYPE_STRING,  # code
            GObject.TYPE_STRING,  # line
            GObject.TYPE_STRING,  # message
        )

        self.append_column('', pixbuf=0)
        self.append_column('Code', text=1)
        self.append_column('Line', text=2)
        self.append_column('Msg', text=3, ellipsize=Pango.EllipsizeMode.END)

        self.set_headers_visible(True)
        self.set_model(self.model)

        # Prepare mapping errors to icons

        theme = Gtk.IconTheme.get_default()

        def _get_icon(icon):
            return Gtk.IconTheme.load_icon(theme, icon, 16, 0)

        self._icons = {
            checkers.ERROR: _get_icon('dialog-error'),
            checkers.WARNING: _get_icon('dialog-warning'),
            checkers.STYLE: _get_icon('dialog-information')
        }

    def append_message(self, message):
        self.model.append([
            self._icons[message.err_type],
            message.err_code,
            "{:0>4}".format(message.line),
            message.message
        ])

    def clear(self):
        self.model.clear()

