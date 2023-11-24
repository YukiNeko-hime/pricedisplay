# -*- coding: UTF-8 -*-

import curses
import datetime
import sparklines
import warnings

from .exceptions import MissingOptionError
from .exceptions import WindowSizeError, WindowPositionError

__version__ = '0.4.1'

class Point:
	"""Represents a point on the terminal screen."""
	
	y = 0
	x = 0
	pos = ( 0,0 )
	
	def __init__( self, pos ):
		self.y = pos[0]
		self.x = pos[1]
		self.pos = pos
	
	def __getitem__( self, index ):
		return self.pos[index]
	
	def __len__( self ):
		return len( self.pos )
	
	def __str__( self ):
		return 'Point( ' + str(self.pos) + ' )'

class Size:
	"""Represents the size of an object."""
	
	height = 0
	width = 0
	size = ( 0,0 )
	
	def __init__( self, size ):
		self.height = size[0]
		self.width = size[1]
		self.size = size
	
	def __getitem__( self, index ):
		return self.size[index]
	
	def __len__( self ):
		return len( self.size )
	
	def __str__( self ):
		return 'Size( ' + str(self.size) + ' )'

class BBox( Point, Size ):
	"""Represents the bounding box of an object. Two bounding boxes can be added returning a bounding box encompassing them both."""
	
	bottom = 0
	left = 0
	right = 0
	top = 0
	
	def __init__( self, size, pos ):
		Point.__init__( self, pos )
		Size.__init__( self, size )
		
		self.bottom = self.y + self.height
		self.left = self.x
		self.right = self.x + self.width
		self.top = self.y
	
	def __add__( self, bb ):
		bottom = max( self.bottom, bb.bottom )
		left = min( self.left, bb.left )
		right = max( self.right, bb.right )
		top = min( self.top, bb.top )
		
		y = top
		x = left
		pos = ( y, x )
		
		height = bottom - top
		width = right - left
		size = ( height, width )
		
		return BBox( size, pos )
	
	def __contains__( self, bb ):
		if self.bottom < bb.bottom:
			return False
		
		if self.left > bb.left:
			return False
		
		if self.right < bb.right:
			return False
		
		if self.top > bb.top:
			return False
		
		return True
	
	def __getitem__( self, index ):
		attrs = tuple( self.size ) + tuple( self.pos )
		return attrs[index]
	
	def __len__( self ):
		attrs = self.size + self.pos
		return len( attrs )
	
	def __str__( self ):
		return 'BBox( ' + str(self.size) + ', ' + str(self.pos) + ' )'

class _DisplayWindow:
	"""Base class for display windows. Defines a bounding box and checks that the window fits in the parent window."""
	
	minSize = Size( ( 0,0 ) )
	
	def __init__( self, size, pos, parent=None ):
		self._boundingBox = bb = BBox( size, pos )
		self._pos = pos
		self._size = size
		
		self._FitsInside( bb, parent )
		self._win = parent.subwin( *bb )
	
	def _FitsInside( self, boundingBox, parent ):
		"""Check that the subwindow fits inside the parent. If no parent was specified, use the whole terminal screen."""
		
		# if no parent is specified, use the whole terminal screen
		if not parent:
			parent = curses.initscr()
		
		self._parent = parent
		
		# find the available space
		parSize = parent.getmaxyx()
		parBB = BBox( parSize, ( 0,0 ) )
		
		# check that all the content fits in the space
		if parBB.height < boundingBox.height or parBB.width < boundingBox.height:
			raise WindowSizeError( size )
		
		if not boundingBox in parBB:
			raise WindowPositionError( pos )
	
	def GetBoundingBox( self ):
		"""Returns the bounding box for the display window."""
		
		return self._boundingBox

