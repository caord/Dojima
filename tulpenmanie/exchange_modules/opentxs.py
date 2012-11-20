# Tulpenmanie, a markets client.
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
from Queue import Queue

import otapi
from PyQt4 import QtCore, QtGui

import tulpenmanie.markets
import tulpenmanie.exchanges
import tulpenmanie.exchange
import tulpenmanie.data.ticker
import tulpenmanie.model.ot.accounts
import tulpenmanie.model.ot.assets
import tulpenmanie.model.ot.markets
import tulpenmanie.ot.contract
import tulpenmanie.ui.ot.nym
import tulpenmanie.ui.ot.offer
import tulpenmanie.ui.ot.views

# i don't really want to import gui stuff here
import tulpenmanie.ui.ot.account


logger = logging.getLogger(__name__)


def saveMarketAccountSettings(server_id, market_id, b_ac_id, c_ac_id):
    settings = QtCore.QSettings()
    settings.beginGroup('OT-defaults')
    settings.beginGroup(server_id)
    settings.beginGroup(market_id)
    settings.setValue('base_account', b_ac_id)
    settings.setValue('counter_account', c_ac_id)


class OTExchangeProxy(object, tulpenmanie.exchange.ExchangeProxy):

    def __init__(self, serverId, marketList):
        self.id = serverId
        self.market_list = marketList
        self.exchange_object = None
        self.local_market_map = dict()
        self.remote_market_map = dict()

    @property
    def name(self):
        return otapi.OT_API_GetServer_Name(self.id)

    def getExchangeObject(self):
        if self.exchange_object is None:
            self.exchange_object = OTExchange(self.id)

        return self.exchange_object

    def getLocalMapping(self, key):
        return self.local_market_map[key]

    def getRemoteMapping(self, key):
        return self.remote_market_map[key]

    #def getLocalMarketIDs(self, remoteMarketID):
    #    return self.local_market_map[remoteMarketID]

    def getRemoteMarketIDs(self, localPair):
        print self.local_market_map
        return self.local_market_map[ str(localPair)]

    def getPrettyMarketName(self, remote_market_id):
        print "marketid", remote_market_id
        storable = otapi.QueryObject(otapi.STORED_OBJ_MARKET_LIST,
                                     'markets', self.id,
                                     'market_data.bin')
        market_list = otapi.MarketList.ot_dynamic_cast(storable)
        for i in range(market_list.GetMarketDataCount()):
            data = market_list.GetMarketData(i)
            if data.market_id == remote_market_id: break
            print "market scale", data.scale
            return QtCore.QCoreApplication.translate('OTExchangeProxy',
                "Scale %1",
                "The market scale, there should be a note on this somewhere "
                "around here.").arg(data.scale)
        return "couldn't find scale"

    def nextPage(self, wizard=None):
        return OTServerWizardPage(self.name, self.id, wizard)

    def remoteToLocal(self, marketID):
        return self.remote_market_map[marketID]


