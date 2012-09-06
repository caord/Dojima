# Tuplenmanie, a commodities market client.
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

import decimal
import heapq
import json
import logging
from PyQt4 import QtCore, QtGui, QtNetwork

import tulpenmanie.providers
from tulpenmanie.model.order import OrdersModel


logger = logging.getLogger(__name__)

EXCHANGE_NAME = "CampBX"
HOSTNAME = "campbx.com"
_BASE_URL = "https://" + HOSTNAME + "/api/"


def _reply_has_errors(reply):
    if reply.error():
        logger.error(reply.errorString())

def _object_pairs_hook(pairs):
    dct = dict()
    for key, value in pairs:
        dct[key] = decimal.Decimal(value)
    return dct


class CampbxError(Exception):

    def __init__(self, value):
        self.value = value
    def __str__(self):
        error_msg= repr(self.value)
        logger.error(error_msg)
        return error_msg


class CampbxRequest(object):

    def __init__(self, url, handler, parent, data=None):
        self.url = url
        self.handler = handler
        self.parent = parent
        if data:
            self.data = data
        else:
            self.data = dict()
        self.reply = None

        self.request = QtNetwork.QNetworkRequest(self.url)
        self.request.setHeader(QtNetwork.QNetworkRequest.ContentTypeHeader,
                               "application/x-www-form-urlencoded")
        query = parent.base_query
        if data:
            for key, value in data['query'].items():
                query.addQueryItem(key, str(value))
        self.query = query.encodedQuery()

    def post(self):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("requesting %s", self.url.toString())
        self.reply = self.parent.network_manager.post(self.request,
                                                      self.query)
        self.reply.finished.connect(self._process_reply)
        self.reply.error.connect(self._process_reply)

    def _process_reply(self):
        if self.reply.error():
            logger.error(self.reply.errorString())
        else:
            if logger.isEnabledFor(logging.INFO):
                logger.debug("received reply to %s", self.reply.url().toString())
            data = json.loads(str(self.reply.readAll()))#,
                #object_pairs_hook=_object_pairs_hook)
            if 'Error' in data:
                msg = str(reply.url().toString()) + " : " + data['Error']
                raise CampbxError(msg)
            elif 'Info' in data:
                msg = str(reply.url().toString()) + " : " + data['Error']
                logger.warning(msg)
            else:
                if self.data:
                    self.data.update(data)
                    self.handler(self.data)
                else:
                    self.handler(data)
        self.reply.deleteLater()
        self.parent._replies.remove(self)


class _Campbx(QtCore.QObject):
    provider_name = EXCHANGE_NAME

    def pop_request(self):
        request = heapq.heappop(self._requests)
        request.post()
        self._replies.add(request)


class CampbxExchangeMarket(_Campbx):

    register_url = "https://CampBX.com/register.php?r=P3hAnksjDmY"
    register_url_info = """register at this link and receive a lifetime 10% """ \
                        """discount on exchange commissions"""

    _xticker_url = QtCore.QUrl(_BASE_URL + "xticker.php")

    ask = QtCore.pyqtSignal(decimal.Decimal)
    last = QtCore.pyqtSignal(decimal.Decimal)
    bid = QtCore.pyqtSignal(decimal.Decimal)

    def __init__(self, remote_market, network_manager=None, parent=None):
        if network_manager is None:
            network_manager = self.manager.network_manager
        super(CampbxExchangeMarket, self).__init__(parent)
        # These must be the same length
        remote_stats = ('Best Ask', 'Last Trade', 'Best Bid')
        self.stats = ('ask', 'last', 'bid')
        self.is_counter = (True, True, True)
        self._signals = dict()
        self.signals = dict()
        for i in range(len(remote_stats)):
            signal = getattr(self, self.stats[i])
            self._signals[remote_stats[i]] = signal
            self.signals[self.stats[i]] = signal

        self.base_query = QtCore.QUrl()
        self.network_manager = network_manager
        self._request_queue = self.network_manager.get_host_request_queue(
            HOSTNAME, 500)
        self._requests = list()
        self._replies = set()

    def refresh(self):
        request = CampbxRequest(self._xticker_url, self._xticker_handler, self)
        self._requests.append(request)
        self._request_queue.enqueue(self)

    def _xticker_handler(self, data):
        for key, value in data.items():
            signal =  self._signals[key]
            signal.emit(decimal.Decimal(value))


