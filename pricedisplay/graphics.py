# -*- coding: UTF-8 -*-

import curses
import datetime
import sparklines
import warnings

from .exceptions import MissingOptionError
from .exceptions import WindowSizeError, WindowPositionError

__version__ = '0.4.0'

class _DisplayWindow:
	_minSize = ( 0,0 )
	
	def __init__( self, size, pos, options, parent=None ):
		y, x = pos
		h, w = size
		self._boundingBox = ((y, x), (y + h, x + w))
		self._low, self._high = options['limits']
		self._size = size		
		
		try:
			self._normalTimezone = options['normalTimezone']
		except KeyError as err:
			raise MissingOptionError( err.args )
		
		if not parent:
			parent = curses.initscr()
		
		ph, pw = parent.getmaxyx()
		
		if pw < w or ph < h:
			raise WindowSizeError(w, h)
		
		if pw < w + x or ph < h + y:
			raise WindowPositionError( y, x )
		
		self._win = parent.subwin(h, w, y, x)
	
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
	
	def GetBoundingBox( self ):
		"""Returns the bounding bow for the dispay window."""
		
		return self._boundingBox

class Graph( _DisplayWindow ):
	"""Displays a simple sparkline graph of the power price, color coded based on the limits given in options. The size of the graph, carets used to mark the current hour, and the number of past hours to show can be given as options."""
	
	minSize = ( 12, 37 )
	_defaultOptions = {
		'height': minSize[0],
		'width': minSize[1],
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
		
		size = ( opts['height'], opts['width'] )
		_DisplayWindow.__init__(self, size, pos, options, parent)
	
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
				if not line[hour] in self._carets and prices[hour] < 0:
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
		
		numLines = self._size[0] - 2		# Leave room for the carets
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
		
		numLines = self._size[0] - 2		# Leave room for the carets
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
		end = start + self._size[1] - 1
		
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

class _DetailWindow( _DisplayWindow ):
	"""Displays price details in text."""
	
	def __init__( self, pos, size, options, parent=None ):
		_DisplayWindow.__init__(self, size, pos, options, parent)
	
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
	
	minSize = ( 1, 17 )
	
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
	
	minSize = ( 1, 17 )
	
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
	
	minSize = ( 5, 17 )
	
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
	
	minSize = ( 5, 17 )
	
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

class HorizontalDetails:
	"""Displays a horzontal block of price details for today and tomorrow."""
	
	minSize = ( 7, 37 )
	_padding = ( 1, 3 )
	_subs = None
	
	def __init__( self, pos, options, parent ):
		y, x = pos
		h, w = self.minSize
		self._boundingBox = ((y, x), (y + h, x + w))
		
		self._subs = []
		padY, padX = self._padding
		
		# add the elements from left to right and top to bottom in a two by two grid
		current = DetailCurrentHour( pos, options, parent )
		self._subs.append(current)
		
		topLeft, bottomRight = current.GetBoundingBox()
		
		pos = ( y, padX + bottomRight[1] )
		next = DetailNextHour( pos, options, parent )
		self._subs.append(next)
		
		pos = ( padY + bottomRight[0], x )
		today = DetailsToday( pos, options, parent )
		self._subs.append(today)
		
		pos = ( padY + bottomRight[0], padX + bottomRight[1] )
		tomorrow = DetailsTomorrow( pos, options, parent )
		self._subs.append(tomorrow)
	
	def GetBoundingBox( self ):
		"""Returns the bounding bow for the dispay window."""
		
		return self._boundingBox
	
	def Update( self, prices ):
		"""Updates the display."""
		
		for sub in self._subs:
			sub.Update( prices )

class VerticalDetails:
	"""Displays a vertical block of price details for today and tomorrow."""
	
	minSize = ( 14, 17 )
	_padding = ( 1, 3 )
	_subs = None
	
	def __init__( self, pos, options, parent ):
		y, x = pos
		h, w = self.minSize
		self._boundingBox = ((y, x), (y + h, x + w))
		
		self._subs = []
		padY, padX = self._padding
		
		# add all the elements from top down in one column
		elems = [
			( DetailCurrentHour, 0 ),
			( DetailNextHour, padY ),
			( DetailsToday, padY ),
			( DetailsTomorrow, 0 )
		]
		
		for elem, padding in elems:
			sub = elem( pos, options, parent )
			self._subs.append( sub )
			
			topLeft, bottomRight = sub.GetBoundingBox()
			pos = ( bottomRight[0] + padding, x )
	
	def GetBoundingBox( self ):
		"""Returns the bounding bow for the dispay window."""
		
		return self._boundingBox
	
	def Update( self, prices ):
		"""Updates the display."""
		
		for sub in self._subs:
			sub.Update( prices )

class Display:
	"""Displays a sparkline graph of the price data with details of the prices."""
	
	_minSize = ( 14, 43 )
	_padding = ( 1, 3 )
	_subs = None
	
	def __init__( self, options, pos=( 0,0 ), parent=None ):
		self._subs = []
		y, x = pos
		h, w =self._minSize
		
		# find the available space
		if not parent:
			parent = curses.initscr()
		
		ph, pw = parentSize = parent.getmaxyx()
		
		# check that all the content fits in the space
		if pw < w or ph < h:
			raise WindowSizeError( w, h )
		
		if pw < w + x or ph < h + y:
			raise WindowPositionError( y, x )
		
		# find the layout and size based on available space and user options
		layout, size = self._ChooseLayout( parentSize, options['preferred'] )
		options['layout'] = layout
		
		self._CreateLayout( size, pos, options, parent )
	
	def _ChooseLayout( self, parentSize, preferred ):
		"""Chooses the layout based on user settings and size constraints set by the parent window."""
		
		ph, pw = parentSize
		
		constraints = self._SizeConstraints()
		( hMin, hMax ), ( wMin, wMax ) = constraints
		
		horizontalSize = ( hMin, wMax )
		verticalSize = ( hMax, wMin )
		
		canUseVertical = ( hMax <= ph ) and ( wMin <= pw )
		canUseHorizontal = ( hMin <= ph ) and ( wMax <= pw )
		
		if  preferred == 'minimal':
			layout = 'minimal'
			size = self._minSize
		
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
			size = self._minSize
		
		return layout, size
	
	def _CreateLayout( self, size, pos, options, parent ):
		"""Creates the layout chosen for the window from subelements."""
		
		h, w = size
		y, x = pos

		self._win = win = parent.subwin( h, w, y, x )
		layout = options['layout']
		
		if layout == 'vertical':
			self._VerticalLayout( options, win )
			
		elif layout == 'horizontal':
			self._HorizontalLayout( options, win )
			
		elif layout == 'minimal':
			self._MinimalLayout( options, win )
	
	def _SizeConstraints( self ):	
		"""Calculates the size constraints for the different layouts."""
		
		padY, padX = self._padding
		
		
		# minimal horizontal size is the width of the horizontal details plus padding
		minHorizontal = padX   + HorizontalDetails.minSize[1] +   padX
		
		
		# maximal horizontal size is the width of the graph, the width of the vertical details and padding
		maxHorizontal = padX   + Graph.minSize[1] +   padX    + VerticalDetails.minSize[1] +   padX
		
		
		# minimal vertical size is the height of the vertical details plus padding and an extra line for the lower graph caret
		minVertical = padY \
				+ VerticalDetails.minSize[0] \
				+ padY \
				+ padY						# leave space for the lower graph caret line
		
		
		# maximal vertical size is is the height of the graph, the height of the horizontal details and padding
		maxVertical = padY \
				+ Graph.minSize[0] \
				+ padY \
				+ HorizontalDetails.minSize[0] \
				+ padY
		
		
		horizontal = ( minHorizontal, maxHorizontal )
		vertical = ( minVertical, maxVertical )
		
		constraint =  ( vertical, horizontal )
		
		return constraint
	
	def _HorizontalLayout(self, options, parent):
		"""Displays the graph and price details in a horizontal layout."""
		
		padY, padX = self._padding
		options['height'] = VerticalDetails.minSize[0] + 1		# leave extra line for the lower graph caret
		
		elems = [ Graph, VerticalDetails ]
		if options['reverse']:
			elems.reverse()				# reverse the order of the elements
		
		# add the elements from left to right
		pos = ( padY, padX )
		for elem in elems:
			sub = elem( pos, options, parent )
			self._subs.append( sub )
			
			topLeft, bottomRight = sub.GetBoundingBox()
			pos = ( padY, padX + bottomRight[1] )
	
	def _MinimalLayout( self, options, parent ):
		"""Displays only the sparkline graph."""
		
		pos = self._padding
		graph = Graph( pos, options, parent )
		self._subs.append( graph )
	
	def _VerticalLayout( self, options, parent ):
		"""Displays the graph and price details in a vertical layout."""
		
		padY, padX = self._padding
		options['width'] = HorizontalDetails.minSize[1]
		
		elems = [ Graph, HorizontalDetails ]
		if options['reverse']:
			elems.reverse()				# reverse the order of the elements
		
		# add the elements from top to bottom
		pos = ( padY, padX )
		for elem in elems:
			sub = elem( pos, options, parent )
			self._subs.append( sub )
			
			topLeft, bottomRight = sub.GetBoundingBox()
			pos = ( padY + bottomRight[0], padX )
	
	def Update( self, prices ):
		"""Updates the display."""
		
		for sub in self._subs:
			sub.Update( prices )
