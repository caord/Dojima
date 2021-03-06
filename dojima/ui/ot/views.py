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
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

import otapi
from PyQt4 import QtCore, QtGui

import dojima.ui.ot.nym


class MarketTableView(QtGui.QTableView):

    marketChanged = QtCore.pyqtSignal(str)
    baseChanged = QtCore.pyqtSignal(str)
    counterChanged = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(MarketTableView, self).__init__(
            parent, contextMenuPolicy=QtCore.Qt.ActionsContextMenu)

        fetch_contract_action = QtGui.QAction(
            QtCore.QCoreApplication.translate('MarketTableView',
                                              "fetch these missing contracts",
                                              "the menu option to request a "
                                              "contract from the server."),
            self, triggered=self.refreshContract)
        self.addAction(fetch_contract_action)

        fetch_all_contracts_action = QtGui.QAction(
            QtCore.QCoreApplication.translate('MarketTableView',
                                              "fetch all missing contracts",
                                              "the menu option to request all "
                                              "contract in markets from the server."),
            self, triggered=self.refreshAllContracts)
        self.addAction(fetch_all_contracts_action)

    def currentChanged(self, current, previous):
        row = current.row()
        model = self.model()
        self.marketChanged.emit(model.getMarketId(row))
        index = model.index(row, model.BASE)
        self.baseChanged.emit(model.data(index, QtCore.Qt.UserRole))
        index = model.index(row, model.COUNTER)
        self.counterChanged.emit(model.data(index, QtCore.Qt.UserRole))

    def refreshContract(self):
        pass
        """
        row = self.currentIndex().row()
        if otapi.OTAPI_Basic_GetNymCount() == 1:
            nym_id = otapi.OTAPI_Basic_GetNym_ID(0)
        else:
            dialog = dojima.ui.ot.nym.SelectNymDialog(self)
            if not dialog.exec_():
                return

            nym_id = dialog.nym_id

        model = self.model()
        for column in (model.BASE, model.COUNTER):
            contract_item = model.item(row, column)
            contract_id = contract_item.data(QtCore.Qt.UserRole)
            objEasy.load_or_retrieve_contract(model.server_id, nym_id, contract_id)
            contract_item.setText(otapi.OTAPI_Basic_GetAssetType_Name(contract_id))
            """

    def refreshAllContracts(self):

        if otapi.OTAPI_Basic_GetNymCount() == 1:
            nym_id = otapi.OTAPI_Basic_GetNym_ID(0)
        else:
            dialog = dojima.ui.ot.nym.SelectNymDialog(self)
            if not dialog.exec_():
                return

        nym_id = dialog.nym_id
        model = self.model()
        for row in range(model.rowCount()):
            for column in (model.BASE, model.COUNTER):
                contract_item = model.item(row, column)
                contract_id = contract_item.data(QtCore.Qt.UserRole)

                objEasy.load_or_retrieve_contract(model.server_id, nym_id, contract_id)
                contract_name = otapi.OTAPI_Basic_GetAssetType_Name(contract_id)
                if contract_name != contract_item.text():
                    contract_item.setText(contract_name)


class AccountComboBox(QtGui.QComboBox):
    """ QComboBox for OT accounts

    This combo does not come with an model, but it does have
    remote_commodity_id and remote_commodity_name Qt Properties.

    """
    # TODO find a place to put an OT ID verification function

    accountIdChanged = QtCore.pyqtSignal(str)

    def __init__(self, model=dojima.model.ot.accounts.model, parent=None):
        super(AccountComboBox, self).__init__(parent)
        self.setModel(model)
        self.currentIndexChanged[int].connect(self.emitAccountId)

    def emitAccountId(self, row):
        self.accountIdChanged.emit(self.itemData(row, QtCore.Qt.UserRole))

    def getAccountId(self):
        return self.itemData(self.currentIndex(), QtCore.Qt.UserRole)

    @QtCore.pyqtProperty(str)
    def remoteAssetId(self):
        ot_id = self.itemData(self.currentIndex(), QtCore.Qt.UserRole)
        if len(ot_id) != 43: return ''
        ot_id = otapi.OTAPI_Basic_GetAccountWallet_AssetTypeID(ot_id)
        if len(ot_id) != 43: return ''
        return ot_id

    @QtCore.pyqtProperty(str)
    def remoteAssetName(self):
        ot_id = self.itemData(self.currentIndex(), QtCore.Qt.UserRole)
        if len(ot_id) != 43: return ''
        ot_id = otapi.OTAPI_Basic_GetAccountWallet_AssetTypeID(ot_id)
        if len(ot_id) != 43: return ''
        return otapi.OTAPI_Basic_GetAssetType_Name(ot_id)

class NymComboBox(QtGui.QComboBox):

    nymIdChanged = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(NymComboBox, self).__init__(parent)
        self.setModel(dojima.model.ot.nyms.model)
        self.currentIndexChanged[int].connect(self.emitNymId)

    def emitNymId(self, row):
        self.nymIdChanged.emit(self.itemData(row, QtCore.Qt.UserRole))

    @QtCore.pyqtProperty(str)
    def nymId(self):
        return self.itemData(self.currentIndex(), QtCore.Qt.UserRole)
        

class ServerComboBox(QtGui.QComboBox):
    """ QComboBox for OT Servers
    """

    serverIdChanged = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(ServerComboBox, self).__init__(parent)
        self.setModel(dojima.model.ot.servers.model)
        self.currentIndexChanged[int].connect(self.emitServerId)

    def emitServerId(self, row):
        self.serverIdChanged.emit(self.itemData(row, QtCore.Qt.UserRole))
            
    @QtCore.pyqtProperty(str)
    def serverId(self):
        ot_id = self.itemData(self.currentIndex(), QtCore.Qt.UserRole)
        assert ot_id
        return ot_id