class _PriceDisplayWindow( _DisplayWindow ):
	"""Base class for price display windows. Defines helper functions for color coding prices and taking into account DST changes."""
	
	minSize = Size( ( 0,0 ) )
	
	def __init__( self, size, pos, options, parent=None ):
		self._low, self._high = options['limits']
		self._normalTimezone = options['normalTimezone']
		
		_DisplayWindow.__init__( self, size, pos, parent )
	
	def _AccountForDST( self, hoursInDay ):
		"""Takes into account the daylight saving time change, when finding the index for the current hour."""
		
		now = datetime.datetime.now()
		utc = datetime.datetime.utcnow()
		
		timezone = now.hour - utc.hour
		offset = timezone - self._normalTimezone
		delta = hoursInDay - 24
		
		index = now.hour + (abs(delta) + delta)/2 - offset
		
		return int( index )
	
	def _PriceToColor( self, price ):
		"""Finds a curses color pair based on the given price (low, medium, high)."""
		
		if price == None:
			color = 0
		elif price < self._low:
			color = 1
		elif price < self._high:
			color = 2
		else:
			color = 3
		
		return curses.color_pair( color )

class Graph( _PriceDisplayWindow ):
	"""Displays a simple sparkline graph of the power price, color coded based on the limits given in options. The size of the graph, carets used to mark the current hour, and the number of past hours to show can be given as options."""
	
	minSize = Size( ( 12, 37 ) )
	_defaultOptions = {
		'height': minSize.height,
		'width': minSize.width,
		'carets': [ '▼', '▲' ],
		'pastHours': 8
	}
	
	def __init__( self, pos, options, parent=None ):
		opts = self._defaultOptions.copy()
		opts.update( options )
		
		self._carets = opts['carets']
		pastHours = opts['pastHours']
		width = opts['width']
		
		# normalize the number of past hours to fit in the space allowed
		if pastHours < 0:
			pastHours = 0
		
		if pastHours > width - 2:
			pastHours = width - 2
		
		self._pastHours = pastHours
		
		h = opts['height']
		w = opts['width']
		size = Size( ( h, w ) )
		_PriceDisplayWindow.__init__(self, size, pos, options, parent)
	
	def _AddCarets( self, lines ):
		"""Adds carets to indicate the current hour in the sparklines."""
		
		pos, neg = lines
		carets = self._carets
		pastHours = self._pastHours
		curHour = pastHours + 1
		hours = len( ( pos + neg )[0] )
		
		# add an empty line to beginning and end to always fit the carets
		# if there are no lines, include the caret on the line
		if pos:
			pos = [ ' '*hours ] + pos
			pos = self._AddUpperCaret( pos )
		else:
			pos = [ ' '*pastHours + carets[0] + ' '*(hours - curHour) ]
		
		if neg:
			neg = neg + [ ' '*hours ]
			neg = self._AddLowerCaret( neg )
		else:
			neg = [ ' '*pastHours + carets[1] + ' '*(hours - curHour) ]
		
		return pos, neg
	
	def _AddLowerCaret( self, lines ):
		"""Add the lower caret to the given lines."""
		
		carets = self._carets
		pastHours = self._pastHours
		curHour = pastHours + 1
		
		# find the highest possible position for the upper caret, searching from bottom up
		i = len( lines ) - 2
		while i > 0:
			prev = lines[i + 1]
			line = lines[i]
			next = lines[i - 1]
			
			# first empty space under negative sparkline on current hour
			if prev[ pastHours ] != ' ' and next[ pastHours ] == ' ':
				lowerCaretLine = prev[ : pastHours ] + carets[1] + prev[ curHour : ]
				lines[i + 1] = lowerCaretLine
				break
			
			# last possible line for the lower caret, if price is positive
			# the character is empty, because the value for the price is None
			if i == 1 and next[ pastHours ] == ' ':
				lowerCaretLine = next[ : pastHours ] + carets[1] + next[ curHour : ]
				lines[0] = lowerCaretLine
			
			i -= 1
		
		return lines
	
	def _AddUpperCaret( self, lines ):
		"""Add the upper caret to the given lines."""
		
		carets = self._carets
		pastHours = self._pastHours
		curHour = pastHours + 1
		
		# find the lowest possible position for the upper caret, searching from top down
		i = 0
		while i < len( lines ) - 1:
			line = lines[i]
			next = lines[i + 1]
			
			# last empty space for the upper caret, if price is positive
			if line[ pastHours ] == ' ' and next[ pastHours ] != ' ':
				upperCaretLine = line[ : pastHours ] + carets[0] + line[ curHour : ]
				lines[i] = upperCaretLine
				break
			
			# last possible line for the upper caret, if price is negative
			if i == len( lines ) - 2 and next[ pastHours ] == ' ':
				upperCaretLine = next[ : pastHours ] + carets[0] + next[ curHour : ]
				lines[-1] = upperCaretLine
			
			i += 1
		
		return lines
	
	def _AddLines( self, lines, colors, prices ):
		"""Adds the sparklines and the lower caret line."""
		
		win = self._win
		pos, neg = lines
		
		# add the upper caret line
		win.addstr( pos[0] )
		win.addstr( '\n' )
		
		self._AddPositiveLines( pos, colors, prices )
		self._AddNegativeLines( neg, colors, prices )
		
		# add the lower caret line
		win.addstr( neg[-1] )
	
	def _AddNegativeLines( self, lines, colors, prices ):
		"""Adds negative lines to the graph."""
		
		win = self._win
		
		for line in lines[:-1]:
			for hour in range( len(line) ):
				price = prices[hour]
				if not line[hour] in self._carets and price != None and price < 0:
					win.addstr(line[hour], colors[hour] | curses.A_REVERSE)
				else:
					win.addstr(line[hour])
			
			win.addstr( '\n' )
	
	def _AddPositiveLines( self, lines, colors, prices ):
		"""Adds positive lines to the graph."""
		
		win = self._win
		
		for line in lines[1:]:
			for hour in range( len(line) ):
				if not line[hour] in self._carets:
					win.addstr(line[hour], colors[hour])
				else:
					win.addstr(line[hour])
			
			win.addstr( '\n' )
	
	def _GetColors( self, visiblePrices ):
		"""Gets the colors for the visible price data based on high and low prices."""
		
		hours = len( visiblePrices )
		colors = []
		for hour in range( hours ):
			price = visiblePrices[ hour ]
			color = self._PriceToColor( price )
			
			colors.append( color )
		
		return colors
	
	def _GetLimits( self, visiblePrices ):
		"""Find the minimum and maximum for the visible prices."""
		
		# filter out None for comparing prices
		filteredPrices = []
		for price in visiblePrices:
			if price != None:
				filteredPrices.append( price )
		
		# add zero for better visualization of prices
		filteredPrices += [0]
		
		minimum = min( filteredPrices )
		maximum = max( filteredPrices )
		
		return minimum, maximum
	
	def _GetScaledLineParameters( self, limits ):
		"""Find the scaled parameters, when there are both positive and negative prices."""
		
		numLines = self._size.height - 2		# Leave room for the carets
		minimum, maximum = limits
		
		ratio = maximum / ( maximum - minimum )
		numPosLines = round( ratio*numLines )
		numNegLines = numLines - numPosLines
		
		if numPosLines == 0:
			numPosLines = 1
			numNegLines = numLines - 1
		
		if numNegLines == 0:
			numPosLines = numLines - 1
			numNegLines = 1
		
		if maximum < abs( minimum ):
			posMaximum = - minimum * ( numPosLines / numNegLines )
			negMaximum = - minimum
		else:
			posMaximum = maximum
			negMaximum = maximum * ( numNegLines / numPosLines )
		
		posParams = numPosLines, posMaximum
		negParams = numNegLines, negMaximum
		
		return posParams, negParams
	
	def _GetLineParameters( self, hasPrices, limits ):
		"""Find the parameters for drawing the sparklines."""
		
		numLines = self._size.height - 2		# Leave room for the carets
		minimum, maximum = limits
		hasPos, hasNeg = hasPrices
		
		if hasPos and hasNeg:
			posParams, negParams = self._GetScaledLineParameters( limits )
		elif hasNeg:
			posParams = ( 0,0 )
			negParams = numLines, -minimum
		
		else:
			posParams = ( numLines, maximum)
			negParams = ( 0,0 )
		
		return posParams, negParams
	
	def _GetNegativeSparklines( self, prices, numLines, maximum ):
		"""Get sparklines for negative prices."""
		
		# normalize negative prices to positive values
		normPrices = []
		for price in prices:
			if price != None:
				normPrices.append( price + maximum )
			else:
				normPrices.append( None )
		
		if numLines:
			sparks = sparklines.sparklines( normPrices, num_lines=numLines, minimum=0, maximum=maximum )
		else:
			sparks = []
		
		return sparks
	
	def _GetPositiveSparklines( self, prices, numLines, maximum ):
		"""Get sparklines for positive prices."""
		
		if numLines:
			sparks = sparklines.sparklines( prices, num_lines=numLines, minimum=0, maximum=maximum )
		else:
			sparks = []
		
		return sparks
		
	def _GetSparklines( self, visiblePrices ):
		"""Gets the sparklines for visible prices."""
		
		limits = self._GetLimits( visiblePrices )
		posPrices, negPrices = self._SplitPrices( visiblePrices )
		
		hasPos = any( price is not None for price in posPrices )
		hasNeg = any( price is not None for price in negPrices )
		hasPrices = hasPos, hasNeg
		
		posParams, negParams = self._GetLineParameters( hasPrices, limits )
		
		posSparks = self._GetPositiveSparklines( posPrices, *posParams )
		negSparks = self._GetNegativeSparklines( negPrices, *negParams )
		
		return posSparks, negSparks
	
	def _GetVisiblePrices( self, priceData ):
		"""Gets the prices, which are visible taking into account dst and the number of past hours to show. Returns a list of the visible prices."""
		
		now = datetime.datetime.now()
		yesterday, today, tomorrow = priceData
		
		prices = yesterday + today + tomorrow
		pastHours = self._pastHours
		curHour = pastHours + 1
		
		hours = len( today )
		if hours != 24:
			index = self._AccountForDST( hours )
		else:
			index = now.hour
		
		start = len( yesterday ) + index - pastHours
		end = start + self._size.width - 1
		
		visiblePrices = prices[ start : end ]
		
		return visiblePrices
	
	def _SplitPrices( self, visiblePrices ):
		"""Splits the prices to positive and negative lists, filling in None for missing values."""
		
		# split out positive prices
		posPrices = []
		for price in visiblePrices:
			if price != None and price >= 0:
				posPrices.append( price )
			else:
				posPrices.append( None )
		
		# split out negative prices
		negPrices = []
		for price in visiblePrices:
			if price != None and price < 0:
				negPrices.append( price )
			else:
				negPrices.append( None )
		
		return posPrices, negPrices
	
	def Update( self, priceData ):
		"""Updates the graph, taking into account the changes in dst."""
		
		win = self._win
		visiblePrices = self._GetVisiblePrices( priceData )
		lines = self._GetSparklines( visiblePrices )
		lines = self._AddCarets( lines )
		colors = self._GetColors( visiblePrices )
		
		win.clear()
		self._AddLines( lines, colors, visiblePrices )
		win.refresh()

