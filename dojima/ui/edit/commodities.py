# -*- coding: utf-8 -*-
# Dojima, a markets client.
# Copyright (C) 2012  Emery Hemingway
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public Licnense for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os.path

from PyQt4 import QtCore, QtGui

import dojima.model.commodities


class EditDialog(QtGui.QDialog):

    def __init__(self, parent=None):
        super(EditDialog, self).__init__(parent)

        # Widgets
        self.list_view = CommoditiesListView()
        prefix_edit = QtGui.QLineEdit()
        prefix_edit.setToolTip("optional, eg. $, €")
        suffix_edit = QtGui.QLineEdit()
        suffix_edit.setToolTip("optional, eg. kg, lb")
        precision_spin = QtGui.QSpinBox()
        precision_spin.setMinimum(-99)
        precision_spin.setToolTip(QtCore.QCoreApplication.translate(
            'EditWidget',
            """Decimal precision used to display quantities and prices.\n"""
            """A negative precision is not recommended."""))

        button_box = QtGui.QDialogButtonBox()
        new_button    = button_box.addButton(QtCore.QCoreApplication.translate('EditWidget', "&New"),    button_box.ActionRole)
        delete_button = button_box.addButton(QtCore.QCoreApplication.translate('EditWidget', "&Delete"), button_box.ActionRole)
        save_button   = button_box.addButton(button_box.Save)
        discard_button = button_box.addButton(button_box.Discard)

        edit_layout = QtGui.QFormLayout()
        edit_layout.addRow(QtCore.QCoreApplication.translate('EditWidget', "Prefix:"), prefix_edit)
        edit_layout.addRow(QtCore.QCoreApplication.translate('EditWidget', "Suffix:"), suffix_edit)
        edit_layout.addRow(QtCore.QCoreApplication.translate('EditWidget', "Display precision:"), precision_spin)

        layout = QtGui.QGridLayout()
        layout.addWidget(self.list_view, 0,0)

        layout.addLayout(edit_layout, 0,1)
        layout.addWidget(button_box, 1,0, 1,2)
        self.setLayout(layout)

        # Model
        self.list_view.setModel(dojima.model.commodities.local_model)
        self.list_view.setModelColumn(dojima.model.commodities.local_model.NAME)

        self.mapper = QtGui.QDataWidgetMapper(self)
        self.mapper.setModel(dojima.model.commodities.local_model)
        self.mapper.addMapping(prefix_edit, dojima.model.commodities.local_model.PREFIX)
        self.mapper.addMapping(suffix_edit, dojima.model.commodities.local_model.SUFFIX)
        self.mapper.addMapping(precision_spin, dojima.model.commodities.local_model.PRECISION)

        # Connect
        self.list_view.commodityChanged.connect(self.mapper.setCurrentModelIndex)
        new_button.clicked.connect(self.new)
        delete_button.clicked.connect(self.delete)
        save_button.clicked.connect(self.save)
        discard_button.clicked.connect(self.reject)

        # Select
        index = dojima.model.commodities.local_model.index(0, dojima.model.commodities.local_model.NAME)
        self.list_view.setCurrentIndex(index)
        self.mapper.toFirst()

    def delete(self):
        # TODO Check if any markets use the selected commodity
        row = self.mapper.currentIndex()
        dojima.model.commodities.local_model.removeRow(row)
        
    def new(self):
        row = dojima.model.commodities.local_model.new_commodity()
        self.mapper.setCurrentIndex(row)
        index = dojima.model.commodities.local_model.index(
            row, dojima.model.commodities.local_model.NAME)
        self.list_view.setCurrentIndex(index)
        self.list_view.setFocus()
        self.list_view.edit(index)

    def save(self):
        dojima.model.commodities.local_model.submit()
        self.accept()


class CommoditiesListView(QtGui.QListView):

    commodityChanged = QtCore.pyqtSignal(QtCore.QModelIndex)

    def currentChanged(self, current, previous):
        self.commodityChanged.emit(current)

class NewCommodityDialog(QtGui.QDialog):

    def __init__(self, parent, name='', prefix='', suffix=''): #, precision=0):
        super(NewCommodityDialog, self).__init__(parent)

        self.name_edit = QtGui.QLineEdit(name)
        self.prefix_edit = QtGui.QLineEdit(prefix + " ")
        self.suffix_edit = QtGui.QLineEdit(" " + suffix)

        self.precision_spin = QtGui.QSpinBox()
        self.precision_spin.setValue(4)
        self.precision_spin.setMinimum(-99)

        button_box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok |
                                            QtGui.QDialogButtonBox.Cancel)

        form_layout = QtGui.QFormLayout()
        form_layout.addRow(QtCore.QCoreApplication.translate('NewCommodityDialog', "name:"), self.name_edit)
        form_layout.addRow(QtCore.QCoreApplication.translate('NewCommodityDialog', "prefix:"), self.prefix_edit)
        form_layout.addRow(QtCore.QCoreApplication.translate('NewCommodityDialog', "suffix:"), self.suffix_edit)
        form_layout.addRow(QtCore.QCoreApplication.translate('NewCommodityDialog', "display precision:"), self.precision_spin)

        layout = QtGui.QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(button_box)
        self.setLayout(layout)

        button_box.accepted.connect(self.save)
        button_box.rejected.connect(self.reject)

    def save(self):
        # TODO search for redundant commodities
        self.row = dojima.model.commodities.local_model.newCommodity()

        dojima.model.commodities.local_model.item(
            self.row, dojima.model.commodities.local_model.NAME).setText(self.name_edit.text())

        dojima.model.commodities.local_model.item(
            self.row, dojima.model.commodities.local_model.PREFIX).setText(self.prefix_edit.text())

        dojima.model.commodities.local_model.item(
            self.row, dojima.model.commodities.local_model.SUFFIX).setText(self.suffix_edit.text())

        dojima.model.commodities.local_model.item(
            self.row, dojima.model.commodities.local_model.PRECISION).setText(self.precision_spin.cleanText())
        print(self.precision_spin.cleanText())
        
        #item = QtGui.QStandardItem(self.precision_spin.text())
        #dojima.model.commodities.local_model.setItem(
        #    self.row, dojima.model.commodities.local_model.PRECISION, item)

        dojima.model.commodities.local_model.submit()
        self.uuid = dojima.model.commodities.local_model.item(
            self.row, dojima.model.commodities.local_model.ID).data(QtCore.Qt.UserRole)
        self.accept()
