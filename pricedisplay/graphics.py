# -*- coding: UTF-8 -*-

import curses
import datetime
import sparklines

#__version__ = '0.1.0'
__version__ = '0.2.0'

class WindowSizeError(Exception):
	def __init__(self, width, height):
		self.height = height
		self.width = width
		msg = 'Parent window is too small, display requires at least ' + str(height) + ' lines and ' + str(width) + ' cols'
		Exception.__init__(self, msg)

class WindowPositionError(Exception):
	def __init__(self, y, x):
		self.y = y
		self.x = x
		msg = 'Display overflows the parent window, when positioned at ' + str(y) + ', ' + str(x)
		Exception.__init__(self, msg)

class _DisplayWindow:
	_minSize = (0,0)
	
	def __init__(self, size, pos, limits, parent=None):
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
			raise WindowPositionError(x, y)
		
		if parent:
			self._win = parent.subwin(h, w, y, x)
		else:
			self._win = curses.newwin(h, w, y, x)
			
	
	def _priceToColor(self, price):
		"""Finds a curses color pair based on the given price (low, medium, high)."""
		if price < self._low:
			color = 1
		elif price < self._high:
			color = 2
		else:
			color = 3
		
		return curses.color_pair(color)
	
	def GetBoundingBox(self):
		"""Returns the bounding bow for the dispay window."""
		return self._boundingBox

class Graph(_DisplayWindow):
	"""Displays a simple sparkline graph of the power price."""
	
	minSize = (37, 11)
	
	def __init__(self, pos, limits, maxWidth=37, maxHeight=11, parent=None):
		size = ( maxWidth, maxHeight )
		_DisplayWindow.__init__(self, size, pos, limits, parent)
	
	def _accountForDST(self, yesterday, prices):
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
	
	def Update(self, priceData):
		"""Updates the graph, taking into account the changes in dst."""
		win = self._win
		now = datetime.datetime.now()
		yesterday, today, tomorrow = priceData
		
		prices = yesterday + today + tomorrow
		
		start = len(yesterday) + now.hour - 8
		end = start + self._size[0] - 1
		visiblePrices = prices[ start : end ]
		
		if len(today) != 24:
			visiblePrices = self._accountForDST(yesterday, prices)
		
		limits = [ i for i in visiblePrices if i != None ] + [0]
		
		minimum = min(limits)
		maximum = max(limits)
		
		win.clear()
		numLines = self._size[1]-1
		lines = sparklines.sparklines( visiblePrices, num_lines=numLines, minimum=minimum, maximum=maximum )
		for line in lines:
			for i in range( len(line) ):
				if visiblePrices[i] != None:
					color = self._priceToColor( visiblePrices[i] )
				else:
					color = curses.color_pair(0)
				
				win.addstr(line[i], color)
			
			win.addstr('\n')
		
		pointer = '^'.rjust(9)
		
		win.addstr(pointer, curses.A_BOLD)
		win.refresh()

class _DetailWindow(_DisplayWindow):
	"""Displays price details in text."""
	
	def __init__(self, pos, size, limits, parent=None):
		_DisplayWindow.__init__(self, size, pos, limits, parent)
	
	def _accountForDST(self, hour, prices):
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
	
	def _addDetail(self, name, price, linebreak=True, textStyle=None):
		"""Add a detail with a name and price, formatted for the display."""
		win = self._win
		
		n = name.ljust(10)
		p = self._formatPrice(price)
		c = self._priceToColor(price)
		
		if textStyle:
			win.addstr( n, textStyle )
		else:
			win.addstr( n )
		
		win.addstr( p, c | curses.A_BOLD )
		
		if linebreak:
			win.addstr('\n')
	
	def _addMissingDetail(self, name, linebreak=True):
		"""Add a detail when price is missing."""
		win = self._win
		
		n = name.ljust(10)
		p = '-'.rjust(6)
		
		win.addstr( n )
		win.addstr( p, curses.A_BOLD )
		
		if linebreak:
			win.addstr('\n')
	
	def _formatPrice(self, price):
		"""Format price for display. Ensure two decimal places adding zeros if necessary. Pad with spaces on the left to align decimal point."""
		price = str(price)
		i, d = price.split('.')
		d = d.ljust(2, '0')
		price = i + '.' + d
		price = price.rjust(6)
		
		return price

class DetailCurrentHour(_DetailWindow):
	"""Displays the price for the current hour."""
	
	minSize = (17,1)
	
	def __init__(self, pos, limits, parent=None):
		_DetailWindow.__init__(self, pos, self.minSize, limits, parent)
	
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
			self._addDetail('current:', cur, False)
		else:
			self._addMissingDetail('current:', False)
		win.refresh()

class DetailNextHour(_DetailWindow):
	"""Displays the price for the current hour."""
	
	minSize = (17,1)
	
	def __init__(self, pos, limits, parent=None):
		_DetailWindow.__init__( self, pos, self.minSize, limits, parent )
	
	def Update(self, prices):
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
			self._addDetail('next:', next, False)
		else:
			self._addMissingDetail('next:', False)
		win.refresh()

