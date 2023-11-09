# -*- coding: UTF-8 -*-

import argparse
import curses
import datetime
import sys
import time
import traceback

from .configparser import Config
from .datahandler import PriceData
from .graphics import Display

from .configparser import ConfigParsingError, CorruptedTemplateError, MissingTemplateError, TemplateParsingError
from .datahandler import DataParsingError, NoDataError, DataRequestError
from .graphics import WindowSizeError

__version__ = '0.3.0'

_debug = 0

_noErrors = 0
_unexpectedError = 1
_configError = 2
_displayError = 3
_dataError = 4


class MissingOptionError( Exception ):
	def __init__( self, option ):
		self.option = option
		msg = 'Missing option: ' + option
		
		Exception.__init__( self, msg )

class App:
	"""An application for displaying and updating price data."""
	
	_running = False
	
	def __init__( self, options ):
		dataOptions = {}
		displayOptions = {}
		
		# check that all options are present
		try:
			freq = options['data.updateFrequency']
			available = options['data.availableAt']
			
			dataOptions['dateField'] = options['data.dateField']
			dataOptions['priceField'] = options['data.priceField']
			dataOptions['source'] = options['data.source']
			
			displayOptions['carets'] = (
				options['caret.style.above'],
				options['caret.style.below']
			)
			
			displayOptions['limits'] = (
				options['price.low'],
				options['price.high']
			)
			
			displayOptions['pastHours'] = options['caret.past_hours']
			displayOptions['preferred'] = options['layout.preferred']
			displayOptions['reverse'] = options['layout.reverse']
			
			displayOptions['normalTimezone'] = options['data.normalTimezone']
		
		except KeyError as err:
			raise MissingOptionError( err.args[0] )
		
		self._updateFrequency = freq
		self._available = available
		self._dataAvailable = self._AvailableFromTime()
		
		stdscr = curses.initscr()
		self._display = Display( displayOptions, parent=stdscr )
		
		self._data = PriceData( dataOptions )
	
	def _EndCurses( self ):
		"""Reverse terminal settings."""
		
		curses.echo()
		curses.cbreak()
		curses.curs_set(1)
		curses.endwin()
	
	def _InitCurses( self ):
		"""Initialize the curses environment."""
		
		curses.noecho()
		curses.cbreak()
		curses.curs_set(0)
		curses.start_color()
		curses.use_default_colors()
		
		curses.init_pair( 1, curses.COLOR_GREEN, -1 )
		curses.init_pair( 2, curses.COLOR_YELLOW, -1 )
		curses.init_pair( 3, curses.COLOR_RED, -1 )
		curses.init_pair( 4, curses.COLOR_CYAN, -1 )
	
	def _InitializeDisplay( self ):
		"""Initialize the price display."""
		
		self._data.Update()
		prices = self._data.GetPrices()
		self._display.Update( prices )
		
		now = datetime.datetime.now()
		self._lastDisplayUpdate = now
		self._lastDataUpdate = now
	
	def _AvailableFromTime(self):
		"""Find the datetime after which new price data is expected to be available."""
		
		today = datetime.datetime.today()
		iso = today.isoformat()
		date = iso.split('T')[0]
		
		availableIso = date + 'T' + self._available
		availableTime = datetime.datetime.fromisoformat(availableIso)
		
		return availableTime
	
	def _MidnightUpdate( self, now ):
		"""Updates the price data and display at midnight."""
		
		self._dataAvailable = _AvailableFromTime()
		self._data.MidnightUpdate()
		prices = self._data.GetPrices()
		self._lastDataUpdate = now
	
	def _DailyDataUpdate( self, now ):
		"""Checks the data source for new data. If there is price data for tomorrow, updates the display."""
		
		prices = self._data.GetPrices()
		
		if None in prices[2]:
			self._data.Update()
			prices = self._data.GetPrices()
			self._lastDataUpdate = now
			
			if not ( None in prices[2] ):
				self._display.Update( prices )
				self._lastDisplayUpdate = now
	
	def _HourlyUpdate( self, now ):
		"""Updates the display every hour."""
		
		prices = self._data.GetPrices()
		self._display.Update( prices )
		self._lastDisplayUpdate = now
	
	def _Mainloop( self ):
		"""Mainloop of the application."""
		
		delta = datetime.timedelta( minutes=self._updateFrequency )
		while self._running:
			now = datetime.datetime.now()
			
			# is midnight
			if now.day != self._lastDataUpdate.day:
				self._MidnightUpdate( now )
			
			# new data will be available soon, check every five minutes
			if now > self._dataAvailable:
				if now - self._lastDataUpdate > delta:
					self._DailyDataUpdate( now )
			
			# update the hourly prices
			if now.hour != self._lastDisplayUpdate.hour:
				self._HourlyUpdate( now )
			
			time.sleep(1)
		
		
	def Start( self ):
		"""Initializes curses and display, then runs the Mainloop in the same thread until application is stopped or interrupted."""
		
		self._running  = True
		self._InitCurses()
		self._InitializeDisplay()
		self._Mainloop()
	
	def Stop( self ):
		"""Stop the application and clear the curses environment."""
		
		self._running = False
		self._EndCurses()


