# -*- coding: UTF-8 -*-

import os
import usersettings
import yaml

__version__ = '0.2.4'

class ConfigParsingError( Exception ):
	pass

class CorruptedTemplateError( Exception ):
	pass

class MissingTemplateError( Exception ):
	pass

class TemplateParsingError( Exception ):
	pass

class _Queries:
	def _YesNo( self, question ):
		"""A simple yes/no prompt."""
		
		answer = None
		while answer == None:
			inp = input( question + ' (y/n): ' )
			if inp in ( 'y', 'yes' ):
				answer = True
			elif inp in ( 'n', 'no' ):
				answer = False
		
		return answer
	
	def _OptionQuestion( self, question, type, default ):
		"""A prompt for the user to set an option."""
		
		answer = None
		while answer == None:
			inp = input( question + ' (default: ' + str( default ) + '): ' )
			
			if inp == '':
				answer = default
			else:
				try:
					answer = self._Validate( inp, type )
				except ValueError:
					print( 'Not a valid type, must be ' + type )
		
		return answer
	
	def _Validate( self, value, type ):
		"""Checks that the given value is of the given type and returns the value in that type. If the type doesn't match, raises a ValueError."""
		
		if type == 'int':
			try:
				return int( value )
			except:
				raise ValueError( 'Invalid value' )
		
		if type == 'float':
			try:
				return float( value )
			except:
				raise ValueError( 'Invalid value' )
		
		if type == 'string':
			return str( value )
		
		if type == 'char':
			value = str( value )
			if len(value) == 1:
				return value
		
		if type == 'bool':
			if value in ( True, 'True', 'true', '1' ):
				return True
				
			if value in ( False, 'False', 'false', '0' ):
				return False
			
			raise ValueError( 'Invalid value' )
		
		raise ValueError( 'Invalid type' )

class Config(_Queries):
	"""Represents a configuration loaded from a yaml file. If a path is given, tries it first, then then the default user config path. If both fail, creates a new file from a template."""
	
	def __init__( self, path='', templatePath='' ):
		userConfig = usersettings.appdirs.user_config_dir()
		self._userConfigPath = os.path.join( userConfig, 'pricedisplay', __version__ )
		self._userConfigFilePath = os.path.join( self._userConfigPath, 'config.yml' )
		
		if templatePath:
			self._templatePath = templatePath
		else:
			# Use the default path
			modulePath = __file__
			packagePath = os.path.dirname( modulePath )
			self._templatePath = os.path.join( packagePath, 'config.template' )
			self._migrateRulesPath = os.path.join( packagePath, 'config.migrate' )
		
		try:
			open( self._templatePath, 'r' ).close()
		except OSError:
			raise MissingTemplateError( 'Missing template: ' + self._templatePath )
		
		self._oldConfigFilePath, self._oldVersion = self._FindOldPath()
		self._configPath = self._FindPath( path )
		self._config = self._LoadFile( self._configPath )
		
		try:
			self.options = self._Parse()
		except ConfigParsingError as err:
			print(err)
			self.Reset()
	
	def _Edit( self, config ):
		"""Prompts the user to give a value for each option in the option type. Empty string sets the default."""
		
		for keyList, option in _OptionIterator( config ):
			# if option wa migrated, don't ask to edit it
			if 'migrated' in option.keys():
				del option['migrated']
			else:
				question = option['question']
				type = option['type']
				default = option['value']
				
				value = self._OptionQuestion( question, type, default )
				option['value'] = value
	
	def _FindPath( self, path ):
		"""Finds the path to the config file. Tries first the file supplied as an argument, then the default config path. If no file is found, creates one from template."""
		
		# first try the path given as the argument
		try:
			with open( path, 'r' ) as file:
				return path
		except OSError:
			pass
		
		# try the user config path
		ucfp = self._userConfigFilePath
		try:
			with open( ucfp, 'r' ) as file:
				return ucfp
		except OSError:
			pass
		
		# create a new config file from template
		os.makedirs( self._userConfigPath, exist_ok=True )
		config = self.CreateFromTemplate()
		
		return ucfp
	
	def _FindOldPath( self ):
		"""Finds the path of the last config file before current for migration."""
		
		userConfig = usersettings.appdirs.user_config_dir()
		configPath = os.path.join( userConfig, 'pricedisplay' )
		
		gen = os.walk( configPath )
		versions = next( gen )[1]
		
		# don't consider the current version, if it exists
		if versions[-1] == __version__:
			versions.pop()
		
		# if old versions exist, pick the latest
		if len(versions):
			oldVersion = versions[-1]
			oldConfigFilePath = os.path.join( configPath, oldVersion, 'config.yml' )
			
			# verify that the file is readable
			try:
				open( oldConfigFilePath, 'r' ).close()
			except OSError:
				oldConfigFilePath = None
			
		else:
			oldConfigFilePath = None
		
		return oldConfigFilePath, oldVersion
	
	def _LoadFile( self, path ):
		"""Loads the config file as yaml."""
		
		with open( path, 'r' ) as file:
			try:
				config = yaml.safe_load( file )
			except yaml.scanner.ScannerError:
				raise ConfigParsingError( "Can't parse the configuration file: " + path )
		
		return config
	
	def _Parse( self ):
		"""Parses the config file. Raises ConfigParsingError, if the options in the file have values that don't match with the type defined by the option."""
		
		config = self._config
		options = {}
		for key, option in _OptionIterator( config ):
			try:
				value = self._Validate( option['value'], option['type'] )
				options[key] = value
			except ValueError:
				raise ConfigParsingError( "Can't parse the configuration file: " + self._configPath )
		
		return options
	
	def CreateFromTemplate( self ):
		"""Creates a new config file from a template, and writes it to the default config path. Gives the user an option to edit the values."""
		
		with open( self._templatePath, 'r' ) as file:
			try:
				config = yaml.safe_load( file )
			except yaml.scanner.ScannerError:
				raise TemplateParsingError( "Can't parse the template file: " + self._templatePath )
		
		question = 'Do you want to edit the configuration file?'
		if self._oldConfigFilePath:
			migrate = self._YesNo( 'Do you want to migrate the old configuration file (version ' + self._oldVersion + ')?' )
			if migrate:
				self.Migrate( config )
				question = 'Do you want to edit the new options?'
		
		edit = self._YesNo( question )
		if edit:
			self._Edit( config )
		
		with open( self._userConfigFilePath, 'w' ) as file:
			yaml.safe_dump( config, file )
		
		self._config = config
	
	def Migrate( self, config ):
		old = self._LoadFile( self._oldConfigFilePath )
		
		rulebook = { 'renamed': {} }
		try:
			rules = self._LoadFile( self._migrateRulesPath )
			rulebook.update( rules )
		except OSError:
			print( 'No migration rules found, continuing without.' )
		
		for key, option in _OptionIterator( old ):
			try:
				# use migration rules for the keys
				if key in rulebook['renamed'].keys():
					key = rulebook['renamed'][key]
				
				# find the old option in the new template, if it exists
				keys = key.split('.')
				item = config
				for key in keys:
					item = item[key]
			
			# No such option in the new config file, skip it.
			except KeyError:
				pass
			
			# if the option type matches, overwrite the default in template
			if item['type'] == option['type']:
				item['value'] = option['value']
				item['migrated'] = True
	
	def Reset( self ):
		"""Asks the user to resets the current cpnfiguration file, with an option for editing the values. If the user declines, raises a ConfigParsingError."""
		
		reset = self._YesNo('Do you want to reset the config?')
		if reset:
			self.CreateFromTemplate()
			try:
				self.options = self._Parse()
			except ConfigParsingError as err:
				# The template is corrupted
				raise CorruptedTemplateError( 'The template file is corrupted: ' + self._templatePath )
		else:
			raise ConfigParsingError( "Can't parse the configuration file: " + self._configPath )