class DetailsToday(_DetailWindow):
	"""Displays the lowest, highest, and average price for today."""
	
	minSize = (17,5)
	
	def __init__(self, pos, limits, parent=None):
		_DetailWindow.__init__( self, pos, self.minSize, limits, parent )
	
	def _AddPrices(self, prices):
		"""Adds prices to the display."""
		
		low = min(prices[1])
		high = max(prices[1])
		average = sum( prices[1] ) / len( prices[1] )
		average = round(average, 2)
		
		self._addDetail('highest:', high)
		self._addDetail('average:', average)
		self._addDetail('lowest:', low, False)
	
	def _AddMissingPrices(self):
		"""Adds missing prices to the display, when data isn't available."""
		
		self._addMissingDetail('highest:',)
		self._addMissingDetail('average:')
		self._addMissingDetail('lowest:', False)
	
	def Update(self, prices):
		"""Updates the displayed prices."""
		
		win = self._win
		now = datetime.datetime.now()
		
		win.clear()
		
		win.addstr('TODAY\n\n', curses.color_pair(4))
		
		if prices[1][0]:
			self._AddPrices(prices)
		else:
			self._AddMissingPrices()
		
		win.refresh()

class DetailsTomorrow(_DetailWindow):
	"""Displays the lowest, highest, and average price for tomorrow."""
	
	minSize = (17,5)
	
	def __init__(self, pos, limits, parent=None):
		_DetailWindow.__init__(self, pos, self.minSize, limits, parent)
	
	def _AddPrices(self, prices):
		"""Adds prices to the display."""
		
		low = min(prices[2])
		high = max(prices[2])
		average = sum( prices[2] ) / len( prices[2] )
		average = round(average, 2)
		
		self._addDetail('highest:', high)
		self._addDetail('average:', average)
		self._addDetail('lowest:', low, False)
	
	def _AddMissingPrices(self):
		"""Adds missing prices to the display, when data isn't available."""
		
		self._addMissingDetail('highest:')
		self._addMissingDetail('average:')
		self._addMissingDetail('lowest:', False)
	
	def Update(self, prices):
		"""Updates the displayed prices."""
		
		win = self._win
		
		win.clear()
		win.addstr('TOMORROW\n\n', curses.color_pair(4))
		
		if prices[2][0]:
			self._AddPrices(prices)
		else:
			self._AddMissingPrices()
		
		win.refresh()

