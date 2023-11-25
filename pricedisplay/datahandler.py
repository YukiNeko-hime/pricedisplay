# -*- coding: UTF-8 -*-

import copy
import datetime
import json
import requests

from requests.exceptions import *
from .exceptions import MissingOptionError
from .exceptions import NoDataError, DataParsingError, DataRequestError

__version__ = '0.4.3'

class PriceData:
	"""Retrieves, parses and updates the price data from the specified source."""
	
	_prices = None
	_day = None
	
	def __init__( self, options ):
		try:
			self._dateField = options['dateField']
			self._priceWithTaxField = options['priceWithTaxField']
			self._priceNoTaxField = options['priceNoTaxField']
			self._source = options['source']
		except KeyError as err:
			raise MissingOptionError( err.args )
		
		self._prices = [ 24*[None], 24*[None], 24*[None] ]
		
		today = datetime.datetime.today()
		self._day = today.day
	
	def _ConvertToPriceList( self, data ):
		"""Convert a list of ( date, price ) tuples to a list of prices. If data is missing, fill in None."""
		if not len(data):
			return 24*[None]
		
		# make sure the data is sorted by day and hour
		data.sort()
		
		# determine DST offset from the acquired data if any
		firstHourOffset = data[0][0].utcoffset()
		lastHourOffset = data[-1][0].utcoffset()
		delta = lastHourOffset - firstHourOffset
		
		dstOffset = delta.days*24 + delta.seconds/3600				# offset in hours
		hoursInDay = 24 - dstOffset
		hoursInDay = int( hoursInDay )
		
		# pad the price data with None
		prices = hoursInDay*[None]
		
		# fill in the price data given as the argument
		i = 0
		while i < len( data ):
			date, price = data[i]
			
			# find out how many hours it has been after midnight for the given hour
			offset = firstHourOffset - date.utcoffset()
			hourOffset = offset.days*24 + offset.seconds/3600
			
			hour = date.hour + hourOffset
			hour = int( hour )
			
			# fill in the price data
			prices[hour] = price
			i += 1
		
		return prices
		
	def _FilterDataByDay( self, data ):
		"""Filters data based on day to ( date, price ) lists for yesterday, today, and tomorrow."""
		
		today = datetime.datetime.today()
		tomorrow = today + datetime.timedelta( days=1 )
		yesterday = today - datetime.timedelta( days=1 )
		
		# split the data to days
		dataToday = []
		dataTomorrow = []
		dataYesterday = []
		
		for line in data:
			date, price = self._ParseObject( line )
			
			if date.day == today.day:
				dataToday.append( (date, price) )
			
			if date.day == tomorrow.day:
				dataTomorrow.append( (date, price) )
			
			if date.day == yesterday.day:
				dataYesterday.append( (date, price) )
		
		return dataYesterday, dataToday, dataTomorrow
	
	def _ParseData( self, data ):
		"""Parses json data to lists of prices on yesterday, today, and tomorrow."""
		
		dataYesterday, dataToday, dataTomorrow = self._FilterDataByDay( data )
		
		# Convert the data to a price list
		pricesToday = self._ConvertToPriceList( dataToday )
		pricesTomorrow = self._ConvertToPriceList( dataTomorrow )
		pricesYesterday = self._ConvertToPriceList( dataYesterday )
		
		self._prices = [ pricesYesterday, pricesToday, pricesTomorrow ]
	
	def _ParseObject( self, obj ):
		"""Parses a json object to a datetime object and a two decimal price in cents."""
		
		date = self._ParseDate( obj, self._dateField )
		priceWithTax = self._ParsePrice( obj, self._priceWithTaxField )
		priceNoTax = self._ParsePrice( obj, self._priceNoTaxField )
		
		# if neither price was found, raise parsing error
		if priceWithTax == None and priceNoTax == None:
			raise DataParsingError( 'No ' + self._priceWithTaxField + ' or ' + self._priceNoTaxField + ' in data' )
		
		# default to the price with tax if present in the data
		if priceWithTax is not None:
			price = priceWithTax
		else:
			price = priceNoTax
		
		# negative price has no tax included
		if priceNoTax != None and priceNoTax < 0:
			price = priceNoTax
		
		return date, price
	
	def _ParseDate( self, obj, field ):
		"""Extracts the date from the json object."""
		
		try:
			dateTime = obj[ field ]
			date = datetime.datetime.fromisoformat( dateTime )
			
		except KeyError:
			raise DataParsingError( 'No ' + field + ' in data' )
			
		except ValueError:
			raise DataParsingError( 'Timestamp is not in iso format (' + field + ')' )
		
		return date
	
	def _ParsePrice( self, obj, field ):
		"""Extracts the price from the json object and rounds it to two decimals. If there is no specified field, return None instead of a parsing error."""
		
		try:
			price = obj[ field ]
			price = round( 100*price, 2 )
			
		except KeyError:
			price = None
			
		except ValueError:
			raise DataParsingError( 'Price is not a number (' + field + ')' )
		
		return price
	
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
		"""Returns the prices for yesterday, today, and tomorrow. Makes a deepcopy of the internal data structure to prevent accidental overwriting of the data."""
		
		return copy.deepcopy( self._prices )
	
	def MidnightUpdate( self ):
		"""Updates the data at midnight. Moves todays data to yesterday and tomorrows data to today."""
		
		trash, yesterday, today = self._prices
		self._prices = [ yesterday, today, 24*[None] ]
	
	def Update(self):
		"""Retrieves new data from the source."""
		
		data = self._RetrieveData()
		self._ParseData( data )
