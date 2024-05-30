from datetime import *
import random 
from decimal import Decimal

from c3.c3exchange import C3Exchange
from c3.signing.signers import EVMMessageSigner
from c3.utils.constants import MainnetConstants



#API Key
private_key = "private_key"
c3PrimaryAccountId = "C3_ACCOUNTID"
c3PrimaryAccountAddress = "AccountAddress"

evmAlgorand = EVMMessageSigner(private_key)

default_client = C3Exchange(base_url=MainnetConstants.API_URL)
c3Account = default_client.login(signer=evmAlgorand, 
    primaryAccountId=c3PrimaryAccountId,
    primaryAccountAddress=c3PrimaryAccountAddress
)

def getAllAssetBalances(asset):
    balances = c3Account.getBalance()

    info = balances['instrumentsInfo']
    for i in range(len(info)):
        if info[i]['instrumentId'] == asset:
            return info[i]
    return {'instrumentId': asset, 'availableCash': '0', 'lockedCash': '0', 'maxBorrow': '0', 'maxLend': '0', 'maxWithdraw': '0', 'maxWithdrawWithBorrow': '0', 'cash': '0', 'poolPosition': '0', 'shortfall': '0'}

def getAssetAvailableBalance(asset):
    return getAllAssetBalances(asset)['availableCash']

def getUSDTAvailableBalance():
    return getAssetAvailableBalance('USDT')

def getAllUSDTBalances():
    return getAllAssetBalances("USDT")

def getBTCAvailableBalance():
    return getAssetAvailableBalance('BTC')

def getAllBTCBalances():
    return getAllAssetBalances("BTC")

def getPythAvailableBalance():
    return getAssetAvailableBalance('PYTH')

def getAllPythBalances():
    return getAllAssetBalances("PYTH")

def getAlgoAvailableBalance():
    return getAssetAvailableBalance('ALGO')

def getAllAlgoBalances():
    return getAllAssetBalances("ALGO")

def placeSellOrders(pair, priceFrom, priceTo, totalAmount, minAmountPerOrder, maxAmountPerOrder):
    if priceTo < priceFrom:
        raise Exception('priceTo must be greater than priceFrom and both must be greater than 0', '')
    if priceFrom == 0:
        raise Exception('priceTo and priceFrom must be greater than 0', '')
    if minAmountPerOrder <= 0.5:
        raise Exception('minAmountPerOrder must be greater than 0.5', '')
    if maxAmountPerOrder <= minAmountPerOrder:
        raise Exception('maxAmountPerOrder must be greater than minAmountPerOrder', '')
    if totalAmount <= 0:
        raise Exception('totalAmount must be greater than 0', '')

    orderAvgAmount = (maxAmountPerOrder + minAmountPerOrder) / 2
    orderCount = int(totalAmount / orderAvgAmount) + 1

    # adjust value after calculating orderCount
    orderAvgAmount = totalAmount / orderCount

    # standarize both limits
    if orderAvgAmount - minAmountPerOrder > maxAmountPerOrder - orderAvgAmount:
        orderAmountSpread = (maxAmountPerOrder - orderAvgAmount)
    else:
        orderAmountSpread = (orderAvgAmount - minAmountPerOrder)

    theoricOrderAvgAmount = orderAvgAmount = totalAmount / orderCount

    orders = []
    currentPrice = Decimal(priceFrom)
    priceIncrement = Decimal((priceTo - priceFrom) / (orderCount - 1))

    totalOrderAmount = 0

    base = pair[0:pair.index('-')]
    theoricalBalance = float(getAssetAvailableBalance(base))

    while orderCount > 0:
        orderAmount = orderAvgAmount + random.triangular(-orderAmountSpread, orderAmountSpread, 0)
        nextPrice = currentPrice + priceIncrement

        if orderAmount > totalAmount:
            if orderCount == 1:
                orderAmount = totalAmount
            else:
                orderAmount = totalAmount / orderCount
        
        if orderCount == 1:
            currentPrice = priceTo
            orderAmount = totalAmount

        if currentPrice > priceTo:
            currentPrice = priceTo

        if orderAmount >= theoricalBalance * 0.8:
            theoricalBalance = float(getAssetAvailableBalance(base)) - 0.01
            orderAmount = totalAmount = theoricalBalance
        
        if totalAmount / orderCount > theoricOrderAvgAmount * 1.05:
            orderAvgAmount += orderAvgAmount * 0.1
        elif totalAmount / orderCount < theoricOrderAvgAmount * 0.95:
            orderAvgAmount -= orderAvgAmount * 0.1
        else:
            orderAvgAmount = theoricOrderAvgAmount
        
        # round it
        orderAmount = float('{0:,.0f}'.format(orderAmount).replace(',', ''))
        if orderAmount == 0:
            break

        if 'BTC' in pair:
            orderPrice = '%0.8f' % currentPrice
        else:
            orderPrice = '%0.4f' % currentPrice

        print("New order: " + pair + " Amount:  " + str(orderAmount) + " Price: " + str(orderPrice) + " Current Balance: " + str(theoricalBalance) + " Order Avg: " + str(orderAvgAmount)
            + " Order Count: " + str(orderCount) + " Total Amount / orderCount: " + str(totalAmount/orderCount))

        orderParams = {
            "marketId": pair,
            "type": "limit",
            "side": "sell",
            "amount": str(orderAmount),
            "price": orderPrice,
        }

        print('order: ' + str(orderParams))
        orderResponse = c3Account.submitOrder(orderParams)

        orderCount -= 1
        totalOrderAmount += orderAmount
        totalAmount -= orderAmount
        theoricalBalance -= orderAmount
        currentPrice = nextPrice
    
    print("Total orders: " + str(len(orders)) + " Total Amount: " + str(totalOrderAmount) )
    return orders

