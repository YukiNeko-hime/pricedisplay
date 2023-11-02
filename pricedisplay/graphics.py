# -*- coding: UTF-8 -*-

import curses
import datetime
import sparklines

__version__ = '0.2.1'

class WindowSizeError( Exception ):
	def __init__( self, width, height ):
		self.height = height
		self.width = width
		msg = 'Parent window is too small, display requires at least ' + str(height) + ' lines and ' + str(width) + ' cols'
		Exception.__init__(self, msg)

class WindowPositionError( Exception ):
	def __init__( self, y, x ):
		self.y = y
		self.x = x
		msg = 'Display overflows the parent window, when positioned at ' + str(y) + ', ' + str(x)
		Exception.__init__(self, msg)

class _DisplayWindow:
	_minSize = (0,0)
	
	def __init__( self, size, pos, limits, parent=None ):
		y, x = pos
		w, h = size
		self._boundingBox = ((y, x), (y + h, x + w))
		self._low, self._high = limits
		self._size = size		
		
		if parent:
			ph, pw = parent.getmaxyx()
		else:
			ph = curses.LINES - 1
			pw = curses.COLS - 1
		
		if pw < w or ph < h:
			raise WindowSizeError(w, h)
		
		if pw < w + x or ph < h + y:
			raise WindowPositionError( y, x )
		
		if parent:
			self._win = parent.subwin(h, w, y, x)
		else:
			self._win = curses.newwin(h, w, y, x)
	
	def _priceToColor( self, price ):
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
	"""Displays a simple sparkline graph of the power price."""
	
	_carets = ( '▼', '▲' )
	_pastHours = 9
	minSize = (37, 12)
	
	def __init__( self, pos, limits, maxWidth=37, maxHeight=12, pastHours=9, parent=None ):
		
		if pastHours < 0:
			pastHours = 0
		
		if pastHours > maxWidth - 2:
			pastHours = maxWidth - 2
		
		self._pastHours = pastHours
		
		size = ( maxWidth, maxHeight )
		_DisplayWindow.__init__(self, size, pos, limits, parent)
	
	def _AccountForDST( self, yesterday, prices ):
		"""Takes into account the daylight saving time change, when finding the prices visible in the graph."""
		
		now = datetime.datetime.now()
		utc = datetime.datetime.utcnow()
		delta = now.hour - utc.hour
		
		if now.month == 10 and delta == 2:
			start = len(yesterday) + now.hour +1 - 8
			end = start + self._size[0] - 1
			visiblePrices = prices[ start : end ]
		
		if now.month == 3 and delta == 3:
			start = len(yesterday) + now.hour -1 - 8
			end = start + self._size[0] - 1
			visiblePrices = prices[ start : end ]
		
		return visiblePrices
	
	def _AddCarets( self, lines ):
		"""Adds carets to indicate the current hour to the sparklines."""
		
		carets = self._carets
		pastHours = self._pastHours
		curHour = pastHours + 1
		hours = len(lines[0])
		
		lines = [ ' '*hours ] + lines
		
		for height in range( len(lines) - 1 ):
			line = lines[height]
			next = lines[height + 1]
			
			if line[ pastHours ] == ' ' and next[ pastHours ] != ' ':
				upperCaretLine = line[ : pastHours ] + carets[0] + line[ curHour : ]
				lines[height] = upperCaretLine
		
		lowerCaretLine = ' '*pastHours + carets[1] + ' '*( hours - curHour )
		lines.append(lowerCaretLine)
		
		return lines
		
	def _AddLines( self, lines, colors ):
		"""Adds the sparklines and the lower caret line."""
		
		win = self._win
		
		for line in lines[ : -1 ]:
			for hour in range( len(line) ):
				if not line[hour] == self._carets[0]:
					win.addstr(line[hour], colors[hour])
				else:
					win.addstr(line[hour])
			
			win.addstr('\n')
		
		# add the lower caret line without line ending
		win.addstr(lines[-1], curses.A_BOLD)
	
	def _GetColors( self, visiblePrices ):
		"""Gets the colors for the visible price data based on high and low prices."""
		
		hours = len( visiblePrices )
		colors = []
		for hour in range( hours ):
			price = visiblePrices[ hour ]
			color = self._priceToColor( price )
			colors.append( color )
		
		return colors
	
	def _GetSparklines( self, visiblePrices ):
		"""Gets the sparklines for visible prices."""
		
		limits = [ i for i in visiblePrices if i != None ] + [0]
		
		minimum = min( limits )
		maximum = max( limits )
		numLines = self._size[1] - 2		# Leave room for the carets
		hours = len( visiblePrices )
		
		lines = sparklines.sparklines( visiblePrices, num_lines=numLines, minimum=minimum, maximum=maximum )
		
		return lines
	
	def _GetVisiblePrices( self, priceData ):
		now = datetime.datetime.now()
		yesterday, today, tomorrow = priceData
		
		prices = yesterday + today + tomorrow
		pastHours = self._pastHours
		curHour = pastHours + 1
		
		start = len( yesterday ) + now.hour - pastHours
		if start < 0:
			prices = ( -start )*[None] + prices
			start = 0
		
		end = start + self._size[0] - 1
		visiblePrices = prices[ start : end ]
		
		if len(today) != 24:
			visiblePrices = self._AccountForDST( yesterday, prices )
		
		return visiblePrices
	
	def Update( self, priceData ):
		"""Updates the graph, taking into account the changes in dst."""
		
		win = self._win
		visiblePrices = self._GetVisiblePrices( priceData )
		lines = self._GetSparklines( visiblePrices )
		lines = self._AddCarets( lines )
		colors = self._GetColors( visiblePrices )
		
		win.clear()
		self._AddLines( lines, colors )
		win.refresh()