class CampbxAccount(_Campbx, tulpenmanie.providers.ExchangeAccount):
    _myfunds_url = QtCore.QUrl(_BASE_URL + "myfunds.php")
    _myorders_url = QtCore.QUrl(_BASE_URL + "myorders.php")
    _tradeenter_url = QtCore.QUrl(_BASE_URL + "tradeenter.php")
    _tradecancel_url = QtCore.QUrl(_BASE_URL + "tradecancel.php")

    BTC_balance_signal = QtCore.pyqtSignal(decimal.Decimal)
    USD_balance_signal = QtCore.pyqtSignal(decimal.Decimal)

    BTC_USD_ready_signal = QtCore.pyqtSignal(bool)

    def __init__(self, credentials, network_manager=None, parent=None):
        if network_manager is None:
            network_manager = self.manager.network_manager
        super(CampbxAccount, self).__init__(parent)
        self.base_query = QtCore.QUrl()
        self.base_query.addQueryItem('user', credentials[0])
        self.base_query.addQueryItem('pass', credentials[2])
        self.network_manager = network_manager
        self._request_queue = self.network_manager.get_host_request_queue(
            HOSTNAME, 500)
        self._requests = list()
        self._replies = set()

        self.ask_orders_model = OrdersModel()
        self.bid_orders_model = OrdersModel()

    def check_order_status(self, remote_pair):
        self.BTC_USD_ready_signal.emit(True)

    def get_ask_orders_model(self, remote_pair):
        return self.ask_orders_model

    def get_bid_orders_model(self, remote_pair):
        return self.bid_orders_model

    def refresh(self):
        request = CampbxRequest(self._myfunds_url, self._myfunds_handler, self)
        self._requests.append(request)
        self._request_queue.enqueue(self)
        self.refresh_orders()

    def _myfunds_handler(self, data):
        #TODO maybe not emit 'Total' but rather available
        self.BTC_balance_signal.emit(decimal.Decimal(data['Total BTC']))
        self.USD_balance_signal.emit(decimal.Decimal(data['Total USD']))

    def refresh_orders(self):
        request = CampbxRequest(self._myorders_url, self._myorders_handler, self)
        self._requests.append(request)
        self._request_queue.enqueue(self)

    def _myorders_handler(self, data):
        for model, array, in ((self.ask_orders_model, 'Sell'),
                              (self.bid_orders_model, 'Buy') ):
            model.clear_orders()
            for order in data[array]:
                if 'Info' in order:
                    break

                order_id = order['Order ID']
                price = order['Price']
                amount = order['Quantity']

                model.append_order(order_id, price, amount)
            model.sort(1, QtCore.Qt.DescendingOrder)

    def place_ask_order(self, pair, amount, price):
        self._place_order(amount, price, "QuickSell")

    def place_bid_order(self, pair, amount, price):
        self._place_order(amount, price, "QuickBuy")

    def _place_order(self, amount, price, trade_mode):
        query = {'TradeMode' : trade_mode,
                 'Quantity' : amount}
        if price:
            query['Price'] = price
        else:
            query['Price'] = 'Market'
        data = {'query':query}
        request = CampbxRequest(self._tradeenter_url, self._tradeenter_handler,
                                self, data)
        self._requests.append(request)
        self._request_queue.enqueue(self)

    def _tradeenter_handler(self, data):
        if data['Success'] != '0':
            # TODO could be a low priority request
            self.refresh_orders()

    def cancel_ask_order(self, pair, order_id):
        self._cancel_order(order_id, 'Sell')

    def cancel_bid_order(self, pair, order_id):
        self._cancel_order(order_id, 'Buy')

    def _cancel_order(self, order_id, order_type):
        data = {'query':{ 'Type' : order_type,
                          'OrderID' : order_id }}
        request = CampbxRequest(self._tradecancel_url,
                                self._tradecancel_handler,
                                self, data)
        self._requests.append(request)
        self._request_queue.enqueue(self)

    def _tradecancel_handler(self, data):
        words = data['Success'].split()
        order_id = words[2]
        items = self.ask_orders_model.findItems(order_id,
                                                QtCore.Qt.MatchExactly, 0)
        if len(items):
            row = items[0].row()
            self.ask_orders_model.removeRow(row)
        if not len(items):
            items = self.bid_orders_model.findItems(order_id,
                                              QtCore.Qt.MatchExactly, 0)
            row = items[0].row()
            self.bid_orders_model.removeRow(row)
        logger.debug("Trimmed order %s from a model", order_id)


class CampbxProviderItem(tulpenmanie.providers.ProviderItem):

    provider_name = EXCHANGE_NAME

    COLUMNS = 3
    MARKETS, ACCOUNTS, REFRESH_RATE = range(COLUMNS)
    mappings = (('refresh rate', REFRESH_RATE),)
    markets = ('BTC_USD',)

    ACCOUNT_COLUMNS = 3
    ACCOUNT_ID, ACCOUNT_ENABLE,  ACCOUNT_PASSWORD = range(ACCOUNT_COLUMNS)
    account_mappings = (('username', ACCOUNT_ID),
                        ('enable', ACCOUNT_ENABLE),
                        ('password', ACCOUNT_PASSWORD))
    numeric_settings = (REFRESH_RATE,)
    boolean_settings = ()
    required_account_settings = (ACCOUNT_PASSWORD,)
    hidden_account_settings = (ACCOUNT_PASSWORD,)


tulpenmanie.providers.register_exchange(CampbxExchangeMarket)
tulpenmanie.providers.register_account(CampbxAccount)
tulpenmanie.providers.register_exchange_model_item(CampbxProviderItem)