class _DetailWindow( _PriceDisplayWindow ):
	"""Displays price details in text."""
	
	def __init__( self, pos, size, options, parent=None ):
		_PriceDisplayWindow.__init__(self, size, pos, options, parent)
	
	def _AddDetail( self, name, price, linebreak=True, textStyle=None ):
		"""Adds a detail with a name and price, formatted for the display."""
		
		win = self._win
		n = name.ljust( 10 )
		p = self._FormatPrice( price )
		c = self._PriceToColor( price )
		
		if textStyle:
			win.addstr( n, textStyle )
		else:
			win.addstr( n )
		
		win.addstr( p, c | curses.A_BOLD )
		
		if linebreak:
			win.addstr( '\n' )
	
	def _AddMissingDetail( self, name, linebreak=True ):
		"""Adds a detail when price is missing."""
		
		win = self._win
		n = name.ljust( 10 )
		p = '-'.rjust( 6 )
		
		win.addstr( n )
		win.addstr( p, curses.A_BOLD )
		
		if linebreak:
			win.addstr( '\n' )
	
	def _FormatPrice( self, price ):
		"""Formats price for display. Ensure two decimal places adding zeros if necessary. Pad with spaces on the left to align decimal point."""
		
		price = str( price )
		i, d = price.split( '.' )
		d = d.ljust( 2, '0' )
		price = i + '.' + d
		price = price.rjust( 6 )
		
		return price