def placeBuyOrders(pair, priceFrom, priceTo, totalAmount, minAmountPerOrder, maxAmountPerOrder):
    if priceTo < priceFrom:
        raise Exception('priceTo must be greater than priceFrom and both must be greater than 0', '')
    if priceFrom == 0:
        raise Exception('priceTo and priceFrom must be greater than 0', '')
    if minAmountPerOrder <= 0.5:
        raise Exception('minAmountPerOrder must be greater than 0.5', '')
    if maxAmountPerOrder <= minAmountPerOrder:
        raise Exception('maxAmountPerOrder must be greater than minAmountPerOrder', '')
    if totalAmount <= 0:
        raise Exception('totalAmount must be greater than 0', '')

    orderAvgAmount = (maxAmountPerOrder + minAmountPerOrder) / 2
    orderCount = int(totalAmount / orderAvgAmount) + 1

    # adjust value after calculating orderCount
    orderAvgAmount = totalAmount / orderCount

    # standarize both limits
    if orderAvgAmount - minAmountPerOrder > maxAmountPerOrder - orderAvgAmount:
        orderAmountSpread = (maxAmountPerOrder - orderAvgAmount)
    else:
        orderAmountSpread = (orderAvgAmount - minAmountPerOrder)

    theoricOrderAvgAmount = orderAvgAmount = totalAmount / orderCount

    orders = []
    currentPrice = Decimal(priceFrom)
    priceIncrement = Decimal((priceTo - priceFrom) / (orderCount - 1))

    totalOrderAmount = 0

    quote = pair[pair.index('-')+1:len(pair)]
    theoricalBalance = float(getAssetAvailableBalance(quote))

    while orderCount > 0:
        orderAmount = orderAvgAmount + random.triangular(-orderAmountSpread, orderAmountSpread, 0)
        nextPrice = currentPrice + priceIncrement

        if orderAmount > totalAmount:
            if orderCount == 1:
                orderAmount = totalAmount
            else:
                orderAmount = totalAmount / orderCount
        
        if orderCount == 1:
            currentPrice = priceTo
            orderAmount = totalAmount

        if currentPrice > priceTo:
            currentPrice = priceTo

        if orderAmount >= theoricalBalance * 0.8:
            theoricalBalance = float(getAssetAvailableBalance(quote)) - 0.01
            orderAmount = totalAmount = theoricalBalance
        
        if totalAmount / orderCount > theoricOrderAvgAmount * 1.05:
            orderAvgAmount += orderAvgAmount * 0.1
        elif totalAmount / orderCount < theoricOrderAvgAmount * 0.95:
            orderAvgAmount -= orderAvgAmount * 0.1
        else:
            orderAvgAmount = theoricOrderAvgAmount
        
        # round it
        orderAmount = float('{0:,.0f}'.format(orderAmount).replace(',', ''))
        if orderAmount == 0:
            break

        if 'BTC' in pair:
            orderPrice = '%0.8f' % currentPrice
        else:
            orderPrice = '%0.4f' % currentPrice

        print(orderAmount)
        orderAmount = float('{0:.2f}'.format(orderAmount).replace(',', ''))
        print(orderAmount)
        if orderAmount == 0:
            break

        print("New order: " + pair + " Amount:  " + str(orderAmount) + " Price: " + str(orderPrice) + " Current Balance: " + str(theoricalBalance) + " Order Avg: " + str(orderAvgAmount)
            + " Order Count: " + str(orderCount) + " Total Amount / orderCount: " + str(totalAmount/orderCount))

        orderParams = {
            "marketId": pair,
            "type": "limit",
            "side": "buy",
            "amount": str(orderAmount),
            "price": orderPrice,
        }

        print('order: ' + str(orderParams))
        orderResponse = c3Account.submitOrder(orderParams)

        orderCount -= 1
        totalOrderAmount += orderAmount
        totalAmount -= orderAmount
        theoricalBalance -= orderAmount
        currentPrice = nextPrice
    
    print("Total orders: " + str(len(orders)) + " Total Amount: " + str(totalOrderAmount) )
    return orders

def getBTCActiveBuyOrders(self, limit=100, priceFrom=None, priceTo=None):
    return self.getActiveBuyOrders(self.algoBTCPairString(), priceFrom, priceTo)

def getUSDTActiveBuyOrders(self, limit=100, priceFrom=None, priceTo=None):
    return self.getActiveBuyOrders(self.algoUSDTPairString(), priceFrom, priceTo)



#import c3_trade
#c3_trade.placeSellOrders('PYTH-USDC', 0.5, 0.6, 1000, 100, 300)
#c3_trade.placeBuyOrders('PYTH-USDC', 0.2, 0.3, 1000, 100, 300)
