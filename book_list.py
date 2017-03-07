#!/usr/bin/env python

import sys
import os
import signal
import json
import functools

from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog, QPushButton, QMessageBox, QLineEdit, QMainWindow, QGridLayout, QVBoxLayout, QDesktopWidget, QAction, QHBoxLayout, QLabel, QShortcut, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QSpacerItem, QMainWindow, QDateEdit, QHeaderView
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor

class Book(object):

    def __init__(self, title, author, date):
        self.title = title
        self.author = author
        self.date = date

    def set_title(self, title):
        self.title = title

    def set_author(self, author):
        self.author = author

    def __repr__(self):
        return "{0}: {1} - {2}".format(self.date, self.author, self.title)

class BookList(QMainWindow):

    # Background colour for table items which are from a new book
    new_bg_item_colour = QColor(40,150,190)

    def __init__(self, list_file=None):
        super(BookList, self).__init__()

        self.list_file = list_file
        self.books = []
        self.new_books = []
        self.table_item_associations = {}

        self.create_window()

        # open a new file, but only force selection if one isn't provided by the
        # commandline
        self.open_new_file(force=self.list_file == None)

    def create_window(self):
        self.tabs = QTabWidget()

        self.create_add_widget()
        self.create_table_widget()

        self.tabs.addTab(self.add_widget, "Add")
        self.tabs.addTab(self.table_widget, "View")

        self.setCentralWidget(self.tabs)

        self.setup_menubar()

        self.setWindowTitle("Book List Manager")

        self.resize(300, 150)
        self.center()

        self.add_shortcut = QShortcut("Return", self.add_widget)
        self.add_shortcut.activated.connect(self.add_book)

    def create_add_widget(self):
        self.add_widget = QWidget()

        self.author_input = QLineEdit()
        self.author_input.setMinimumWidth(250)
        self.author_input.setMaximumWidth(500)
        self.author_label = QLabel("Author:")
        self.author_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.author_label.setFixedWidth(45)
        self.author_lock = QCheckBox()
        self.author_lock.setToolTip("Don't erase author when adding")

        self.title_input = QLineEdit()
        self.title_input.setMinimumWidth(250)
        self.title_input.setMaximumWidth(500)
        self.title_label = QLabel("Title:")
        self.title_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.title_label.setFixedWidth(45)


        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setMinimumWidth(250)
        self.date_input.setMaximumWidth(500)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy/MM/dd")
        self.date_input.setMaximumDate(QDate.currentDate())
        self.date_label = QLabel("Date:")
        self.date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.date_label.setFixedWidth(45)
        self.date_today = QPushButton("Today")
        self.date_today.clicked.connect(functools.partial(self.date_input.setDate, QDate.currentDate()))
        
        
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.add_book)
        self.add_btn.setMaximumWidth(500)

        self.input_layout = QGridLayout()
        self.input_layout.addWidget(self.title_label, 0, 1)
        self.input_layout.addWidget(self.title_input, 0, 2)
        self.input_layout.addWidget(self.author_label, 1, 1)
        self.input_layout.addWidget(self.author_input, 1, 2)
        self.input_layout.addWidget(self.author_lock, 1, 3)
        self.input_layout.addWidget(self.date_label, 2, 1)
        self.input_layout.addWidget(self.date_input, 2, 2)
        self.input_layout.addWidget(self.date_today, 2, 3)
        self.input_layout.addWidget(self.add_btn, 3, 2)


        # Messing around with stretch to get the thing to stay in the middle.
        # Probably a better way of doing this.
        self.sub_layout = QVBoxLayout()
        self.sub_layout.addStretch()
        self.sub_layout.addLayout(self.input_layout)
        self.sub_layout.addStretch()
        
        self.main_layout = QHBoxLayout()
        self.main_layout.addStretch()
        self.main_layout.addLayout(self.sub_layout)
        self.main_layout.addStretch()

        self.add_widget.setLayout(self.main_layout)

    def create_table_widget(self):
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(3) # date, author, title
        self.table_widget.setSortingEnabled(True)
        self.table_widget.setHorizontalHeaderLabels(["Title", "Author", "Date"])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.table_widget.itemChanged.connect(self.table_item_updated)

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

    def center(self):
        """Center the qt frame on the desktop
        """
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def closeEvent(self, event):
        """On close event, ask if user wants to quit, and try to write the book list. If
        a list doesn't exist, then don't quit.

        """
        reply = QMessageBox.question(self, 'Message',
                                     "Are you sure to quit?\n{0} books will be added to your list.".format(len(self.new_books)),
                                     QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)


        if reply == QMessageBox.Yes:
            if self.write_book_list():
                event.accept()
            else:
                result = QMessageBox.warning(self, "Message", "A list file wasn't specified and you added books. Won't exit because you'll lose data!")
                event.ignore()
        else:
            event.ignore()


    def get_list_file(self, new=False):
        """Get the list file to be used. If new is false, will check if the list file is
        set and exists. If new is true, will always ask for a new file.

        """
        if new or not self.list_file or not os.path.isfile(self.list_file):
            result = QMessageBox.warning(self, "Message", "Please select the book list you want to use or add to.")
            dialog = QFileDialog()
            dialog.setFileMode(QFileDialog.AnyFile)
            if dialog.exec_() == 1: # open clicked, otherwise cancelled
                self.list_file = dialog.selectedFiles()[0]
                if not os.path.isfile(self.list_file):
                    with open(self.list_file, 'w'): # just to create the file
                        pass

        return self.list_file

    def populate_table_widget(self):
        """Populates the table widget with books that already exist in the file.
        """
        self.table_item_associations = {} # reset item associations, since the table is being repopulated
        for book in self.books:
            self.add_book_to_table_widget(book)

    def add_book_to_table_widget(self, book, new=False):
        """Adds books to the table widget. If new is set, add the book with a different
        coloured background.

        """
        row_num = self.table_widget.rowCount()
        self.table_widget.insertRow(row_num)

        title_item = QTableWidgetItem(book.title)
        author_item = QTableWidgetItem(book.author)
        date_item = QTableWidgetItem(book.date)
        # date item isn't editable
        date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable);

        # crude way of being able to edit book objects when the item is changed
        # in view. The value is a function which takes a string parameter to
        # modify the object member variable
        self.table_item_associations[title_item] = (book.set_title)
        self.table_item_associations[author_item] = (book.set_author)

        if new:
            title_item.setBackground(BookList.new_bg_item_colour)
            author_item.setBackground(BookList.new_bg_item_colour)
            date_item.setBackground(BookList.new_bg_item_colour)

        self.table_widget.setItem(row_num, 0, title_item)
        self.table_widget.setItem(row_num, 1, author_item)
        self.table_widget.setItem(row_num, 2, date_item)

    def read_book_list(self):
        """Read a book list from file. If there are any new books that have been added,
        will write them to the file before reading a new set of books. The books
        are read from file in a json format.

        """
        if self.new_books: # if there are new books, write them to file before resetting
            self.write_book_list()

        self.books = []
        self.new_books = []

        with open(self.get_list_file(), 'r') as f:
            try:
                for book_json in json.loads(f.read()):
                    self.books.append(Book(book_json["title"], book_json["author"], book_json["date"]))
            except ValueError as e:
                f.seek(0) # go back to the start of the file - read sends us to the end
                # this probably happens if you load a list with the old csv syntax
                for line in f:
                    sp = line.split(',')
                    self.books.append(Book(sp[2], sp[1], sp[0]))

        self.populate_table_widget()

    def write_book_list(self):
        """Write the books to file. This writes books that existed in the file when it
        was first loaded, and books which were added in the session. In this way
        we automatically transfer modifications to any books without having to
        check which books were modified and just changing those bits.

        """
        if not self.get_list_file():
            return False
        else:
            with open(self.get_list_file(), 'w') as f:
                all_books = self.books + self.new_books
                book_dicts = []
                for book in all_books:
                    book_dicts.append(book.__dict__)

                f.write(json.dumps(book_dicts, indent=1))

            return True

    def reset_add_view(self):
        """Reset the add view to a default state. The title and author entries are
        cleared, and the focus is set on the title. If the author_lock checkbox
        is checked, then we do not reset the author string to empty.

        """
        self.title_input.setText("")
        self.title_input.setFocus()

        if not self.author_lock.isChecked():
            self.author_input.setText("")

    def add_book(self):
        """Add a book to the list. This book goes into a separate list from the books
        which existed when the file was first loaded. The book is also added to
        the table view. Once the book is added, the add view is reset to a
        default state.

        """
        if not self.author_input.text() or not self.title_input.text():
            result = QMessageBox.warning(self, "Message", "Please enter both an author and title.")
        else:
            self.new_books.append(Book(self.title_input.text(), self.author_input.text(), self.date_input.date().toString("yyyy/MM/dd")))
            self.add_book_to_table_widget(self.new_books[-1], new=True)
            self.reset_add_view()

    def open_new_file(self, force=True):
        """Opens a new file, and will not stop asking until you actually pick one. Will
        first write newly added books to the current list file. If force is
        True, will always ask for a new file. Otherwise, might not ask if the
        list_file exists and is a valid file.

        """
        if len(self.new_books) > 0:
            self.write_book_list()

        while True: # nasty
            self.get_list_file(new=force)
            if self.list_file:
                break

        self.read_book_list()

if __name__ == '__main__':
    app = QApplication(sys.argv)

    if len(sys.argv) > 1:
        list_file = sys.argv[1]
    gui = BookList(list_file)
    gui.show()

    try:
        sys.exit(app.exec_())
    except Exception as e:
        gui.write_book_list()