class DetailCurrentHour( _DetailWindow ):
	"""Displays the price for the current hour."""
	
	minSize = Size( ( 1, 17 ) )
	
	def __init__( self, pos, options, parent=None ):
		_DetailWindow.__init__( self, pos, self.minSize, options, parent )
	
	def Update(self, prices):
		"""Updates the displayed price."""
		
		win = self._win
		now = datetime.datetime.now()
		
		today = prices[1]
		hours = len( today )
		if hours == 24:
			index = now.hour
		else:
			index = self._AccountForDST( hours )
		
		cur = today[index]
		
		win.clear()
		if cur:
			self._AddDetail( 'current:', cur, False )
		else:
			self._AddMissingDetail( 'current:', False )
		win.refresh()

class DetailNextHour( _DetailWindow ):
	"""Displays the price for the current hour."""
	
	minSize = Size( ( 1, 17 ) )
	
	def __init__( self, pos, options, parent=None ):
		_DetailWindow.__init__( self, pos, self.minSize, options, parent )
	
	def Update( self, prices ):
		"""Updates the displayed price."""
		
		win = self._win
		now = datetime.datetime.now()
		
		today = prices[1]
		tomorrow = prices[2]
		
		hours = len( today )
		if hours == 24:
			index = now.hour + 1
		else:
			index = self._AccountForDST( hours ) + 1
		
		nextPrices = today + tomorrow
		next = nextPrices[index]
		
		win.clear()
		if next:
			self._AddDetail( 'next:', next, False )
		else:
			self._AddMissingDetail( 'next:', False )
		win.refresh()