def _InitApp( settings ):
	"""Catch errors related to initializing the application."""
	
	try:
		return App( settings.options )
		
	except WindowSizeError as err:
		msg = 'Terminal window is too small, price display requires at least ' + str( err.height ) + ' lines and ' + str( err.width ) + ' cols'
		_ShowErrorMessage( msg )
		sys.exit( _displayError )
	
	except MissingOptionError as err:
		_ShowErrorMessage( err )
		app = _ResetSettings( settings )
		return app
	
	except Exception as err:
		_ShowErrorMessage( 'Unexpected error occurred' )
		sys.exit( _unexpectedError )

def _InitSettings( settingsPath ):
	"""Catch errors related to initializing the settings."""
	
	try:
		return Config( settingsPath )
	
	except ( ConfigParsingError, MissingTemplateError, TemplateParsingError ) as err:
		_ShowErrorMessage( err )
		sys.exit( _configError )
	
	except Exception as err:
		_ShowErrorMessage( 'Unexpected error occurred' )
		sys.exit( _unexpectedError )

def _ResetSettings( settings ):
	"""Catch errors related to resetting the settings."""
	
	try:
		settings.Reset()
		app = App( settings.options )
		return app
	
	except ( ConfigParsingError, CorruptedTemplateError, MissingTemplateError, TemplateParsingError ) as err:
		_ShowErrorMessage( err )
		sys.exit( _configError )
	
	except MissingOptionError as err:
		_ShowErrorMessage( 'Missing option in template: ' + err.option )
		sys.exit( _configError )
	
	except Exception as err:
		_ShowErrorMessage( 'Unexpected error occurred' )
		sys.exit( _unexpectedError )

def _ShowErrorMessage( msg ):
	"""Show error message or stack trace depending on the debugging level."""
	
	if _debug:
		traceback.print_exc()
	else:
		print( msg, file=sys.stderr )

def _StartApp( app ):
	"""Catch errors related to starting and running the application."""
	
	try:
		app.Start()
	except KeyboardInterrupt:
		if _debug:
			print( 'KeyboardInterrupt, exiting gracefully', file=sys.stderr )
		
		app.Stop()
		sys.exit( _noErrors )
	
	except ( DataParsingError, NoDataError, DataRequestError ) as err:
		_ShowErrorMessage( err )
		app.Stop()
		sys.exit( _dataError )
	
	except Exception as err:
		_ShowErrorMessage( 'Unexpected error occurred' )
		app.Stop()
		sys.exit( _unexpectedError )

def Main():
	"""Parses arguments, reads the config, passes options to the application, and handles any errors."""
	
	# parse commanline arguments
	parser = argparse.ArgumentParser( prog='pricedisplay', description='A terminal display for the Finnish power price.' )
	parser.add_argument( '--debug', action='store_true', help='set debugging mode', required=False )
	parser.add_argument( '--settings', default='', help='path to a settings file', metavar='PATH', required=False )
	args = parser.parse_args()
	
	global _debug
	_debug = args.debug
	settingsPath = args.settings
	
	# create and start the application.
	settings = _InitSettings( settingsPath )
	app = _InitApp( settings )
	_StartApp( app )

if __name__ == '__main__':
	Main()
