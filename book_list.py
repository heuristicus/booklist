#!/usr/bin/env python

import sys
import os
import signal
import datetime

from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog, QPushButton, QMessageBox, QLineEdit, QMainWindow, QGridLayout, QVBoxLayout, QDesktopWidget, QAction, QHBoxLayout, QLabel, QShortcut, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QSpacerItem, QMainWindow
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor

class Book():
    def __init__(self, title, author, date):
        self.title = title
        self.author = author
        self.add_date = date

    def get_date_str(self):
        return self.add_date.strftime("%Y/%m/%d")

    def csv_str(self):
        return "{0},{1},{2}".format(self.get_date_str(), self.author, self.title)

    def __repr__(self):
        return "{0}: {1} - {2}".format(self.get_date_str(), self.author, self.title)

class BookList(QMainWindow):

    def __init__(self):
        super(BookList, self).__init__()

        self.list_file = None
        self.books = []
        self.new_books = []

        self.create_window()

        while not self.list_file:
            self.open_new_file()

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

        self.add_shortcut = QShortcut("Return", self)
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

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.add_book)
        self.add_btn.setMaximumWidth(500)

        self.input_layout = QGridLayout()
        self.input_layout.addWidget(self.title_label, 0, 1)
        self.input_layout.addWidget(self.title_input, 0, 2)
        self.input_layout.addWidget(self.author_label, 1, 1)
        self.input_layout.addWidget(self.author_input, 1, 2)
        self.input_layout.addWidget(self.author_lock, 1, 3)
        self.input_layout.addWidget(self.add_btn, 2, 2)


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

    def setup_menubar(self):
        open_action = QAction('&Open', self)
        open_action.setShortcut('Ctrl+o')
        open_action.setStatusTip('Select list file')
        open_action.triggered.connect(self.open_new_file)

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(open_action)

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def closeEvent(self, event):
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

    def read_book_list(self):
        if self.new_books: # if there are new books, write them to file before resetting
            self.write_book_list()

        self.books = []
        self.new_books = []

        with open(self.get_list_file(), 'r') as f:
            for line in f:
                sp = line.split(',')
                self.books.append(Book(sp[2], sp[1], datetime.datetime.strptime(sp[0], "%Y/%m/%d").date()))

        self.populate_table_widget()

    def populate_table_widget(self):
        for num, book in enumerate(self.books):
            self.table_widget.insertRow(num)
            self.table_widget.setItem(num, 0, QTableWidgetItem(book.title))
            self.table_widget.setItem(num, 1, QTableWidgetItem(book.author))
            self.table_widget.setItem(num, 2, QTableWidgetItem(book.get_date_str()))

    def add_book_to_table_widget(self, book):
        row_num = self.table_widget.rowCount()
        new_bg = QColor(40,150,190)
        self.table_widget.insertRow(row_num)

        title_item = QTableWidgetItem(book.title)
        title_item.setBackground(new_bg)
        author_item = QTableWidgetItem(book.author)
        author_item.setBackground(new_bg)
        date_item = QTableWidgetItem(book.get_date_str())
        date_item.setBackground(new_bg)

        self.table_widget.setItem(row_num, 0, title_item)
        self.table_widget.setItem(row_num, 1, author_item)
        self.table_widget.setItem(row_num, 2, date_item)

    def write_book_list(self):
        if not self.get_list_file():
            return False
        else:
            with open(self.get_list_file(), 'a+') as f:
                for book in self.new_books:
                    f.write(book.csv_str() + "\n")

            return True

    def add_book(self):
        if not self.author_input.text() or not self.title_input.text():
            result = QMessageBox.warning(self, "Message", "Please enter both an author and title.")
        else:
            self.new_books.append(Book(self.title_input.text(), self.author_input.text(), datetime.datetime.today()))
            self.add_book_to_table_widget(self.new_books[-1])
            self.title_input.setText("")
            self.title_input.setFocus()

            if not self.author_lock.isChecked():
                self.author_input.setText("")

    def open_new_file(self):
        if len(self.new_books) > 0:
            self.write_book_list()

        self.get_list_file(new=True)
        self.read_book_list()

if __name__ == '__main__':
    app = QApplication(sys.argv)

    gui = BookList()
    gui.show()

    try:
        sys.exit(app.exec_())
    except Exception as e:
        gui.write_book_list()