class DetailsToday( _DetailWindow ):
	"""Displays the lowest, highest, and average price for today."""
	
	minSize = Size( ( 5, 17 ) )
	
	def __init__( self, pos, options, parent=None ):
		_DetailWindow.__init__( self, pos, self.minSize, options, parent )
	
	def _AddPrices( self, prices ):
		"""Adds prices to the display."""
		
		# filter out None for comparing prices
		filteredPrices = []
		for price in prices[1]:
			if price != None:
				filteredPrices.append( price )
		
		low = min( filteredPrices )
		high = max( filteredPrices )
		average = sum( filteredPrices ) / len( filteredPrices )
		average = round( average, 2 )
		
		self._AddDetail ('highest:', high )
		self._AddDetail( 'average:', average )
		self._AddDetail( 'lowest:', low, False )
	
	def _AddMissingPrices( self ):
		"""Adds missing prices to the display, when data isn't available."""
		
		self._AddMissingDetail( 'highest:' )
		self._AddMissingDetail( 'average:' )
		self._AddMissingDetail( 'lowest:', False )
	
	def Update( self, prices ):
		"""Updates the displayed prices."""
		
		win = self._win
		now = datetime.datetime.now()
		
		win.clear()
		
		win.addstr( 'TODAY\n\n', curses.color_pair(4) )
		
		if prices[1][0]:
			self._AddPrices(prices)
		else:
			self._AddMissingPrices()
		
		win.refresh()

class DetailsTomorrow( _DetailWindow ):
	"""Displays the lowest, highest, and average price for tomorrow."""
	
	minSize = Size( ( 5, 17 ) )
	
	def __init__( self, pos, options, parent=None ):
		_DetailWindow.__init__( self, pos, self.minSize, options, parent )
	
	def _AddPrices( self, prices ):
		"""Adds prices to the display."""
		
		# filter out None for comparing prices
		filteredPrices = []
		for price in prices[2]:
			if price != None:
				filteredPrices.append( price )
		
		low = min( filteredPrices )
		high = max( filteredPrices )
		average = sum( filteredPrices ) / len( filteredPrices )
		average = round( average, 2 )
		
		self._AddDetail( 'highest:', high )
		self._AddDetail( 'average:', average )
		self._AddDetail( 'lowest:', low, False )
	
	def _AddMissingPrices( self ):
		"""Adds missing prices to the display, when data isn't available."""
		
		self._AddMissingDetail( 'highest:' )
		self._AddMissingDetail( 'average:' )
		self._AddMissingDetail( 'lowest:', False )
	
	def Update( self, prices ):
		"""Updates the displayed prices."""
		
		win = self._win
		
		win.clear()
		win.addstr( 'TOMORROW\n\n', curses.color_pair(4) )
		
		if prices[2][0]:
			self._AddPrices( prices )
		else:
			self._AddMissingPrices()
		
		win.refresh()