class OTServerWizardPage(QtGui.QWizardPage):

    def __init__(self, title, server_id, parent):
        super(OTServerWizardPage, self).__init__(parent)
        self.wizard = parent
        self.server_id = server_id
        self.setTitle(title)
        self.setSubTitle(
            QtCore.QCoreApplication.translate('OTServerWizardPage',
                "Select accounts to match a new or existing market.",
                "This is the the heading underneath the title on the "
                "OT page in the markets wizard."))

    def changeBaseAsset(self, asset_id):
        self.base_accounts_model.setFilterFixedString(asset_id)

    def changeCounterAsset(self, asset_id):
        self.counter_accounts_model.setFilterFixedString(asset_id)

    #def changeMarket(self, market_id):
        #print market_id

    def changeNym(self, nym_id):
        self.nym_accounts_model.setFilterFixedString(nym_id)

    def initializePage(self):
        self.nyms_model = tulpenmanie.model.ot.nyms.model
        self.markets_model = tulpenmanie.model.ot.markets.OTMarketsModel(
            self.server_id)
        accounts_model = tulpenmanie.model.ot.accounts.OTServerAccountsModel(
            self.server_id)

        simple_accounts_model = tulpenmanie.model.ot.accounts.OTAccountsProxyModel()
        simple_accounts_model.setSourceModel(accounts_model)
        simple_accounts_model.setFilterRole(QtCore.Qt.UserRole)
        simple_accounts_model.setFilterKeyColumn(accounts_model.TYPE)
        simple_accounts_model.setFilterFixedString('s')
        simple_accounts_model.setDynamicSortFilter(True)

        self.nym_accounts_model = tulpenmanie.model.ot.accounts.OTAccountsProxyModel()
        self.nym_accounts_model.setSourceModel(simple_accounts_model)
        self.nym_accounts_model.setFilterRole(QtCore.Qt.UserRole)
        self.nym_accounts_model.setFilterKeyColumn(accounts_model.NYM)
        self.nym_accounts_model.setDynamicSortFilter(True)

        self.base_accounts_model = tulpenmanie.model.ot.accounts.OTAccountsProxyModel()
        self.base_accounts_model.setSourceModel(self.nym_accounts_model)
        self.base_accounts_model.setFilterRole(QtCore.Qt.UserRole)
        self.base_accounts_model.setFilterKeyColumn(accounts_model.ASSET)
        self.base_accounts_model.setDynamicSortFilter(True)

        self.counter_accounts_model = tulpenmanie.model.ot.accounts.OTAccountsProxyModel()
        self.counter_accounts_model.setSourceModel(self.nym_accounts_model)
        self.counter_accounts_model.setFilterRole(QtCore.Qt.UserRole)
        self.counter_accounts_model.setFilterKeyColumn(accounts_model.ASSET)
        self.counter_accounts_model.setDynamicSortFilter(True)

        self.markets_view = tulpenmanie.ui.ot.views.MarketTableView()
        self.markets_view.setSelectionBehavior(self.markets_view.SelectRows)
        self.markets_view.setSelectionMode(self.markets_view.SingleSelection)
        self.markets_view.setModel(self.markets_model)
        self.markets_view.setShowGrid(False)

        self.nym_combo = tulpenmanie.ui.ot.views.ComboBox()
        self.nym_combo.setModel(self.nyms_model)
        nym_label = QtGui.QLabel(
            QtCore.QCoreApplication.translate('OTServerWizardPage',
                                              "Server Nym:",
                                              "The label next to the nym "
                                              "combo box."))
        nym_label.setBuddy(self.nym_combo)
        new_nym_button = QtGui.QPushButton(
            QtCore.QCoreApplication.translate('OTServerWizardPage',
                                              "New Nym",
                                              "The button next to the nym"
                                              "combo box."))
        self.base_account_combo = tulpenmanie.ui.ot.views.ComboBox()
        base_label = QtGui.QLabel(
            QtCore.QCoreApplication.translate('OTServerWizardPage',
                                              "Base account:",
                                              "The account of the base asset to "
                                              "use with this market."))
        base_label.setBuddy(self.base_account_combo)
        self.counter_account_combo = tulpenmanie.ui.ot.views.ComboBox()
        counter_label = QtGui.QLabel(
            QtCore.QCoreApplication.translate('OTServerWizardPage',
                                              "Counter account:",
                                              "The account of the counter"
                                              "currency to use with this"
                                              "market."))
        counter_label.setBuddy(self.counter_account_combo)

        self.base_account_combo.setModel(self.base_accounts_model)
        self.counter_account_combo.setModel(self.counter_accounts_model)

        new_offer_button = QtGui.QPushButton(
            QtCore.QCoreApplication.translate('OTServerWizardPage',
                                              "New Offer",
                                              "Button to pop up the new offer "
                                              "dialog."))

        new_account_button = QtGui.QPushButton(
            QtCore.QCoreApplication.translate('OTServerWizardPage',
                                              "New Account",
                                              "Button to pop up the new account "
                                              "dialog."))

        refresh_markets_button = QtGui.QPushButton(
            QtCore.QCoreApplication.translate('OTServerWizardPage',
                                              "Refresh Markets",
                                              "Button to refresh the listed "
                                              "markets on the server."))

        # Layout could use some work, sizes look wrong
        layout = QtGui.QGridLayout()
        layout.addWidget(self.markets_view, 0,0, 1,4)
        layout.addWidget(nym_label, 1,0)
        layout.addWidget(self.nym_combo, 1,1, 1,2)
        layout.addWidget(new_nym_button, 1,3)
        layout.addWidget(base_label, 2,0, 1,2)
        layout.addWidget(counter_label, 2,2, 1,2)
        layout.addWidget(self.base_account_combo, 3,0, 1,2)
        layout.addWidget(self.counter_account_combo, 3,2, 1,2)
        layout.addWidget(new_offer_button, 4,0)
        layout.addWidget(new_account_button, 4,3)
        layout.addWidget(refresh_markets_button, 4,2)
        self.setLayout(layout)

        self.markets_view.baseChanged.connect(self.changeBaseAsset)
        self.markets_view.counterChanged.connect(self.changeCounterAsset)
        #self.markets_view.marketChanged.connect(self.changeMarket)

        self.base_account_combo.currentIndexChanged.connect(
            self.completeChanged.emit)
        self.counter_account_combo.currentIndexChanged.connect(
            self.completeChanged.emit)

        new_nym_button.clicked.connect(self.showNewNymDialog)
        new_offer_button.clicked.connect(self.showNewOfferDialog)
        new_account_button.clicked.connect(self.showNewAccountDialog)
        refresh_markets_button.clicked.connect(self.refreshMarkets)
        self.nym_combo.otIdChanged.connect(self.changeNym)

        # select
        self.markets_view.selectRow(0)
        self.nym_combo.currentIndexChanged.emit(0)

    def isComplete(self):
        return (self.base_account_combo.getOTID() !=
                self.counter_account_combo.getOTID())

    def isFinalPage(self):
        return True

    def refreshMarkets(self):
        self.markets_model.refresh(self.nym_combo.getOTID())

    def showNewAccountDialog(self):
        dialog = tulpenmanie.ui.ot.account.NewAccountDialog(self.server_id, self)
        if dialog.exec_():
            self.nym_accounts_model.refresh()

    def showNewNymDialog(self):
        dialog = tulpenmanie.ui.ot.nym.CreateNymDialog(self)
        if dialog.exec_():
            self.nyms_model.refresh()

    def showNewOfferDialog(self):
        dialog = tulpenmanie.ui.ot.offer.NewOfferDialog(self.server_id)
        if dialog.exec_():
            self.refreshMarkets()

    def validatePage(self):
        nym_id = self.nym_combo.getOTID()
        b_ac_id = self.base_account_combo.getOTID()
        c_ac_id = self.counter_account_combo.getOTID()

        b_as_id = otapi.OT_API_GetAccountWallet_AssetTypeID( str(b_ac_id))
        c_as_id = otapi.OT_API_GetAccountWallet_AssetTypeID( str(c_ac_id))

        storable = otapi.QueryObject(otapi.STORED_OBJ_MARKET_LIST,
                                     'markets', self.server_id,
                                     'market_data.bin')
        market_list = otapi.MarketList.ot_dynamic_cast(storable)
        market_id = None
        for i in range(market_list.GetMarketDataCount()):
            data = market_list.GetMarketData(i)
            if (data.asset_type_id == b_as_id and
                data.currency_type_id == c_as_id):
                saveMarketAccountSettings(self.server_id, data.market_id,
                                   b_ac_id, c_ac_id)

        # get the base asset factor and set the scale to that

        contract = tulpenmanie.ot.contract.CurrencyContract(b_as_id)
        factor = contract.getFactor()

        return True

        # Now do whatever MainWindow does and create that dock thing
        # scratch that, just save the settings, and the when the wizard closes
        # the mainwindow can reload the markets


