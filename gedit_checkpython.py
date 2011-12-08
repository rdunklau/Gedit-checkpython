from collections import namedtuple
from gi.repository import GObject, Gedit, Gtk, GdkPixbuf
import pep8
import sys
import re
from optparse import OptionParser
import StringIO
import ast
from pyflakes import checker as flakeschecker

pep8.options = OptionParser()
pep8.options.count = 1
pep8.options.select = []
pep8.options.ignore = []
pep8.options.show_source = False
pep8.options.show_pep8 = False
pep8.options.quiet = 0
pep8.options.repeat = True
pep8.options.verbose = 0
pep8.options.counters = dict.fromkeys(pep8.BENCHMARK_KEYS, 0)
pep8.options.physical_checks = pep8.find_checks('physical_line')
pep8.options.logical_checks = pep8.find_checks('logical_line')
pep8.options.messages = {}


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

message = namedtuple('Message', ('message', 'lineno', 'col', 'message_args'))


class Pep8Plugin(GObject.Object, Gedit.WindowActivatable):
    __gtype_name = 'Pep8Plugin'
    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        super(Pep8Plugin, self).__init__()

    def do_activate(self):
        self.init_ui()

    def do_deactivate(self):
        self.remove_ui()

    def do_update_states(self):
        pass

    def remove_ui(self):
        manager = self.window.get_ui_manager()
        manager.remove_ui(self._ui_merge_id)
        manager.remove_action_group(self._actions)
        manager.ensure_update()

    def init_ui(self):
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

        self._model = Gtk.ListStore(GObject.TYPE_STRING,  # type
                                    GObject.TYPE_INT,  # line
                                    GObject.TYPE_STRING)
        self._side_widget = Gtk.TreeView()
        self._side_widget.set_model(self._model)
        self._side_widget.set_headers_visible(True)
        
        column = Gtk.TreeViewColumn('Type')
        cell = Gtk.CellRendererText()
        column.pack_start(cell, False)
        self._side_widget.append_column(column)
        column.add_attribute(cell, "text", 0)
        column.set_resizable(True)
        column.set_reorderable(True)
        column.set_sort_column_id(0)

        column = Gtk.TreeViewColumn('Line')
        cell = Gtk.CellRendererText()
        column.pack_start(cell, False)
        self._side_widget.append_column(column)
        column.add_attribute(cell, "text", 1)
        column.set_resizable(True)
        column.set_reorderable(True)
        column.set_sort_column_id(1)

        column = Gtk.TreeViewColumn('Message')
        cell = Gtk.CellRendererText()
        column.pack_start(cell, False)
        self._side_widget.append_column(column)
        column.add_attribute(cell, "text", 2)
        column.set_resizable(True)
        column.set_reorderable(True)
        column.set_sort_column_id(2)
        
        
        sw = Gtk.ScrolledWindow()
        sw.add(self._side_widget)


        self._side_widget.connect("row-activated", self.on_row_click)
        icon = Gtk.Image.new_from_stock(Gtk.STOCK_YES, Gtk.IconSize.MENU)
        panel = self.window.get_side_panel()
        panel.add_item(sw, "Pep 8 conformance", "Pep8 conformance",
                icon)
        panel.activate_item(sw)
        self._side_widget.show_all()

    def check_all(self, action, data=None):
        self._model.clear()
        self.check_pep8()
        self.check_pyflakes()

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

    
    def check_pep8(self):
        name, content = self._get_all_text()
        lines = ['%s\n' % line for line in content.split('\n')]
        old_stderr, sys.stderr = sys.stderr, StringIO.StringIO()
        old_stdout, sys.stdout = sys.stdout, StringIO.StringIO()
        try:
            pep8.Checker(name, lines=lines).check_all()
        except:
            pass
        finally:
            sys.stderr, err_result = old_stderr, sys.stderr
            sys.stdout, result = old_stdout, sys.stdout
        result.seek(0)
        pep8regexpr = r'([^:]*):(\d*):(\d*): (\w\d*) (.*)'
        errors = sorted([re.match(pep8regexpr, line)
            for line in result.readlines() if line],
            key=lambda x: x.group(2))
        for match in errors:
            lineno = int(match.group(2))
            text = match.group(5)
            col = int(match.group(3) or -1)
            err_type = match.group(4)
            self._model.append((err_type, lineno, text))

    def check_pyflakes(self):
        old_stderr, sys.stderr = sys.stderr, StringIO.StringIO()
        name, content = self._get_all_text()
        try:
            tree = ast.parse(content, name)
        except:
            try:
                value = sys.exc_info()[1]
                lineno, offset, line = value[1][1:]
            except IndexError:
                lineno, offset, line = 1, 0, ''
            messages = [message(str(value), lineno, offset, tuple())]
        else:
            messages = flakeschecker.Checker(tree, name).messages
        finally:
            sys.stderr = old_stderr
        for w in messages:
            self._model.append(('E', w.lineno, (w.message % w.message_args)))

    def on_row_click(self, tree_view, path, view=None):
        doc = self.window.get_active_document()
        lineno = self._side_widget.props.model[path.get_indices()[0]]
        line_iter = doc.get_iter_at_line(lineno[1] - 1)
        self.window.get_active_view().get_buffer().place_cursor(line_iter)
        self.window.get_active_view().scroll_to_iter(
                line_iter, 0, False, 0, 0.3)