class Display:
	"""Displays a sparkline graph of the price data with details of the prices."""
	
	_minSize = ( 43, 13 )
	_padding = 3
	_subs = None
	
	def __init__(self, limits, preferred=False, reversed=False, pos=( 0,0 ), parent=None):
		if parent:
			ph, pw = parent.getmaxyx()
			size = ( pw, ph )
			
		else:
			size = ( curses.COLS-1, curses.LINES-1 )
		
		if size[0] < self._minSize[0] or size[1] < self._minSize[1]:
			raise WindowSizeError( self._minSize[0], self._minSize[1] )
		
		self._size = size
		self._subs = []
		x, y = pos
		
		maxHorizontal = self._padding \
				 + Graph.minSize[0] \
				 + self._padding + DetailsToday.minSize[0] \
				 + self._padding
		
		maxVertical = 1 + Graph.minSize[1] \
				+ 1 + DetailCurrentHour.minSize[1] \
				+ 1 + DetailsToday.minSize[1] + 1
		
		minHorizontal = self._padding + Graph.minSize[0] \
				 + self._padding
		
		minVertical = 1 + DetailCurrentHour.minSize[1] \
				+ DetailNextHour.minSize[1] \
				+ 1 + DetailsToday.minSize[1] \
				+ 1 + DetailsTomorrow.minSize[1] + 1
		
		
		horizontalSize = ( maxHorizontal, minVertical )
		verticalSize = ( minHorizontal, maxVertical )
		
		canUseVertical = ( minHorizontal < size[0] ) and ( maxVertical < size[1] )
		canUseHorizontal = ( maxHorizontal < size[0] ) and ( minVertical < size[1] )
		
		if parent:
			newWindow = parent.subwin
		else:
			newWindow = curses.newwin
		
		if  preferred == 'minimal':
			layout = 'minimal'
		
		elif preferred == 'horizontal' and canUseHorizontal:
			layout = 'horizontal'
		
		elif preferred == 'vertical' and canUseVertical:
			layout = 'vertical'
		
		elif canUseVertical:
			layout = 'vertical'
		
		elif canUseHorizontal:
			layout = 'horizontal'
		
		else:
			layout = 'minimal'
		
		
		if layout == 'vertical':
			w, h = verticalSize
			win = newWindow( h, w, y, x )
			
			if reversed:
				self._VerticalLayoutInverted(limits, parent=win)
			else:
				self._VerticalLayout(limits, parent=win)
			
		elif layout == 'horizontal':
			w, h = horizontalSize
			win = newWindow( h, w, y, x )
			
			if reversed:
				self._HorizontalLayoutInverted(limits, parent=win)
			else:
				self._HorizontalLayout(limits, parent=win)
		
		elif layout == 'minimal':
			w, h = self._minSize
			win = newWindow( h, w, y, x )
			self._MinimalLayout(limits, parent=win)
		
		self._win = win
	
	def _HorizontalLayout(self, limits, parent):
		"""Displays the graph and price details in a horizontal layout."""
		
		height = DetailCurrentHour.minSize[1] \
			  + DetailNextHour.minSize[1] \
			  + 1 + DetailsToday.minSize[1] \
			  + 1 + DetailsTomorrow.minSize[1] + 1
		
		pos = (1, self._padding)
		graph = Graph( pos, limits, maxHeight=height, parent=parent )
		self._subs.append(graph)
		
		# text on the right side of the graph
		bb = graph.GetBoundingBox()
		pos = ( 1, self._padding + bb[1][1] )
		self._VerticalTextBlock( pos, limits, parent )
	
	def _HorizontalLayoutInverted(self, limits, parent):
		"""Displays the graph and price details in a horizontal layout."""
		
		height = DetailCurrentHour.minSize[1] \
			  + DetailNextHour.minSize[1] \
			  + 1 + DetailsToday.minSize[1] \
			  + 1 + DetailsTomorrow.minSize[1] + 1
		
		# text on the left side of the graph
		pos = (1, self._padding)
		lastSub = self._VerticalTextBlock( pos, limits, parent )
		
		bb = lastSub.GetBoundingBox()
		pos = ( 1, self._padding + bb[1][1] )
		graph = Graph( pos, limits, maxHeight=height, parent=parent )
		self._subs.append(graph)
	
	def _MinimalLayout(self, limits, parent):
		"""Displays only the sparkline graph."""
		
		pos = (1, self._padding)
		graph = Graph( pos, limits, parent=parent )
		self._subs.append(graph)
	
	def _VerticalLayout(self, limits, parent):
		"""Displays the graph and price details in a vertical layout."""
		
		width = DetailsToday.minSize[0] \
			 + self._padding \
			 + DetailsTomorrow.minSize[0]
		
		pos = (1, self._padding)
		graph = Graph( pos, limits, maxWidth=width, parent=parent )
		self._subs.append(graph)
		
		# text below the graph
		bb = graph.GetBoundingBox()
		pos = ( 1 + bb[1][0], self._padding )
		self._HorizontalTextBlock( pos, limits, parent )
	
	def _VerticalLayoutInverted(self, limits, parent):
		"""Displays the graph and price details in a vertical layout."""
		
		width = DetailsToday.minSize[0] \
			 + self._padding \
			 + DetailsTomorrow.minSize[0]
		
		# text above the graph
		pos = (1, self._padding)
		lastSub = self._HorizontalTextBlock( pos, limits, parent )
		
		bb = lastSub.GetBoundingBox()
		pos = ( 1 + bb[1][0], self._padding )
		graph = Graph( pos, limits, maxWidth=width, parent=parent )
		self._subs.append(graph)
	
	def _HorizontalTextBlock(self, pos, limits, parent):
		"""Displays a horzontal block of price details for today and tomorrow."""
		
		current = DetailCurrentHour( pos, limits, parent=parent )
		self._subs.append(current)
		
		bb = current.GetBoundingBox()
		pos = ( bb[0][0], self._padding + bb[1][1] )
		next = DetailNextHour( pos, limits, parent=parent )
		self._subs.append(next)
		
		bb = current.GetBoundingBox()
		pos = ( 1 + bb[1][0], self._padding )
		today = DetailsToday( pos, limits, parent=parent )
		self._subs.append(today)
		
		bb = today.GetBoundingBox()
		pos = ( bb[0][0], self._padding + bb[1][1] )
		tomorrow = DetailsTomorrow( pos, limits, parent=parent )
		self._subs.append(tomorrow)
		
		return tomorrow
	
	def _VerticalTextBlock(self, pos, limits, parent):
		"""Displays a vertical block of price details for today and tomorrow."""
		
		current = DetailCurrentHour( pos, limits, parent=parent )
		self._subs.append(current)
		
		bb = current.GetBoundingBox()
		pos = ( bb[1][0], bb[0][1] )
		next = DetailNextHour( pos, limits, parent=parent )
		self._subs.append(next)
		
		bb = next.GetBoundingBox()
		pos = (  bb[1][0] + 1, bb[0][1] )
		today = DetailsToday( pos, limits, parent=parent )
		self._subs.append(today)
		
		bb = today.GetBoundingBox()
		pos = ( bb[1][0] + 1, bb[0][1] )
		tomorrow = DetailsTomorrow( pos, limits, parent=parent )
		self._subs.append(tomorrow)
		
		return tomorrow
	
	def Update(self, prices):
		"""Updates the display."""
		
		for sub in self._subs:
			sub.Update(prices)