class OTExchange(QtCore.QObject, tulpenmanie.exchange.Exchange):

    exchange_error_signal = QtCore.pyqtSignal(str)
    balance_proxies = dict()

    def __init__(self, serverID, parent=None):
        super(OTExchange, self).__init__(parent)
        self.server_id = serverID
        self.account_object = None
        self.ticker_proxies = dict()
        self.ticker_clients = dict()
        # market_id -> [base_id, counter_id]
        self.assets = dict()
        # market_id -> [base_account_id, counter_account_id]
        self.accounts = dict()
        # market_id -> scale
        self.scales = dict()

        storable = otapi.QueryObject(otapi.STORED_OBJ_MARKET_LIST, 'markets',
                                     self.server_id, 'market_data.bin')
        market_list = otapi.MarketList.ot_dynamic_cast(storable)
        for i in range(market_list.GetMarketDataCount()):
            data = market_list.GetMarketData(i)
            market_id = data.market_id
            self.assets[market_id] = (data.asset_type_id, data.currency_type_id)
            self.scales[market_id] = data.scale

        # The request timer and queues
        self.request_timer = QtCore.QTimer(self)
        self.request_timer.timeout.connect(self.sendRequest)
        # Just start the timer at init()
        self.request_timer.start(512)
        # the server get offers but doesn't immedialty update the best prices,
        # find out what that update period is and set the refresh rate to that
        self.ticker_clients = 0
        self.ticker_timer = QtCore.QTimer(self)
        self.ticker_timer.timeout.connect(self.enqueueGetMarketList)
        self.getaccount_queue = Queue()
        self.getRequestNumber_queue = Queue()
        self.getMarketList_queue = Queue()
        self.getNymOffers_queue = Queue()
        self.offer_queue = Queue()
        self.trades_queue = Queue()

        settings = QtCore.QSettings()
        settings.beginGroup('OT_Servers')
        settings.beginGroup(self.server_id)
        self.nym_id = str(settings.value('nym', ''))
        settings.beginGroup('markets')
        for market_id in settings.childGroups():
            b_ac_id = str(settings.value('base_account', ''))
            c_ac_id = str(settings.value('counter_account', ''))
            self.accounts[str(market_id)] = [b_ac_id, c_ac_id]

    def changeNym(self, nym_id):
        self.nym_id = str(nym_id)
        settings = QtCore.QSettings()
        settings.beginGroup('OT_Servers')
        settings.beginGroup(self.server_id)
        settings.setValue('nym', nym_id)
        if not otapi.OT_API_IsNym_RegisteredAtServer(self.nym_id,
                                                     self.server_id):
            r = otapi.OT_API_createUserAccount(self.server_id, self.nym_id)
            if r < 1:
                QtGui.QApplication.restoreOverrideCursor()
                QtGui.QMessageBox.error(self,
                    QtCore.QCoreApplication.translate('OTExchange',
                        "Error registering nym"),
                    QtCore.QCoreApplication.translate('OTExchange'
                        "Error registering the nym with the server."))
                return
        else:
            if otapi.OT_API_GetNym_TransactionNumCount(self.server_id,
                                                       self.nym_id) < 48:
                logger.info("Requesting more transaction numbers")
                otapi.OT_API_getTransactionNumber(self.server_id, self.nym_id)

    def changeBaseAccount(self, market_id, account_id):
        settings = QtCore.QSettings()
        settings.beginGroup('OT_Servers')
        settings.beginGroup(self.server_id)
        settings.beginGroup('markets')
        settings.beginGroup(market_id)
        settings.setValue('base_account', account_id)
        if market_id in self.accounts:
            self.accounts[market_id][0] = account_id
        else:
            self.accounts[market_id] = [account_id, None]

        if self.account_object:
            self.account_object.changeBaseAccount(market_id, account_id)

    def changeCounterAccount(self, market_id, account_id):
        settings = QtCore.QSettings()
        settings.beginGroup('OT_Servers')
        settings.beginGroup(self.server_id)
        settings.beginGroup('markets')
        settings.beginGroup(market_id)
        settings.setValue('counter_account', account_id)
        if market_id in self.accounts:
            self.accounts[market_id][1] = account_id
        else:
            self.accounts[market_id] = [None, account_id]

        if self.account_object:
            self.account_object.changeCounterAccount(market_id, account_id)

    def echoTicker(self, market_id=None):
        self.readMarketList()

    def enqueueGetMarketList(self):
        self.getMarketList_queue.put(None)

    def getAccountObject(self):
        if self.account_object is None:
            self.account_object = OTExchangeAccount(self)

        return self.account_object

    def getFactors(self, market_id):
        b_asset_id, c_asset_id = self.assets[market_id]
        b_contract = tulpenmanie.ot.contract.CurrencyContract(b_asset_id)
        c_contract = tulpenmanie.ot.contract.CurrencyContract(c_asset_id)
        return ( b_contract.getFactor(), c_contract.getFactor(), )

    def getRemotePair(self, market_id):
        return self.assets[market_id]

    def getScale(self, market_id):
        return int(self.scales[market_id])

    def getTickerProxy(self, market_id):
        if market_id not in self.ticker_proxies:
            ticker_proxy = tulpenmanie.data.ticker.TickerProxy(self)
            self.ticker_proxies[market_id] = ticker_proxy
            return ticker_proxy
        return self.ticker_proxies[market_id]

    def populateMenuBar(self, menu_bar, market_id):

        # Make submenus
        exchange_menu = menu_bar.getExchangeMenu()
        nyms_menu = CurrentNymMenu(
            QtCore.QCoreApplication.translate('OTExchange', "No nym selected",
                                              "The text that is displayed in "
                                              "the exchange menu until a nym "
                                              "for this exchange server is "
                                              "chosen."),
            exchange_menu)
        exchange_menu.addMenu(nyms_menu)

        b_as_id, c_as_id = self.assets[market_id]
        if market_id in self.accounts:
            b_ac_id, c_ac_id = self.accounts[market_id]
        else:
            b_ac_id, c_ac_id = None, None
        account_main_menu = menu_bar.getAccountMenu()
        b_ac_menu = NymAccountMenu(
            QtCore.QCoreApplication.translate('OTExchange', "Base Account",
                "Title of a submenu to select the account that will hold the "
                "base asset."),
                b_as_id, market_id, self.changeBaseAccount,
                self.nym_id, b_ac_id, account_main_menu)
        c_ac_menu = NymAccountMenu(
            QtCore.QCoreApplication.translate('OTExchange', "Counter Account",
                "Title of a submenu to select the account that will hold the "
                "counter asset."),
                c_as_id, market_id, self.changeCounterAccount,
                self.nym_id, c_ac_id, account_main_menu)
        account_main_menu.addMenu(b_ac_menu)
        account_main_menu.addMenu(c_ac_menu)

        # create actions
        nyms_group = QtGui.QActionGroup(exchange_menu)
        for i in range(otapi.OT_API_GetNymCount()):
            nym_id = otapi.OT_API_GetNym_ID(i)
            nym_label = otapi.OT_API_GetNym_Name(nym_id)
            action = ChangeOTThingAction(nym_id, nym_label, nyms_menu)
            action.setActionGroup(nyms_group)
            nyms_menu.addAction(action)
            action.currentLabelChanged.connect(nyms_menu.changeTitle)
            action.currentIDChanged.connect(c_ac_menu.setNymId)
            action.currentIDChanged.connect(b_ac_menu.setNymId)
            if nym_id == self.nym_id: action.trigger()
            # no sense changing the nym needlessly
            action.currentIDChanged.connect(self.changeNym)

    def readMarketList(self):
        storable = otapi.QueryObject(otapi.STORED_OBJ_MARKET_LIST,
                                     'markets', self.server_id,
                                     'market_data.bin')
        if not storable: return
        market_list = otapi.MarketList.ot_dynamic_cast(storable)
        for i in range(market_list.GetMarketDataCount()):
            data = market_list.GetMarketData(i)
            if data.market_id in self.ticker_proxies:
                proxy = self.ticker_proxies[data.market_id]
                proxy.ask_signal.emit(int(data.current_ask))
                proxy.last_signal.emit(int(data.last_sale_price))
                proxy.bid_signal.emit(int(data.current_bid))

    def sendRequest(self):
        # if the timer is the only one to call this it shouldn't block
        if not self.getRequestNumber_queue.empty():
            r = otapi.OT_API_getRequest(self.server_id, self.nym_id)
            if r > 0:
                logger.error("request number request failed")
                self.getRequestNumber_queue.get_nowait()
            return

        if not self.offer_queue.empty():
            tcount = otapi.OT_API_GetNym_TransactionNumCount(self.server_id,
                                                             self.nym_id)
            if tcount < 3:
                logger.info("Only %s transaction numbers, requesting more",
                            tcount)
                otapi.OT_API_getRequest(self.server_id, self.nym_id)
                r = otapi.OT_API_getTransactionNumber(self.server_id,
                                                      self.nym_id)
                if r < 1:
                    logger.error("requesting more transaction numbers failed")
                    self.getRequestNumber_queue.put(None)
                return

            # MARKET_SCALE,	Defaults to minimum of 1. Market granularity.
            # MINIMUM_INCREMENT, This will be multiplied by the Scale. Min 1.
            # TOTAL_ASSETS_ON_OFFER, Total assets available for sale or purchase.
            # Will be multiplied by minimum increment.

            # SELLING == OT_TRUE, BUYING == OT_FALSE

            market_id, total, price, buy_sell = self.offer_queue.get()
            base_asset_id, counter_asset_id = self.assets[market_id]
            base_account_id, counter_account_id = self.accounts[market_id]
            scale = self.scales[market_id]
            increment = 1
            r = otapi.OT_API_issueMarketOffer(self.server_id, self.nym_id,
                                              base_asset_id, base_account_id,
                                              counter_asset_id,
                                              counter_account_id,
                                              str(scale), str(increment),
                                              str(total), str(price), buy_sell)
            if r < 1:
                logger.error("issue market offer failed")
                self.getRequestNumber_queue.put(None)
                self.offer_queue.put( (market_id, total, price, buy_sell,) )
            return

        if not self.getaccount_queue.empty():
            account_id = self.getaccount_queue.get_nowait()
            r = otapi.OT_API_getAccount(self.server_id, self.nym_id, account_id)
            if r < 1:
                logger.error("account info request failed")
                self.getRequestNumber_queue.put(None)
                self.getaccount_queue.put(acount_id)
                return
            balance = int(otapi.OT_API_GetAccountWallet_Balance(account_id))
            proxy = self.balance_proxies[account_id]
            proxy.balance.emit(balance)
            return

        if not self.getNymOffers_queue.empty():
            self.getNymOffers_queue.get_nowait()
            logger.info('requesting nym %s offer list from %s', self.nym_id,
                                                                self.server_id)
            r = otapi.OT_API_getNym_MarketOffers(self.server_id, self.nym_id)
            if r < 1:
                logger.error("nym market offers request failed")
                self.getRequestNumber_queue.put(None)
                self.getNymOffers_queue.put(None)
                return
            self.account_object.readNymOffers()
            return

        if not self.getMarketList_queue.empty():
            self.getMarketList_queue.get_nowait()
            r = otapi.OT_API_getMarketList(self.server_id, self.nym_id)
            if r < 1:
                logger.error("market list/info request failed")
                self.getRequestNumber_queue.put(None)
                return
            self.readMarketList()
            return

        if not self.trades_queue.empty():
            market_id = self.trades_queue.get_nowait()
            logger.info('requesting %s trade list from %s',
                        market_id, self.server_id)
            r = otapi.OT_API_getMarketRecentTrades(self.server_id, self.nym_id,
                                                   market_id)
            if r < 1:
                self.getRequestNumber_queue.put(None)
                self.trades_queue.put(market_id)
                return
            self.readTrades(market_id)

    def setDefaultAccounts(self, marketId):
        # I guess we could just read from settings each time, but ram is cheap
        settings = QtCore.QSettings()
        settings.beginGroup('OT-defaults')
        settings.beginGroup(self.server_id)
        settings.setValue('nym', self.nym_id)

        b_ac_id, c_ac_id = self.accounts[marketId]
        saveMarketAccountSettings(self.server_id, marketId, b_ac_id, c_ac_id)

    def setTickerStreamState(self, state, market_id):
        if state is True:
            self.startTickerStream(market_id)
            return
        self.stopTickerStream(market_id)

    def showAccountDialog(self, market_id, parent=None):
        base_id, counter_id = self.assets[market_id]
        dialog = tulpenmanie.ui.ot.account.MarketAccountsDialog(self.server_id,
                                                                base_id,
                                                                counter_id,
                                                                parent)
        if dialog.exec_():
            b_ac_i = str(dialog.getBaseAccountId())
            c_ac_i = str(dialog.getCounterAccountId())
            assert (otapi.OT_API_GetAccountWallet_NymID(b_ac_i)
                    == otapi.OT_API_GetAccountWallet_NymID(c_ac_i))
            assert (otapi.OT_API_GetAccountWallet_ServerID(b_ac_i)
                    == otapi.OT_API_GetAccountWallet_ServerID(c_ac_i))

            self.nym_id = str(dialog.getNymId())
            self.accounts[market_id] = (b_ac_i, c_ac_i)
            self.setDefaultAccounts(market_id)
            return True

        return False

    def startTickerStream(self, market_id=None):
        if self.ticker_clients == 0:
            logger.debug("starting ticker stream for %s", self.server_id)
            self.ticker_timer.start(16384)

        self.ticker_clients += 1

    def stopTickerStream(self, market_id=None):
        if self.ticker_clients == 1:
            logger.debug("stopping ticker stream for %s", self.server_id)
            self.ticker_timer.stop()

        self.ticker_clients -= 1
        assert self.ticker_clients >= 0

    def readTrades(self, market_id):
        logger.debug('reading %s trades', market_id)
        storable = otapi.QueryObject(otapi.STORED_OBJ_TRADE_LIST_MARKET,
                                     "markets", self.server_id,
                                     "recent", market_id + ".bin")
        trades = otapi.TradeListMarket.ot_dynamic_cast(storable)
        if not trades:
            return