class _DetailWindow( _DisplayWindow ):
	"""Displays price details in text."""
	
	def __init__( self, pos, size, limits, parent=None ):
		_DisplayWindow.__init__(self, size, pos, limits, parent)
	
	def _accountForDST( self, hour, prices ):
		"""Account for the change in daylight saving time."""
		
		now = datetime.datetime.now()
		utc = datetime.datetime.utcnow()
		delta = now.hour - utc.hour
		
		if now.month == 10 and delta == 2:
			nextPrices = prices[1] + prices[2]
			next = nextPrices[hour + 1]
		
		if now.month == 3 and delta == 3:
			nextPrices = prices[1] + prices[2]
			next = nextPrices[hour - 1]
		
		return next
	
	def _addDetail( self, name, price, linebreak=True, textStyle=None ):
		"""Add a detail with a name and price, formatted for the display."""
		
		win = self._win
		n = name.ljust( 10 )
		p = self._formatPrice( price )
		c = self._priceToColor( price )
		
		if textStyle:
			win.addstr( n, textStyle )
		else:
			win.addstr( n )
		
		win.addstr( p, c | curses.A_BOLD )
		
		if linebreak:
			win.addstr('\n')
	
	def _addMissingDetail( self, name, linebreak=True ):
		"""Add a detail when price is missing."""
		
		win = self._win
		n = name.ljust( 10 )
		p = '-'.rjust( 6 )
		
		win.addstr( n )
		win.addstr( p, curses.A_BOLD )
		
		if linebreak:
			win.addstr('\n')
	
	def _formatPrice( self, price ):
		"""Format price for display. Ensure two decimal places adding zeros if necessary. Pad with spaces on the left to align decimal point."""
		
		price = str( price )
		i, d = price.split( '.' )
		d = d.ljust( 2, '0' )
		price = i + '.' + d
		price = price.rjust( 6 )
		
		return price

class DetailCurrentHour( _DetailWindow ):
	"""Displays the price for the current hour."""
	
	minSize = (17,1)
	
	def __init__( self, pos, limits, parent=None ):
		_DetailWindow.__init__( self, pos, self.minSize, limits, parent )
	
	def Update(self, prices):
		"""Update the displayed price."""
		
		win = self._win
		now = datetime.datetime.now()
		
		cur = prices[1][now.hour]
		
		# take dst into account
		if len(prices[1]) != 24:
			cur = self._accountForDST( now.hour, prices )
		
		win.clear()
		if cur:
			self._addDetail( 'current:', cur, False )
		else:
			self._addMissingDetail( 'current:', False )
		win.refresh()

class DetailNextHour( _DetailWindow ):
	"""Displays the price for the current hour."""
	
	minSize = (17,1)
	
	def __init__( self, pos, limits, parent=None ):
		_DetailWindow.__init__( self, pos, self.minSize, limits, parent )
	
	def Update( self, prices ):
		"""Update the displayed price."""
		
		win = self._win
		now = datetime.datetime.now()
		
		nextPrices = prices[1] + prices[2]
		next = nextPrices[now.hour + 1]
		
		# take dst into account
		if len(prices[1]) != 24:
			next = self._accountForDST( now.hour + 1, prices )
		
		win.clear()
		if next:
			self._addDetail( 'next:', next, False )
		else:
			self._addMissingDetail( 'next:', False )
		win.refresh()