class _Collection( _DisplayWindow ):
	"""A collection of subwindows for structuring a display."""
	
	minSize = Size( ( 0,0 ) )
	_padding = Size( ( 0,0 ) )
	_subs = None
	
	def __init__( self, pos=( 0,0 ), size=( 0,0 ), padding=( 0,0 ), options={}, parent=None ):
		self._options = options
		self._padding = padding
		self._subs = []
		
		_DisplayWindow.__init__( self, size, pos, parent )
	
	def _AddElements( self, elems ):
		"""Adds elements from an array."""
		
		y, x = pos = self._pos
		pad = self._padding
		
		rows = len( elems )
		cols = len( elems[0] )
		
		# add the elements from left to right and top to bottom
		i = 0
		while i < rows:
			j = 0
			while j < cols:
				elem = elems[ i ][ j ]
				current = elem( pos, self._options, self._parent )
				self._subs.append( current )
				
				bb = current.GetBoundingBox()
				pos = ( pos[0], bb.right + pad.width )
				
				j += 1
			
			pos = ( pad.height + bb.bottom, x )
			i += 1
	
	def Update( self, prices ):
		"""Updates the display."""
		
		for sub in self._subs:
			sub.Update( prices )

class _SpacedCollection( _Collection ):
	"""A collection with a margin around the elements."""
	
	minSize = Size( ( 0,0 ) )
	_padding = Size( ( 0,0 ) )
	
	def __init__( self, pos=( 0,0 ), size=( 0,0 ), margin=( 0,0 ), padding=( 0,0 ), options={}, parent=None ):
		
		# check that the content fits in the parent window with the specified margin
		paddedSize = ( 2*margin.height + size.height, 2*margin.width + size.width )
		bb = BBox( paddedSize, pos )
		self._FitsInside( bb, parent )
		
		# add margin to left and top with positioning
		y = pos.y + margin.height
		x = pos.x + margin.width
		pos = Point( ( y, x ) )
		
		_Collection.__init__( self, pos, size, padding, options, parent )

class HourDetails( _Collection ):
	minSize = Size( ( 2, 17 ) )
	_padding = Size( ( 0, 0 ) )
	
	def __init__( self, pos, options, parent=None ):
		_Collection.__init__( self, pos, self.minSize, self._padding, options, parent )
		
		elems = [
				[ DetailCurrentHour ],
				[ DetailNextHour ]
			]
		
		self._AddElements( elems )

class HorizontalDetails( _Collection ):
	"""Displays a horzontal block of price details for today and tomorrow."""
	
	minSize = Size( ( 7, 37 ) )
	_padding = Size( ( 1, 3 ) )
	
	def __init__( self, pos, options, parent=None ):
		_Collection.__init__( self, pos, self.minSize, self._padding, options, parent )
		
		elems = [
				[ DetailCurrentHour, DetailNextHour ],
				[ DetailsToday, DetailsTomorrow ]
			]
		
		self._AddElements( elems )

class VerticalDetails( _Collection ):
	"""Displays a vertical block of price details for today and tomorrow."""
	
	minSize = Size( ( 14, 17 ) )
	_padding = Size( ( 1, 0 ) )
	
	def __init__( self, pos, options, parent=None ):
		_Collection.__init__( self, pos, self.minSize, self._padding, options, parent )
		
		# add all the elements from top down in one column
		elems = [
				[ HourDetails ],
				[ DetailsToday ],
				[ DetailsTomorrow ]
			]
		
		self._AddElements( elems )

