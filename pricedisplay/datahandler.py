# -*- coding: UTF-8 -*-

import datetime
import json
import requests

from requests.exceptions import *

__version__ = '0.2.4'

class NoDataError(Exception):
	pass

class DataParsingError(Exception):
	pass

class DataRequestError(Exception):
	pass

class MissingOptionError( Exception ):
	def __init__( self, option ):
		self.option = option
		msg = 'Missing option: ' + option
		
		Exception.__init__( self, msg )

class PriceData:
	"""Retrieves, parses and updates the price data from the specified source."""
	
	_prices = None
	_day = None
	
	def __init__( self, options ):
		try:
			self._dateField = options['dateField']
			self._priceField = options['priceField']
			self._source = options['source']
		except KeyError as err:
			raise MissingOptionError( err.args )
		
		self._prices = ( 24*[None], 24*[None], 24*[None] )
		
		today = datetime.datetime.today()
		self._day = today.day
	
	def _FilterData( self, data ):
		"""Filters data based on day to price lists for yesterday, today, and tomorrow."""
		
		today = datetime.datetime.today()
		tomorrow = today + datetime.timedelta( days=1 )
		yesterday = today - datetime.timedelta( days=1 )
		
		priceToday = []
		priceTomorrow = []
		priceYesterday = []
		
		for line in data:
			day, price = self._ParseObject( line )
			
			if day == today.day:
				priceToday.append( price )
			
			if day == tomorrow.day:
				priceTomorrow.append( price )
			
			if day == yesterday.day:
				priceYesterday.append( price )
		
		# add placeholder values for days which have no data
		if not priceToday:
			priceToday = 24*[None]
		
		if not priceTomorrow:
			priceTomorrow = 24*[None]
		
		if not priceYesterday:
			priceYesterday = 24*[None]
		
		return priceYesterday, priceToday, priceTomorrow
	
	def _ParseData( self, data ):
		"""Parses json data to lists of prices on yesterday, today, and tomorrow."""
		
		priceYesterday, priceToday, priceTomorrow = self._FilterData( data )
		
		if len( priceYesterday ):
			self._prices = ( priceYesterday, priceToday, priceTomorrow )
		else:
			self._prices = ( self._prices[0], priceToday, priceTomorrow )
	
	def _ParseObject( self, obj ):
		"""Parses a json object to a datetime object and a two decimal price in cents."""
		
		try:
			dateTime = obj[ self._dateField ]
			date = datetime.datetime.fromisoformat( dateTime )
			day = date.day
			
		except KeyError:
			raise DataParsingError( 'No ' + self._dateField + ' in data' )
			
		except ValueError:
			raise DataParsingError( 'Timestamp is not in iso format' )
		
		try:
			price = obj[ self._priceField ]
			price = round( 100*price, 2 )
			
		except KeyError:
			raise DataParsingError( 'No ' + self._priceField + ' in data' )
			
		except ValueError:
			raise DataParsingError( 'Price is not a number' )
		
		return day, price
	
	def _RequestDataHTTP( self ):
		"""Requests data with a http get."""
		
		try:
			resp = requests.get( self._source )
			resp.raise_for_status()
			data = resp.json()
		
		# handle request errors
		except (ConnectionError, HTTPError, Timeout, TooManyRedirects, RequestException ) as err:
			raise DataRequestError( 'Error in retrieving the data: ' + self._source + '\n' + str(err) )
		
		# handle json decoding errors
		except ( json.decoder.JSONDecodeError ):
			raise DataParsingError( "Can't decode json" )
		
		return data
	
	def _LoadDataFile( self ):
		"""Reads data from a file."""
		
		try:
			with open( self._source, 'r' ) as file:
				data = json.load( file )
		
		#handle OS related errors
		except OSError:
			raise DataRequestError( 'No such file: ' + self._source )
		
		# handle json decoding errors
		except ( json.decoder.JSONDecodeError ):
			raise DataParsingError( "Can't decode json" )
		
		return data
	
	def _RetrieveData( self ):
		"""Retrieves data either by http request or from a local file."""
		
		if self._source.lower().startswith('http'):
			return self._RequestDataHTTP()
		else:
			return self._LoadDataFile()
	
	def GetPrices( self ):
		"""Returns the prices for yesterday, today, and tomorrow."""
		
		return self._prices
	
	def MidnightUpdate( self ):
		"""Updates the data at midnight. Moves todays data to yesterday and tomorrows data to today."""
		
		trash, yesterday, today = self._prices
		self._prices = ( yesterday, today, 24*[None] )
	
	def Update(self):
		"""Retrieves new data from the source."""
		
		data = self._RetrieveData()
		self._ParseData( data )
