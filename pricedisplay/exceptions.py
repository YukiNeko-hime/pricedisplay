# -*- coding: UTF-8 -*-

__version__ = '0.5.0'

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
class DataParsingError( Exception ):
	pass

class DataRequestError( Exception ):
	pass

class NoDataError( Exception ):
	pass


# display related errors
class CollectionSizeError( Exception ):
	pass

class WindowPositionError( Exception ):
	def __init__( self, pos ):
		self.y = pos[0]
		self.x = pos[1]
		msg = 'Display overflows the parent window, when positioned at ' + str( self.y ) + ', ' + str( self.x )
		Exception.__init__( self, msg )
		
class WindowSizeError( Exception ):
	def __init__( self, size ):
		self.height = size[0]
		self.width = size[1]
		msg = 'Parent window is too small, display requires at least ' + str( self.height ) + ' lines and ' + str( self.width ) + ' cols'
		Exception.__init__( self, msg )