class OTExchangeAccount(QtCore.QObject, tulpenmanie.exchange.ExchangeAccount):

    exchange_error_signal = QtCore.pyqtSignal(str)
    accountChanged = QtCore.pyqtSignal(str)

    def __init__(self, exchangeObj):
        super(OTExchangeAccount, self).__init__(exchangeObj)
        self.exchange_obj = exchangeObj
        # These are needed for the inherited get proxy methods
        self.base_offers_proxies = dict()
        self.offers_proxies = dict()
        self.offers_model = QtGui.QStandardItemModel()

    def changeBaseAccount(self, market_id, account_id):
        self.accountChanged.emit(market_id)

    def changeCounterAccount(self, market_id, account_id):
        self.accountChanged.emit(market_id)

    def getAccountPair(self, market_id):
        return self.exchange_obj.accounts[market_id]

    def getBalanceProxy(self, account_id):
        if account_id not in self.exchange_obj.balance_proxies:
            proxy = tulpenmanie.data.balance.BalanceProxy(self)
            self.exchange_obj.balance_proxies[account_id] = proxy
            return proxy

        return self.exchange_obj.balance_proxies[account_id]

    def getOffersModel(self, market_id):
        if market_id not in self.offers_proxies:
            base, counter = self.exchange_obj.accounts[market_id]
            if base in self.base_offers_proxies:
                base_proxy = self.base_offers_proxies[base]
            else:
                base_proxy = QtGui.QSortFilterProxyModel()
                base_proxy.setSourceModel(self.offers_model)
                base_proxy.setFilterKeyColumn(1)
                base_proxy.setFilterRole(QtCore.Qt.UserRole)
                base_proxy.setFilterFixedString(base)
                base_proxy.setDynamicSortFilter(True)

            proxy = QtGui.QSortFilterProxyModel()
            proxy.setSourceModel(base_proxy)
            proxy.setFilterKeyColumn(2)
            proxy.setFilterRole(QtCore.Qt.UserRole)
            proxy.setFilterFixedString(counter)
            proxy.setDynamicSortFilter(True)
            self.offers_proxies[market_id] = proxy

            #self.asks_model.setHorizontalHeaderLabels(
            #    ("id",
            #     QtCore.QCoreApplication.translate('AccountWidget',
            #                                       "ask", "sell offer price"),
            #     QtCore.QCoreApplication.translate('AccountWidget',
            #                                       "amount",
            #                                       "sell offer amount")))
            #self.bids_model.setHorizontalHeaderLabels(
            #    ("id",
            #     QtCore.QCoreApplication.translate('AccountWidget',
            #                                       "bid", "buy offer price"),
            #     QtCore.QCoreApplication.translate('AccountWidget',
            #                                       "amount",
            #                                       "buy offer amount")))

            return proxy

        return self.offers_proxies[market_id]

    def hasAccount(self, market_id):
        if market_id not in self.exchange_obj.accounts:
            return False
        base, counter = self.exchange_obj.accounts[market_id]
        if not base or not counter:
            return False

        return True

    def readNymOffers(self):
        storable = otapi.QueryObject(otapi.STORED_OBJ_OFFER_LIST_NYM, 'nyms',
                                     self.exchange_obj.server_id, 'offers',
                                     self.exchange_obj.nym_id + '.bin')
        if not storable: return
        offers = otapi.OfferListNym.ot_dynamic_cast(storable)

        self.offers_model.clear()
        for row in range(offers.GetOfferDataNymCount()):
            offer = offers.GetOfferDataNym(row)

            item = QtGui.QStandardItem(offer.transaction_id)
            self.offers_model.setItem(row, 0, item)

            item = QtGui.QStandardItem()
            item.setData( int(offer.total_assets) - int(offer.finished_so_far),
                          QtCore.Qt.DisplayRole)
            item.setData(offer.asset_acct_id, QtCore.Qt.UserRole)
            self.offers_model.setItem(row, 1, item)

            item = QtGui.QStandardItem()
            item.setData( int(offer.price_per_scale)
                          * int(offer.minimum_increment)
                          * int(offer.scale),
                          QtCore.Qt.DisplayRole)
            item.setData(offer.currency_acct_id, QtCore.Qt.UserRole)
            self.offers_model.setItem(row, 2, item)

            if offer.selling is True: selling = 'a'
            else: selling = 'b'

            item = QtGui.QStandardItem()
            item.setData(selling, QtCore.Qt.DisplayRole)
            self.offers_model.setItem(row, 3, item)

    def refresh(self, market_id):
        self.refreshBalance(market_id)
        self.refreshOffers()

    def refreshBalance(self, market_id):
        for account_id in self.exchange_obj.accounts[market_id]:
            self.exchange_obj.getaccount_queue.put(account_id)

    def refreshOffers(self, market_id=None):
        self.exchange_obj.getNymOffers_queue.put(True)

    def placeAskLimitOffer(self, market_id, amount, price):
        # SELLING == OT_TRUE, BUYING == OT_FALSE
        self.exchange_obj.offer_queue.put( (market_id, int(amount), int(price), 1) )

    def placeBidLimitOffer(self, market_id, amount, price):
        # SELLING == OT_TRUE, BUYING == OT_FALSE
        self.exchange_obj.offer_queue.put( (market_id, int(amount), int(price), 0) )

    def cancel_ask_order(self, market_id, order_id):
        pass

    def cancel_bid_order(self, market_id, order_id):
        pass

    def getCommission(self, amount, market_id):
        return 0