class DetailsToday( _DetailWindow ):
	"""Displays the lowest, highest, and average price for today."""
	
	minSize = (17,5)
	
	def __init__( self, pos, limits, parent=None ):
		_DetailWindow.__init__( self, pos, self.minSize, limits, parent )
	
	def _AddPrices( self, prices ):
		"""Adds prices to the display."""
		
		low = min( prices[1] )
		high = max( prices[1] )
		average = sum( prices[1] ) / len( prices[1] )
		average = round( average, 2 )
		
		self._addDetail ('highest:', high )
		self._addDetail( 'average:', average )
		self._addDetail( 'lowest:', low, False )
	
	def _AddMissingPrices( self ):
		"""Adds missing prices to the display, when data isn't available."""
		
		self._addMissingDetail( 'highest:' )
		self._addMissingDetail( 'average:' )
		self._addMissingDetail( 'lowest:', False )
	
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
	
	minSize = (17,5)
	
	def __init__( self, pos, limits, parent=None ):
		_DetailWindow.__init__( self, pos, self.minSize, limits, parent )
	
	def _AddPrices( self, prices ):
		"""Adds prices to the display."""
		
		low = min( prices[2] )
		high = max( prices[2] )
		average = sum( prices[2] ) / len( prices[2] )
		average = round( average, 2 )
		
		self._addDetail( 'highest:', high )
		self._addDetail( 'average:', average )
		self._addDetail( 'lowest:', low, False )
	
	def _AddMissingPrices( self ):
		"""Adds missing prices to the display, when data isn't available."""
		
		self._addMissingDetail( 'highest:' )
		self._addMissingDetail( 'average:' )
		self._addMissingDetail( 'lowest:', False )
	
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

