# -*- coding: UTF-8 -*-

__version__ = '0.4.0'

# general errors
class MissingOptionError( Exception ):
	def __init__( self, option ):
		self.option = option
		msg = 'Missing option: ' + option
		
		Exception.__init__( self, msg )


# config related errors
class ConfigParsingError( Exception ):
	pass

class CorruptedTemplateError( Exception ):
	pass

class MissingTemplateError( Exception ):
	pass

class TemplateParsingError( Exception ):
	pass


# data fetching and parsing related errors
class NoDataError(Exception):
	pass

class DataParsingError(Exception):
	pass

class DataRequestError(Exception):
	pass


# display related errors
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