class CurrentNymMenu(QtGui.QMenu):

    template = QtCore.QCoreApplication.translate('OTExchange', "Current nym: %1",
                                                 "%1 will be replaced with the "
                                                 "currently selected nym label.")

    def changeTitle(self, label):
        self.setTitle(self.template.arg(label))


class ChangeOTThingAction(QtGui.QAction):

    currentIDChanged = QtCore.pyqtSignal(str)
    currentLabelChanged = QtCore.pyqtSignal(str)

    def __init__(self, ot_id, label, parent):
        super(ChangeOTThingAction, self).__init__(label, parent,
                                                  checkable=True)
        self.id = ot_id
        self.label = label
        self.triggered.connect(self.thingChanged)

    def thingChanged(self, toggled):
        self.currentIDChanged.emit(self.id)
        self.currentLabelChanged.emit(self.label)


class ChangeAccountAction(QtGui.QAction):

    currentLabelChanged = QtCore.pyqtSignal(str)

    def __init__(self, label, account_id, market_id,
                 change_account_method, parent=None):
        super(ChangeAccountAction, self).__init__(label, parent,
                                                  checkable=True)
        self.label = label
        self.account_id = account_id
        self.market_id = market_id
        self.changeExchangeAccount = change_account_method
        self.triggered.connect(self.accountChanged)

    def accountChanged(self, toggled):
        assert toggled
        self.changeExchangeAccount(self.market_id, self.account_id)
        self.currentLabelChanged.emit(self.label)


