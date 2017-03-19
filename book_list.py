#!/usr/bin/env python

import sys
import os
import signal
import json
import functools
import itertools
import datetime

from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog, QPushButton, QMessageBox, QLineEdit, QMainWindow, QGridLayout, QVBoxLayout, QDesktopWidget, QAction, QHBoxLayout, QLabel, QShortcut, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QSpacerItem, QMainWindow, QDateEdit, QHeaderView, QItemDelegate, QTableView
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QKeySequence

logging_enabled = True

def log(string):
    if logging_enabled:
        with open("booklist.log", 'a+') as f:
            f.write("{0}: {1}\n".format(datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f"), string))

class CalendarDelegate(QItemDelegate):

    def createEditor(self, parent, option, index):
        self.date_input = QDateEdit(parent)
        self.date_input.setMinimumWidth(100)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy/MM/dd")
        self.date_input.setMaximumDate(QDate.currentDate())

        return self.date_input

    def setEditorData(self, editor, index):
        editor.setDate(QDate.fromString(index.model().data(index, Qt.DisplayRole), "yyyy/MM/dd"))

    def setModelData(self, editor, model, index):
        date = editor.date().toString("yyyy/MM/dd")
        if date:
            model.setData(index, date, Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

class MultiColumnFilterProxyModel(QSortFilterProxyModel):

    def __init__(self, parent=None):
        super(MultiColumnFilterProxyModel, self).__init__(parent)
        self.filter_columns = [0, 1, 2]

    def filterAcceptsRow(self, row_num, parent):
        """http://www.dayofthenewdan.com/2013/02/09/Qt_QSortFilterProxyModel.html
        """
        model = self.sourceModel()
        filter_regexp = self.filterRegExp()
        filter_regexp.setCaseSensitivity(Qt.CaseInsensitive)
        tests = [filter_regexp.lastIndexIn(model.index(row_num, col, parent).data().lower()) >= 0 for col in self.filter_columns]

        return any(tests)

class Book(object):

    def __init__(self, title, author, date):
        self.title = title
        self.author = author
        self.date = date
        log(u"created book {0}".format(self.__repr__()))

    def set_title(self, title):
        self.title = title

    def set_author(self, author):
        self.author = author

    def set_date(self, date):
        self.date = date

    def contains(self, string):
        """Check if any of the elements of this book contain the given string.

        """

        return string in self.title or string in self.author or string in self.date

    def __eq__(self, other):
        return self.title == other.title and self.author == other.author and self.date == other.date

    def __repr__(self):
        return u"{0}: {1} - {2}".format(self.date, self.author, self.title)

class BookListModel(QAbstractTableModel):


    # Background colour for table items which are from a new book
    new_bg_item_colour = QColor(40,150,190)

    def __init__(self, list_file=None, parent=None):
        super(BookListModel, self).__init__(parent)
        self.books = [] # all books, old and new
        self.new_books = [] # only new books
        self.deleted_books = []
        self.list_file = list_file

    def columnCount(self, parent):
        return 3

    def rowCount(self, parent):
        return len(self.books)

    def data(self, index, role):
        if role == Qt.DisplayRole or role == Qt.EditRole:
            book = self.books[index.row()]
            if index.column() == 0:
                return book.title
            elif index.column() == 1:
                return book.author
            elif index.column() == 2:
                return book.date
        if role == Qt.BackgroundRole:
            if self.books[index.row()] in self.new_books:
                return BookListModel.new_bg_item_colour

        return QVariant()

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section == 0:
                    return "Title"
                elif section == 1:
                    return "Author"
                elif section == 2:
                    return "Date"

        return QVariant()

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            book = self.books[index.row()]
            if index.column() == 0:
                book.title = value
            elif index.column() == 1:
                book.author = value
            elif index.column() == 2:
                book.date = value

        return True

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled

    def insertRows(self, row, count, parent):
        self.beginInsertRows(QModelIndex(), row, row + count - 1)
        self.endInsertRows()

    def removeRows(self, row, count, parent):
        self.beginRemoveRows(QModelIndex(), row, row + count - 1)
        to_del = self.books[row:row + count] # can't delete and loop
        for book in to_del:
            self.deleted_books.append(book)
            self.books.remove(book)

            if book in self.new_books:
                self.new_books.remove(book)
            log("removed book {0}".format(book.__repr__()))

        self.endRemoveRows()
        return True

    def add_book(self, book):
        log("adding book")
        self.books.append(book)
        self.new_books.append(book)
        self.insertRows(len(self.books) - 1, 1, QModelIndex())

    def has_book(self, new_book):
        for book in self.books:
            title_match = new_book.title.lower() == book.title.lower()
            author_match = new_book.author.lower() == book.author.lower()
            if author_match and title_match:
                log("Book exists in list")
                return True

        return False

    def set_list_file(self, list_file):
        """Change the list file used by this model. Saves changes made in the session up
        to this point in the previous file before loading the new one.

        """
        log("changing list file, current is {0}".format(list_file))
        if self.list_file:
            self.write_book_list()

        self.list_file = list_file
        log("list file set to {0}".format(self.list_file))

        self.read_book_list()

    def read_book_list(self):
        """Read a book list from file. If there are any new books that have been added,
        will write them to the file before reading a new set of books. The books
        are read from file in a json format.

        """
        if self.new_books: # if there are new books, write them to file before resetting
            self.write_book_list()

        self.books = []
        self.new_books = []

        with open(self.list_file, 'r') as f:
            for book_json in json.loads(f.read()):
                self.books.append(Book(book_json["title"], book_json["author"], book_json["date"]))

    def write_book_list(self):
        """Write the books to file. This writes books that existed in the file when it
        was first loaded, and books which were added in the session. In this way
        we automatically transfer modifications to any books without having to
        check which books were modified and just changing those bits.

        """
        log("writing book list to {0}".format(self.list_file))
        with open(self.list_file, 'w') as f:
            book_dicts = []
            for book in self.books:
                log("wrote {0}".format(book.__dict__))
                book_dicts.append(book.__dict__)

            f.write(json.dumps(book_dicts, indent=1))

class BookList(QMainWindow):

    def __init__(self, list_file=None):
        super(BookList, self).__init__()

        self.book_model = BookListModel()
        log("created book list model")
        self.list_file = list_file
        log("got list file {0}".format(self.list_file))

        # open a new file, but only force selection if one isn't provided by the
        # commandline
        self.open_new_file(force=self.list_file == None)

        self.create_window()
        log("booklist init completed")

    def create_window(self):
        self.main_widget = QWidget()

        self.create_add_widget()
        self.create_view_widget()

        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.view_widget)
        self.main_layout.addWidget(self.add_widget)

        self.setCentralWidget(self.main_widget)
        self.centralWidget().setLayout(self.main_layout)

        self.setup_menubar()
        self.update_status()

        self.title_input.setFocus()

        self.setWindowTitle("Book List Manager")

        tablewidth = 0
        for i in range(0, self.book_model.columnCount(QModelIndex())):
            tablewidth += self.table_widget.columnWidth(i)

        self.resize(tablewidth + 50, 600)
        self.center()

    def create_add_widget(self):
        self.add_widget = QWidget()

        self.author_input = QLineEdit()
        self.author_input.setMinimumWidth(250)
        self.author_input.setMaximumWidth(500)
        self.author_input.setPlaceholderText("Author")
        self.author_lock = QCheckBox()
        self.author_lock.setToolTip("Don't erase author when adding")

        self.title_input = QLineEdit()
        self.title_input.setMinimumWidth(250)
        self.title_input.setMaximumWidth(500)
        self.title_input.setPlaceholderText("Title")

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setMinimumWidth(250)
        self.date_input.setMaximumWidth(500)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy/MM/dd")
        self.date_input.setMaximumDate(QDate.currentDate())
        self.date_today = QPushButton("Today")
        self.date_today.clicked.connect(functools.partial(self.date_input.setDate, QDate.currentDate()))

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.add_book)
        self.add_btn.setMaximumWidth(500)

        self.input_layout = QGridLayout()
        self.input_layout.addWidget(self.title_input, 0, 2)
        self.input_layout.addWidget(self.author_input, 1, 2)
        self.input_layout.addWidget(self.author_lock, 1, 3)
        self.input_layout.addWidget(self.date_input, 2, 2)
        self.input_layout.addWidget(self.date_today, 2, 3)
        self.input_layout.addWidget(self.add_btn, 3, 2)

        # Messing around with stretch to get the thing to stay in the middle.
        # Probably a better way of doing this.
        self.sub_layout = QVBoxLayout()
        self.sub_layout.addLayout(self.input_layout)

        self.add_layout = QHBoxLayout()
        self.add_layout.addStretch()
        self.add_layout.addLayout(self.sub_layout)
        self.add_layout.addStretch()

        self.add_widget.setLayout(self.add_layout)

        self.add_shortcut = QShortcut("Return", self.add_widget, context=Qt.WidgetWithChildrenShortcut)
        self.add_shortcut.activated.connect(self.add_book)

    def create_view_widget(self):
        self.view_widget = QWidget()

        self.table_widget = QTableView()
        self.table_widget.setSortingEnabled(True)

        self.proxy_model = MultiColumnFilterProxyModel()
        self.proxy_model.setSourceModel(self.book_model)

        self.table_widget.setModel(self.proxy_model)
        # Can only sort properly after proxy model has been set
        self.table_widget.sortByColumn(2, Qt.DescendingOrder)

        # Title and author are set to contents, but date is fixed
        self.table_widget.horizontalHeader().setMinimumSectionSize(100)
        self.table_widget.horizontalHeader().setMaximumSectionSize(400)
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)

        # delegate date editing to the calendar delegate, which allows use of
        # drop down calendar and guarantees correctness.
        self.calendar_delegate = CalendarDelegate()
        self.table_widget.setItemDelegateForColumn(2, self.calendar_delegate)

        self.table_layout = QVBoxLayout()
        self.table_layout.addWidget(self.table_widget)

        self.search_layout = QHBoxLayout()
        self.search_text = QLineEdit()
        self.search_text.setPlaceholderText("Enter filter string")
        self.search_text.setMinimumWidth(200)
        self.search_text.setMaximumWidth(500)
        self.search_text.textChanged.connect(self.proxy_model.setFilterRegExp)
        self.search_text.textChanged.connect(self.update_status)
        # Need this because of some strange behaviour. Without this, if you type
        # a unique filter string for a book with a short field plus an extra
        # uninvolved character (e.g. On Liberty with the filter libertyy), and
        # then use backspace to erase characters one by one, eventually when you
        # erase the whole string, the columns will be resized only one, to the
        # size of the first (short) entry to reappear in the table.
        self.search_text.textChanged.connect(self.resize_table)
        self.search_clear = QPushButton("Clear")
        self.search_clear.clicked.connect(self.clear_search)

        self.search_layout.addWidget(self.search_clear)
        self.search_layout.addWidget(self.search_text)
        self.search_layout.addStretch()

        self.view_layout = QVBoxLayout()

        self.view_layout.addLayout(self.search_layout)
        self.view_layout.addLayout(self.table_layout)

        self.view_widget.setLayout(self.view_layout)

        self.delete_shortcut = QShortcut(QKeySequence.Delete, self.view_widget, context=Qt.WidgetWithChildrenShortcut)
        self.delete_shortcut.activated.connect(self.delete_book)

    def resize_table(self, changed_text=None):
        self.table_widget.resizeColumnsToContents()

    def clear_search(self):
        """Clears the text in the search box and resets the table to the state of
        displaying all books in the list.

        """
        self.search_text.clear()

    def table_item_updated(self, changed_item):
        if changed_item in self.table_item_associations:
            self.table_item_associations[changed_item](changed_item.text())

    def setup_menubar(self):
        open_action = QAction('&Open', self)
        open_action.setShortcut('Ctrl+o')
        open_action.setStatusTip('Select list file')
        open_action.triggered.connect(self.open_new_file)

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(open_action)
        menubar.setVisible(True)

    def center(self):
        """Center the qt frame on the desktop
        """
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def closeEvent(self, event):
        log("got close event")
        """On close event, ask if user wants to quit, and try to write the book list. If
        a list doesn't exist, then don't quit.

        """
        reply = QMessageBox.question(self, 'Message',
                                     "Are you sure to quit?\n{0} books will be added to your list.".format(len(self.book_model.new_books)),
                                     QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)


        if reply == QMessageBox.Yes:
            log("close event accepted")
            self.book_model.write_book_list()
        else:
            log("close event ignored")
            event.ignore()

    def user_wants_duplicate(self, book):
        """Ask the user if they want to add a duplicate book.

        """
        
        log("Book already exists in list.")
        message_box = QMessageBox()
        message_box.setText("{0} - {1}\n\nFound a book with the same author and title in the list. Do you want to add this book anyway?".format(book.author, book.title))
        message_box.setWindowTitle("Book already exists")
        yes_button = message_box.addButton("Add anyway", QMessageBox.YesRole)
        no_button = message_box.addButton("Don't add", QMessageBox.NoRole)

        message_box.setDefaultButton(no_button)
        message_box.exec_()

        return message_box.clickedButton() == yes_button

    def add_book(self):
        """Add a book to the list. This book goes into a separate list from the books
        which existed when the file was first loaded. The book is also added to
        the table view. Once the book is added, the add view is reset to a
        default state.

        """
        if not self.author_input.text() or not self.title_input.text():
            result = QMessageBox.warning(self, "Message", "Please enter both an author and title.")
        else:
            new_book = Book(self.title_input.text(), self.author_input.text(), self.date_input.date().toString("yyyy/MM/dd"))
            duplicate = self.book_model.has_book(new_book)
            if not duplicate or (duplicate and self.user_wants_duplicate(new_book)):
                self.book_model.add_book(new_book)
                self.reset_add_view()
                self.resize_table()
                self.update_status()

    def delete_book(self):
        log("deleting books")
        # Do things this way because the rows aren't deleted simultaneously, so
        # the indexes of the items change
        selected = self.table_widget.selectedIndexes()
        log("selected indices {0}".format(selected))
        reply = QMessageBox.question(self, 'Delete selection',
                                     "Are you sure to delete these books?\n{0} books will be removed from your list.".format(len(selected)),
                                     QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            while selected:
                index = selected.pop()
                log("removing book at row {0}".format(index.row()))
                self.proxy_model.removeRows(index.row(), 1, index)
                selected = self.table_widget.selectedIndexes()
            self.update_status()
            self.resize_table()

    def update_status(self, string=None):
        status_string = "Total: {0}".format(len(self.book_model.books))
        new = len(self.book_model.new_books)
        if new > 0:
            status_string += ", New: {0}".format(new)

        filtered = self.proxy_model.rowCount(QModelIndex())
        if filtered != len(self.book_model.books):
            status_string += ", Filtered: {0}".format(filtered)
        self.statusBar().showMessage(status_string)

    def open_new_file(self, force=True):
        """Opens a new file, and will not stop asking until you actually pick one. Will
        first write newly added books to the current list file. If force is
        True, will always ask for a new file. Otherwise, might not ask if the
        list_file exists and is a valid file.

        """
        log("opening new file with arg force={0}".format(force))
        while True: # nasty
            self.get_list_file(new=force)
            if self.list_file:
                self.book_model.set_list_file(self.list_file)
                break

        log("got new list file {0}".format(self.list_file))

    def reset_add_view(self):
        """Reset the add view to a default state. The title and author entries are
        cleared, and the focus is set on the title. If the author_lock checkbox
        is checked, then we do not reset the author string to empty.

        """
        self.title_input.setText("")
        self.title_input.setFocus()

        if not self.author_lock.isChecked():
            self.author_input.setText("")

    def get_list_file(self, new=False):
        """Get the list file to be used. If new is false, will check if the list file is
        set and exists. If new is true, will always ask for a new file.

        """
        log("getting list file, current is {0}".format(self.list_file))
        if new or not self.list_file or not os.path.isfile(self.list_file):
            log("Querying user")
            message_box = QMessageBox()
            message_box.setText("Open existing book list or create a new one?")
            message_box.setWindowTitle("Select list file")
            existing_button = message_box.addButton("Open Existing", QMessageBox.YesRole)
            new_button = message_box.addButton("Create new", QMessageBox.YesRole)

            message_box.setDefaultButton(existing_button)
            message_box.exec_()

            dialog = QFileDialog()
            dialog.setNameFilter("Only .txt files (*.txt)")

            if message_box.clickedButton() == new_button:
                dialog.setFileMode(QFileDialog.AnyFile)
                dialog.setDefaultSuffix("txt")
            elif message_box.clickedButton() == existing_button:
                dialog.setFileMode(QFileDialog.ExistingFile)

            if dialog.exec_() == 1: # open clicked, otherwise cancelled
                selected = dialog.selectedFiles()[0]
                _, ext = os.path.splitext(selected)

                if ext != ".txt":
                    selected += ".txt"
                    result = QMessageBox.warning(self, "Your filename was changed", 'You selected a filename with an extension other than ".txt", but the program only supports list files with the  ".txt" extension. You can find your file at:\n {0}'.format(selected))

                self.list_file = selected

                log("Got file {0} from user".format(self.list_file))
                if not os.path.isfile(self.list_file):
                    log("File did not exist - creating")
                    with open(self.list_file, 'w'): # just to create the file
                        pass

        return self.list_file

if __name__ == '__main__':
    app = QApplication(sys.argv)
    log("-------------------- START --------------------")
    log("args: {0}".format(sys.argv))
    list_file = None
    if len(sys.argv) > 1:
        log("got list file in args")
        list_file = sys.argv[1]

    gui = BookList(list_file)
    gui.show()

    try:
        sys.exit(app.exec_())
    except Exception as e:
        log("caught exception in main")
        gui.write_book_list()