class Display( _SpacedCollection ):
	"""Displays a sparkline graph of the price data with details of the prices."""
	
	minSize = Size( ( 14, 43 ) )
	_margin = Size( ( 1, 3 ) )
	_padding = Size( ( 1, 3 ) )
	
	def __init__( self, options, pos=Point( ( 0,0 ) ), parent=None ):
		pad = self._padding
		
		# find the available space
		if not parent:
			parent = curses.initscr()
		
		parSize = Size( parent.getmaxyx() )
		contentHeight = parSize.height - 2*pad.height
		contentWidth = parSize.width - 2*pad.width
		contentSize = Size( ( contentHeight, contentWidth ) )
		
		# find the layout and size based on available space and user options
		layout, size = self._ChooseLayout( contentSize, options['preferred'] )
		options['layout'] = layout
		
		# init the collection and create layout
		_SpacedCollection.__init__( self, pos, size, self._margin, self._padding, options, parent )
		self._CreateLayout( options )
	
	def _ChooseLayout( self, contentSize, preferred ):
		"""Chooses the layout based on user settings and size constraints set by the parent window."""
		
		contBB = BBox( contentSize, ( 0,0 ) )
		
		verticalSize = self._VerticalSize()
		horizontalSize = self._HorizontalSize()
		minimalSize = Graph.minSize
		
		vertBB = BBox( verticalSize, ( 0,0 ) )
		horBB = BBox( horizontalSize, ( 0,0 ) )
		
		canUseVertical = vertBB in contBB
		canUseHorizontal = horBB in contBB
		
		if  preferred == 'minimal':
			layout = 'minimal'
			size = minimalSize
		
		elif preferred == 'horizontal' and canUseHorizontal:
			layout = 'horizontal'
			size = horizontalSize
		
		elif preferred == 'vertical' and canUseVertical:
			layout = 'vertical'
			size = verticalSize
		
		elif canUseVertical:
			layout = 'vertical'
			size = verticalSize
		
		elif canUseHorizontal:
			layout = 'horizontal'
			size = horizontalSize
		
		else:
			layout = 'minimal'
			size = minimalSize
		
		return layout, size
	
	def _CreateLayout( self, options ):
		"""Creates the layout chosen for the window from subelements."""
		
		layout = options['layout']
		
		if layout == 'vertical':
			self._VerticalLayout( options )
			
		elif layout == 'horizontal':
			self._HorizontalLayout( options )
			
		elif layout == 'minimal':
			self._MinimalLayout( options )
	
	def _HorizontalSize( self ):	
		"""Calculates the size of the horizontal layout."""
		
		pad = self._padding
		
		# maximal horizontal size is the width of the graph, the width of the vertical details
		maxHorizontal = Graph.minSize.width + pad.width + VerticalDetails.minSize.width
		
		# minimal vertical size is the height of the vertical details plus an extra line for the lower graph caret
		minVertical = VerticalDetails.minSize.height + pad.height			# leave space for the lower graph caret line
		
		horizontalSize = Size( ( minVertical, maxHorizontal ) )
		
		return horizontalSize
	
	def _VerticalSize( self ):	
		"""Calculates the size of the vertical layout."""
		
		pad = self._padding
		
		# minimal horizontal size is the width of the horizontal details
		minHorizontal = HorizontalDetails.minSize.width
		
		# maximal vertical size is the height of the graph and the height of the horizontal details
		maxVertical =Graph.minSize.height + pad.height + HorizontalDetails.minSize.height
		
		verticalSize = Size( ( maxVertical, minHorizontal ) )
		
		return verticalSize
	
	def _HorizontalLayout( self, options ):
		"""Displays the graph and price details in a horizontal layout."""
		
		options['height'] = VerticalDetails.minSize.height + 1		# leave extra line for the lower graph caret
		
		row = [ Graph, VerticalDetails ]
		if options['reverse']:
			row.reverse()				# reverse the order of the elements
		
		elems = [ row ]
		self._AddElements( elems )
	
	def _MinimalLayout( self, options ):
		"""Displays only the sparkline graph."""
		
		elems = [ [ Graph ] ]
		self._AddElements( elems )
	
	def _VerticalLayout( self, options ):
		"""Displays the graph and price details in a vertical layout."""
		
		options['width'] = HorizontalDetails.minSize.width
		
		elems = [
				[ Graph ],
				[ HorizontalDetails ]
			]
		
		if options['reverse']:
			elems.reverse()				# reverse the order of the elements
		
		self._AddElements( elems )