class NymAccountMenu(QtGui.QMenu):
    template = QtCore.QCoreApplication.translate('OTExchange',
                                                 "Current account: %1",
                                                 "%1 will be replaced with the "
                                                 "currently selected account "
                                                 "label.")

    def __init__(self, title, asset_id, market_id,
                 change_account_method,
                 current_nym_id, current_account_id, parent):
        super(NymAccountMenu, self).__init__(title, parent)
        self.asset_id = asset_id
        self.market_id = market_id
        self.change_account_method = change_account_method
        if current_nym_id: self.setNymId(current_nym_id)
        if current_account_id:
            for action in self.actions():
                if action.account.account_id == current_account_id:
                    action.trigger()

    def changeTitle(self, label):
        self.setTitle(self.template.arg(label))

    def setNymId(self, nym_id):
        self.clear()
        action_group = QtGui.QActionGroup(self)
        actions = list()
        for i in range(otapi.OT_API_GetAccountCount()):
            account_id = otapi.OT_API_GetAccountWallet_ID(i)
            if otapi.OT_API_GetAccountWallet_NymID(account_id) != nym_id:
                continue
            if (otapi.OT_API_GetAccountWallet_AssetTypeID(account_id)
                != self.asset_id):
                continue

            if otapi.OT_API_GetAccountWallet_Type(account_id) == 'issuer':
                continue

            account_label =  otapi.OT_API_GetAccountWallet_Name(account_id)
            action = ChangeAccountAction(account_label,
                                         account_id, self.market_id,
                                         self.change_account_method, self)
            action.setActionGroup(action_group)
            action.currentLabelChanged.connect(self.changeTitle)
            self.addAction(action)
            actions.append(action)

        if len(actions) == 1:
            actions[0].trigger()