class _OptionIterator:
	"""Iterates through the options in a given yaml representation of a config file."""
	
	def __init__( self, config ):
		self._config = config
		self._keys = [ list( config.keys() ) ]
		self._indices = [-1]
	
	def __iter__( self ):
		return self
	
	def __next__( self ):
		keys = self._keys
		indices = self._indices
		
		# Move to the next index in the index chain
		indices[-1] += 1
		while not indices[-1] < len( keys[-1] ):
			indices.pop()
			keys.pop()
			if len( indices ):
				indices[-1] += 1
			else:
				raise StopIteration
		
		
		item = self._UseKeys( keys, indices )
		while not self._IsOption( item ):
			# The item is not an option or dictionary, move to next one
			if type(item) != dict:
				return self.__next__()
			
			keys.append( list(item.keys()) )
			indices.append(0)
			
			item = self._UseKeys( keys, indices )
		
		keyList = self._MapKeys( keys, indices )
		key = '.'.join( keyList )
		
		return key, item
	
	def _IsOption( self, item ):
		"""Check if the given item is an option. An option is a dictionary, which has the keys 'value' and 'type'. An option may also contain additional keys."""
		
		# not a dictionary
		if type(item) != dict:
			return False
		
		keys = item.keys()
		if 'value' in keys and 'type' in keys:
			return True
		else:
			return False
	
	def _MapKeys( self, keys, indices ):
		keyList = []
		
		for i in range( len(keys) ):
			key = keys[i]
			index = indices[i]
			
			keyList.append( key[index] )
		
		return keyList
	
	def _UseKeys( self, keys, indices ):
		"""Uses a list of keys to find the current dictionary in a multi-level config dictionary."""
		
		item = self._config
		keyList = self._MapKeys( keys, indices )
		for key in keyList:
			item = item[key]
		
		return item
