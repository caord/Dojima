# Dojima, a markets client.
# Copyright (C) 2012-2013 Emery Hemingway
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

import heapq
import logging

from PyQt4 import QtCore, QtGui

import dojima.data.account
import dojima.data.balance
#import dojima.data.orders


class ExchangeProxy:

    def __init__(self):
        self.exchange_object = None

    def getLocaltoRemote(self, key):
        return self.local_market_map[key]

    def getPrettyInterMarketName(self, remoteMarketID):
        raise NotImplementedError

    def getRemoteMapping(self, key):
        return self.remote_market_map[key]

    def getRemoteMarketIDs(self, localMarket_id):
        return self.local_market_map[localMarket_id]

    def getRemoteToLocal(self, marketID):
        return self.remote_market_map[marketID]

    def refreshMarkets(self):
        raise NotImplementedError

    def nextPage(self, wizard):
        raise NotImplementedError

    
class ExchangeProxySingleMarket(ExchangeProxy):

    def getLocaltoRemote(self, key):
        return self.local_market_map
    
    def getRemoteMapping(self, key):
        return self.remote_market_map

    def getRemoteMarketIDs(self, localMarket_id=None):
        return (self.local_market_map,)

    def getRemoteToLocal(self, marketID=None):
        return self.local_market

    def getPrettyMarketName(self, market_id=None):
        return market_id

    def refreshMarkets(self):
        local_base_id = dojima.model.commodities.remote_model.getRemoteToLocalMap(self.base_id)
        local_counter_id = dojima.model.commodities.remote_model.getRemoteToLocalMap(self.counter_id)

        if ((local_base_id is None) or
            (local_counter_id is None)): return

        local_market_id = local_base_id + '_' + local_counter_id
        self.local_market = local_market_id
        dojima.markets.container.addExchange(self, local_market_id, local_base_id, local_counter_id)

    
class Exchange:

    def echoTicker(self, remoteMarketID):
        pass

    def getAccountValidityProxy(self, marketID):
        if marketID not in self.account_validity_proxies:
            validity_proxy = dojima.data.account.AccountValidityProxy(self)
            self.account_validity_proxies[marketID] = validity_proxy
            return validity_proxy
        return self.account_validity_proxies[marketID]

    def getBalanceProxy(self, symbol):
        if symbol not in self.funds_proxies:
            proxy = dojima.data.funds.BalanceProxyDecimal(self)
            self.funds_proxies[symbol] = proxy
            return proxy

        return self.funds_proxies[symbol]

    def getBalanceBaseProxy(self, market_id):
        raise NotImplementedError

    def getBalanceCounterProxy(self, market_id):
        raise NotImplementedError

    def getOffersModelAsks(self, market_id):
        if market_id in self.offers_proxies_asks:
            return self.offers_proxies_asks[market_id]

        base_model = self.getOffersModel(market_id)
        asks_model = dojima.data.offers.FilterAsksModel(base_model)
        self.offers_proxies_asks[market_id] = asks_model
        return asks_model

    def getOffersModelBids(self, market_id):
        if market_id in self.offers_proxies_bids:
            return self.offers_proxies_bids[market_id]

        base_model = self.getOffersModel(market_id)
        bids_model = dojima.data.offers.FilterBidsModel(base_model)
        self.offers_proxies_bids[market_id] = bids_model
        return bids_model
        
    def getScale(self, remoteMarketID):
        return 1

    def getTickerProxy(self, market_id):
        if market_id not in self.ticker_proxies:
            ticker_proxy = dojima.data.market.TickerProxyDecimal(self)
            self.ticker_proxies[market_id] = ticker_proxy
            return ticker_proxy
        return self.ticker_proxies[market_id]

    def getTickerRefreshRate(self, market=None):
        return self._ticker_refresh_rate

    def getOffersModel(self, market_id):
        if market_id in self.offers_proxies:
            return self.offers_proxies[market_id]

        base_symbol, counter_symbol = self.getMarketSymbols(market_id)
        if base_symbol in self.base_offers_proxies:
            base_proxy = self.base_offers_proxies[base_symbol]
        else:
            base_proxy = QtGui.QSortFilterProxyModel()
            base_proxy.setSourceModel(self.offers_model)
            base_proxy.setFilterKeyColumn(dojima.data.offers.BASE)
            base_proxy.setFilterFixedString(base_symbol)
            base_proxy.setDynamicSortFilter(True)
            self.base_offers_proxies[base_symbol] = base_proxy

        proxy = QtGui.QSortFilterProxyModel()
        proxy.setSourceModel(base_proxy)
        proxy.setFilterKeyColumn(dojima.data.offers.COUNTER)
        proxy.setFilterFixedString(counter_symbol)
        proxy.setDynamicSortFilter(True)
        self.offers_proxies[market_id] = proxy
        return proxy

    def pop_request(self):
        request = heapq.heappop(self.requests)[1]
        request.send()

    def populateMenuBar(self, menu, remoteMarketID):
        pass
        
    def refresh(self, market_id):
        self.refreshOffers(market_id)
        self.refreshBalance(market_id)
        
    def setTickerRefreshRate(self, rate):
        self._ticker_refresh_rate = rate
        if self.ticker_timer.isActive():
            self.ticker_timer.setInterval(self._ticker_refresh_rate * 1000)

    def setTickerStreamState(self, state, market_id):
        if state is True:
            if not market_id in self.ticker_clients:
                self.ticker_clients[market_id] = 1
            else:
                self.ticker_clients[market_id] += 1
                
            if self.ticker_timer.isActive(): return
                
            self.ticker_timer.start(self._ticker_refresh_rate * 1000)
        else:
            if market_id not in self.ticker_clients: return
        
            market_clients = self.ticker_clients[market_id]
            if market_clients > 1:
                self.ticker_clients[market_id] -= 1
                return
            
            if market_clients == 1:
                self.ticker_clients.pop(market_id)

            if sum(self.ticker_clients.values()) == 0:
                self.ticker_timer.stop()
        

class ExchangeSingleMarket(Exchange):

    def getBalanceBaseProxy(self, market=None):
        return self.base_balance_proxy

    def getBalanceCounterProxy(self, market=None):
        return self.counter_balance_proxy

    def getDepthProxy(self, market=None):
        return self.depth_proxy

    def getOffersModelAsks(self, market=None):
        return self.offer_proxy_asks

    def getOffersModelBids(self, market=None):
        return self.offer_proxy_bids
    
    def getTickerProxy(self, market=None):
        return self.ticker_proxy

    def getTickerRefreshRate(self):
        return self._ticker_refresh_rate

    def setTickerStreamState(self, state, market=None):
        if state is True:
            self.ticker_clients += 1
            if self.ticker_timer.isActive():
                self.ticker_timer.setInterval(self._ticker_refresh_rate * 1000)
                return
            self.ticker_timer.start(self._ticker_refresh_rate * 1000)
        else:
            if self.ticker_clients >1:
                self.ticker_clients -= 1
                return
            if self.ticker_clients == 0:
                return
            self.ticker_clients = 0
            self.ticker_timer.stop()

            
class EditCredentialsAction(QtGui.QAction):

    accountSettingsChanged = QtCore.pyqtSignal()

    def __init__(self, parent):
        super(EditCredentialsAction, self).__init__(
            QtCore.QCoreApplication.translate("ExchangeDockWidget", "Edit Credentials",
                                              "The title of an option on the 'Account' menu"),
            parent)
        self.triggered.connect(self.show_dialog)