def parse_servers():
    assets_mapping_model = tulpenmanie.model.ot.assets.OTAssetsSettingsModel()

    for i in range(otapi.OT_API_GetServerCount()):
        server_id = otapi.OT_API_GetServer_ID(i)
        if otapi.Exists('markets', server_id, 'market_data.bin'):
            storable = otapi.QueryObject(otapi.STORED_OBJ_MARKET_LIST,
                                         'markets', server_id,
                                         'market_data.bin')
        else:
            storable = otapi.CreateObject(otapi.STORED_OBJ_MARKET_LIST)

        market_list = otapi.MarketList.ot_dynamic_cast(storable)
        if not market_list.GetMarketDataCount():
            continue

        # we'll just make an item here and then stick it the bigger model
        # wherever a supported market may be
        exchange_proxy = None

        for j in range(market_list.GetMarketDataCount()):
            market_data = market_list.GetMarketData(j)

            search = assets_mapping_model.findItems(market_data.asset_type_id)
            if not search: continue
            row = search[0].row()
            local_base_id = assets_mapping_model.item(
                row, assets_mapping_model.LOCAL_ID).text()

            search = assets_mapping_model.findItems(market_data.currency_type_id)
            if not search: continue
            row = search[0].row()
            local_counter_id = assets_mapping_model.item(
                row, assets_mapping_model.LOCAL_ID).text()

            local_pair = local_base_id + '_' + local_counter_id
            local_pair = str(local_pair)

            if exchange_proxy is None:
                exchange_proxy = OTExchangeProxy(server_id, market_list)


            if local_pair in exchange_proxy.local_market_map:
                local_map = exchange_proxy.local_market_map[local_pair]
            else:
                local_map = list()
                exchange_proxy.local_market_map[local_pair] = local_map

            if market_data.market_id not in local_map:
                local_map.append(market_data.market_id)

            exchange_proxy.remote_market_map[market_data.market_id] = local_pair
            tulpenmanie.markets.container.addExchange(exchange_proxy,
                                                      local_pair)
        if exchange_proxy:
            tulpenmanie.exchanges.container.addExchange(exchange_proxy)

parse_servers()