class Display:
	"""Displays a sparkline graph of the price data with details of the prices."""
	
	_minSize = ( 43, 14 )
	_padding = ( 1, 3 )
	_subs = None
	
	def __init__( self, limits, preferred='vertical', reversed=False, past=-40, pos=( 0,0 ), parent=None ):
		self._subs = []
		y, x = pos
		w, h =self._minSize
		
		if parent:
			ph, pw = parentSize = parent.getmaxyx()
		else:
			ph, pw = parentSize = ( curses.LINES, curses.COLS )
		
		if pw < w or ph < h:
			raise WindowSizeError( w, h )
		
		if pw < w + x or ph < h + y:
			raise WindowPositionError( y, x )
		
		layout, size = self._ChooseLayout( parentSize, preferred )
		
		layoutStyle = ( layout, reversed )
		win = self._CreateLayout( size, pos, layoutStyle, limits, past, parent )
		
		self._win = win
	
	def _CreateLayout( self, size, pos, layoutStyle, limits, past, parent ):
		"""Creates the layout chosen for the window from subelements."""
		
		layout, reversed = layoutStyle
		
		if parent:
			newWindow = parent.subwin
		else:
			newWindow = curses.newwin
		
		w, h = size
		y, x = pos
		if layout == 'vertical':
			win = newWindow( h, w, y, x )
			
			if reversed:
				self._VerticalLayoutInverted( limits, past, win )
			else:
				self._VerticalLayout( limits, past, win )
			
		elif layout == 'horizontal':
			win = newWindow( h, w, y, x )
			
			if reversed:
				self._HorizontalLayoutInverted( limits, past, win )
			else:
				self._HorizontalLayout( limits, past, win )
		
		elif layout == 'minimal':
			win = newWindow( h, w, y, x )
			self._MinimalLayout( limits, past, win )
	
	def _ChooseLayout( self, parentSize, preferred ):
		"""Chooses the layout based on user settings and size constraints set by the parent window or the terminal size."""
		ph, pw = parentSize
		
		const = self._SizeConstraints()
		( wMin, wMax ), ( hMin, hMax ) = const
		
		horizontalSize = ( wMax, hMin )
		verticalSize = ( wMin, hMax )
		
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
	
	def _SizeConstraints( self ):	
		"""Calculates the size constraints for the different layouts."""
		
		padY, padX = self._padding
		
		minHorizontal = padX \
				 + DetailsToday.minSize[0] \
				 + padX \
				 + DetailsToday.minSize[0] \
				 + padX
		
		maxHorizontal = padX \
				 + Graph.minSize[0] \
				 + padX \
				 + DetailsToday.minSize[0] \
				 + padX
		
		minVertical = padY \
				+ DetailCurrentHour.minSize[1] \
				+ DetailNextHour.minSize[1] \
				+ padY \
				+ DetailsToday.minSize[1] \
				+ padY \
				+ DetailsTomorrow.minSize[1] \
				+ padY \
				+ padY							# leave space for the lower caret line
		
		maxVertical = padY \
				+ Graph.minSize[1] \
				+ padY \
				+ DetailCurrentHour.minSize[1] \
				+ padY \
				+ DetailsToday.minSize[1] \
				+ padY
		
		horizontal = ( minHorizontal, maxHorizontal )
		vertical = ( minVertical, maxVertical )
		
		constraint =  ( horizontal, vertical )
		
		return constraint
	
	# Different layouts for the window
	
	def _HorizontalLayout(self, limits, past, parent):
		"""Displays the graph and price details in a horizontal layout."""
		
		padY, padX = self._padding
		
		height = DetailCurrentHour.minSize[1] \
			  + DetailNextHour.minSize[1] \
			  + 1 + DetailsToday.minSize[1] \
			  + 1 + DetailsTomorrow.minSize[1] + 1
		
		graph = Graph( ( padY, padX ), limits, maxHeight=height, pastHours=past, parent=parent )
		self._subs.append(graph)
		
		# text on the right side of the graph
		bb = graph.GetBoundingBox()
		pos = ( padY, padX + bb[1][1] )
		self._VerticalTextBlock( pos, limits, parent )
	
	def _HorizontalLayoutInverted( self, limits, past, parent ):
		"""Displays the graph and price details in a horizontal layout."""
		
		padY, padX = self._padding
		
		height = DetailCurrentHour.minSize[1] \
			  + DetailNextHour.minSize[1] \
			  + padY \
			  + DetailsToday.minSize[1] \
			  + padY \
			  + DetailsTomorrow.minSize[1] \
			  + padY
		
		# text on the left side of the graph
		pos = ( padY, padX )
		lastSub = self._VerticalTextBlock( pos, limits, parent )
		
		bb = lastSub.GetBoundingBox()
		pos = ( padY, padX + bb[1][1] )
		graph = Graph( pos, limits, maxHeight=height, pastHours=past, parent=parent )
		self._subs.append(graph)
	
	def _MinimalLayout( self, limits, past, parent ):
		"""Displays only the sparkline graph."""
		
		pos = self._padding
		graph = Graph( pos, limits, pastHours=past, parent=parent )
		self._subs.append(graph)
	
	def _VerticalLayout( self, limits, past, parent ):
		"""Displays the graph and price details in a vertical layout."""
		
		padY, padX = self._padding
		
		width = DetailsToday.minSize[0] \
			 + padX \
			 + DetailsTomorrow.minSize[0]
		
		pos = ( padY, padX )
		graph = Graph( pos, limits, maxWidth=width, pastHours=past, parent=parent )
		self._subs.append(graph)
		
		# text below the graph
		bb = graph.GetBoundingBox()
		pos = ( padY + bb[1][0], padX )
		self._HorizontalTextBlock( pos, limits, parent )
	
	def _VerticalLayoutInverted( self, limits, past, parent ):
		"""Displays the graph and price details in a vertical layout."""
		
		padY, padX = self._padding
		
		width = DetailsToday.minSize[0] \
			 + padX \
			 + DetailsTomorrow.minSize[0]
		
		# text above the graph
		pos = ( padY, padX )
		lastSub = self._HorizontalTextBlock( pos, limits, parent )
		
		bb = lastSub.GetBoundingBox()
		pos = ( padY + bb[1][0], padX )
		graph = Graph( pos, limits, maxWidth=width, pastHours=past, parent=parent )
		self._subs.append(graph)
	
	def _HorizontalTextBlock( self, pos, limits, parent ):
		"""Displays a horzontal block of price details for today and tomorrow."""
		
		padY, padX = self._padding
		
		current = DetailCurrentHour( pos, limits, parent )
		self._subs.append(current)
		
		bb = current.GetBoundingBox()
		pos = ( bb[0][0], padX + bb[1][1] )
		next = DetailNextHour( pos, limits, parent )
		self._subs.append(next)
		
		bb = current.GetBoundingBox()
		pos = ( padY + bb[1][0], padX )
		today = DetailsToday( pos, limits, parent )
		self._subs.append(today)
		
		bb = today.GetBoundingBox()
		pos = ( bb[0][0], padX + bb[1][1] )
		tomorrow = DetailsTomorrow( pos, limits, parent )
		self._subs.append(tomorrow)
		
		return tomorrow
	
	def _VerticalTextBlock( self, pos, limits, parent ):
		"""Displays a vertical block of price details for today and tomorrow."""
		
		padY, padX = self._padding
		
		current = DetailCurrentHour( pos, limits, parent=parent )
		self._subs.append(current)
		
		bb = current.GetBoundingBox()
		pos = ( bb[1][0], bb[0][1] )
		next = DetailNextHour( pos, limits, parent=parent )
		self._subs.append(next)
		
		bb = next.GetBoundingBox()
		pos = (  bb[1][0] + padY, bb[0][1] )
		today = DetailsToday( pos, limits, parent=parent )
		self._subs.append(today)
		
		bb = today.GetBoundingBox()
		pos = ( bb[1][0] + padY, bb[0][1] )
		tomorrow = DetailsTomorrow( pos, limits, parent=parent )
		self._subs.append(tomorrow)
		
		return tomorrow
	
	def Update( self, prices ):
		"""Updates the display."""
		
		for sub in self._subs:
			sub.Update( prices )