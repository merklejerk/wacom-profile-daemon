#!/usr/bin/env python3

"""
The MIT License (MIT)

Copyright (c) 2017 Lawrence Forman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import argparse
import datetime
import json
import math
import re
import subprocess
import sys
import time

def run( cmd, capture=True, lines=False, hide_errors=False ):
	stdout = subprocess.PIPE if capture else None
	stderr = subprocess.STDOUT
	if hide_errors:
		stderr = subprocess.DEVNULL
	cp = subprocess.run( cmd, stdout=stdout, stderr=stderr, shell=True )
	if cp.returncode == 0:
		if capture:
			stdout = str( cp.stdout, 'utf-8' )
			if not lines:
				return stdout
			return stdout.split( '\n' )
		return True
	return False

def eprint( *args, **kwargs ):
	print( "(!)", *args, file=sys.stderr, **kwargs )

class Bounds:
	def __init__( self, min_x=0, min_y=0, max_x=0, max_y=0 ):
		self.min_x = min_x
		self.min_y = min_y
		self.max_x = max_x
		self.max_y = max_y

	@property
	def width( self ):
		return self.max_x - self.min_x

	@width.setter
	def width( self, value ):
		self.max_x = value + self.min_x

	@property
	def height( self ):
		return self.max_y - self.min_y

	@height.setter
	def height( self, value ):
		self.max_y = value + self.min_y

	@property
	def aspect( self ):
		return self.width / float( self.height )

	@property
	def values( self ):
		yield self.min_x
		yield self.min_y
		yield self.max_x
		yield self.max_y

	@property
	def geometry_str( self ):
		return '%dx%d+%d+%d' % \
			(math.ceil( self.width ), math.ceil( self.height),
				math.floor( self.min_x ), math.floor( self.min_y ))

	@classmethod
	def from_geometry_str( cls, geom_str ):
		mo = re.match( r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', geom_str )
		nums = [int( i ) for i in mo.groups( ) ]
		return cls( nums[2], nums[3], nums[0], nums[1] )

	def __str__( self ):
		return self.geometry_str

	def __eq__( self, other ):
		if not isinstance( other, self.__class__ ):
			return False
		return self.min_x == other.min_x and self.min_y == other.min_y and \
		 	self.max_x == other.max_x and self.max_y == other.max_y

	def __ne__( self, other ):
		return not self.__eq__( other )

class Wacom:
	@staticmethod
	def get_device_id( device_type ):
		for line in run( 'xsetwacom --list devices', lines=True ):
			mo = re.search( r'\bid:\s+(\d+)\s+type:\s+%s\s*$' % device_type,
				line )
			if mo != None:
				return mo.group( 1 )
		return None

	@staticmethod
	def get_initial_area( device_id ):
		run( "xsetwacom --set %s resetarea" % device_id, hide_errors=True )
		return Wacom.get_area( device_id )

	@staticmethod
	def get_area( device_id ):
		lines = run( "xsetwacom --get %s Area" % device_id, lines=True,
			hide_errors=True )
		if lines is False:
			return None
		output = lines[0]
		if re.match( r'\d+ \d+ \d+ \d+', output ):
			nums = [int( i ) for i in re.split( '\s+', output )]
			return Bounds( *nums )
		return None

	@staticmethod
	def set_area( device_id, area ):
		return re.match( r'\s*', run( r'xsetwacom --set %s Area %s' %
			(device_id,' '.join( str( i ) for i in area.values )) ) ) != None

	@staticmethod
	def set_output_area( device_id, area ):
		return re.match( r'\s*', run( r'xsetwacom --set %s MapToOutput %s' %
			(device_id,area.geometry_str) ) ) != None

	@staticmethod
	def set_raw_opt( device_id, opt_str ):
		return re.match( r'\s*',
			run( r'xsetwacom --set %s %s' % (device_id,opt_str) ) ) != None

	@staticmethod
	def get_devices( ):
		devices = set( )
		for line in run( r'xsetwacom --list devices', lines=True ):
			mo = re.match(
				r'(.*\b)\s+id:\s+(\d+)\s+type:\s+(PAD|STYLUS|ERASER)\s*$',
				line )
			if mo != None:
				devices.add( (mo.group( 2 ), mo.group( 1 ), mo.group( 3 )) )
		return devices

class XUtil:
	@staticmethod
	def get_all_windows_ids( ):
		output = run( r'xprop -root _NET_CLIENT_LIST' )
		return re.search( '#\s+(.*)$', output ).group( 1 ).split( ', ' )

	@staticmethod
	def find_window_id( regexp ):
		for window_id in get_all_windows_ids( ):
			 if re.search( regexp, XUtil.get_window_name( window_id ) ):
				 return window_id
		return None

	@staticmethod
	def find_window_id_by_class( cls ):
		for window_id in get_all_windows_ids( ):
			for window_class in XUtil.get_window_classes( window_id ):
				if cls == window_class:
					return window_id
		return None

	@staticmethod
	def get_window_classes( window_id ):
		output = run( r'xprop -id %s WM_CLASS' % window_id )
		mo = re.match( '[^=]+=\s+(.+)$', output )
		if mo:
			return [cls.strip( '"' ) for cls in mo.group( 1 ).split( ', ' )]
		return []

	@staticmethod
	def get_window_name( window_id ):
		output = run( r'xprop -id %s WM_NAME' % window_id )
		mo = re.search( r'=\s+"(.*)"\s*$', output )
		if mo:
			return mo.group( 1 )
		return ""

	@staticmethod
	def get_active_window_id( ):
		output = run( r'xprop -root _NET_ACTIVE_WINDOW' )
		return re.search( r': window id # (.*)\s*$', output ).group( 1 )

	@staticmethod
	def get_window_bounds( window_id, include_frame=False ):
		bounds = Bounds( )
		lines = run( 'xwininfo -id "%s"' % window_id, lines=True )
		if not lines:
			return None
		for line in lines:
			mo = re.match( r'^\s*Absolute upper-left X:\s+ (\d+)', line )
			if mo:
				bounds.min_x = int( mo.group( 1 ) )
				continue
			mo = re.match( r'^\s*Absolute upper-left Y:\s+ (\d+)', line )
			if mo:
				bounds.min_y = int( mo.group( 1 ) )
				continue
			mo = re.match( r'^\s*Width:\s+(\d+)', line )
			if mo:
				bounds.width = int( mo.group( 1 ) )
				continue
			mo = re.match( r'^\s*Height:\s+(\d+)', line )
			if mo:
				bounds.height = int( mo.group( 1 ) )
				continue
		if include_frame:
			output = run( 'xprop _NET_FRAME_EXTENTS -id "%s"' % window_id )
			mo = re.match( r'.* = \d+, \d+, (\d+), \d+', output )
			if mo:
				bounds.min_y -= int( mo.group( 1 ) )
		return bounds

	@staticmethod
	def get_active_display_by_index( idx ):
		for line in run( "xrandr", lines=True ):
			mo = re.match( r'(\S+)\s+connected\s+', line )
			if mo != None:
				if idx == 0:
					return mo.group( 1 )
				idx -= 1
		return None

	@staticmethod
	def get_display_bounds( display_id ):
		for line in run( "xrandr", lines=True ):
			mo = re.match(
				r'%s\s+connected\s+\w+\s+([\d+-x]+)' % display_id, line )
			if mo != None:
				return Bounds.from_geometry_str( mo.group( 1 ) )
		return None

class DeviceProperties:
	def __init__( self, dev_id, name, dev_type, initial_area=None ):
		self.dev_id = dev_id
		self.name = name
		self.dev_type = dev_type
		self.initial_area = initial_area

	def __eq__( self, other ):
		if not isinstance( other, self.__class__ ):
			return False
		return self.dev_id == other.dev_id

	def __ne__( self, other ):
		return not self.__eq__( other )

class Daemon:
	_Match_Keys = ('window-title','window-class','window-id')
	_Match_Window_Operators = {
		'window-title': lambda wid, regexp: \
			re.search( regexp, XUtil.get_window_name( wid ) ) != None,
		'window-class': lambda wid, cls: cls in XUtil.get_window_classes( wid ),
		'window-id': lambda wid, wid2: wid == wid2
	}

	def __init__( self, config_file, update_rate=1.0, debug=False ):
		self.update_rate = update_rate
		self.debug = debug
		with open( config_file ) as f:
			self.config = json.loads( f.read( ) )

	def _debug_print( self, *args, **kwargs ):
		if self.debug:
			timestamp = '[@%s]' % datetime.datetime.now( ).time( )
			print( timestamp, *args, **kwargs )

	def run( self ):
		self._active_window = None
		self._active_window_bounds = None
		self._devices = {}

		while True:
			if self._update_devices( ):
				self._on_devices_changed( )
			if self._update_active_window( ):
				self._on_window_changed( )
			time.sleep( self.update_rate )

	def _update_devices( self ):
		changed = False
		curr_devices = Wacom.get_devices( )

		# Add new devices
		for dev_id, dev_name, dev_type in curr_devices:
			if dev_id not in self._devices:
				initial_area = Wacom.get_initial_area( dev_id )
				self._devices[dev_id] = \
					DeviceProperties( dev_id, dev_name, dev_type, initial_area )
				self._debug_print( "New device: %s (%s)."
					% (dev_name, dev_type) )
				changed = True

		# Remove missing devices.
		for dev in list( self._devices.values( ) ):
			if (dev.dev_id, dev.name, dev.dev_type) not in curr_devices:
				self._debug_print( "Remove device: %s (%s)."
					% (dev.name, dev.dev_type) )
				del self._devices[dev.dev_id]
				changed = True

		return changed

	def _update_active_window( self ):
		new_active = XUtil.get_active_window_id( )
		new_active_bounds = XUtil.get_window_bounds( new_active ) if \
			new_active else None
		if new_active != self._active_window or \
				new_active_bounds != self._active_window_bounds:
			self._active_window = new_active
			self._active_window_bounds = new_active_bounds
			return True
		return False

	def _on_devices_changed( self ):
		self._debug_print( "Devices changed." )
		self._apply_active_rules( )

	def _on_window_changed( self ):
		self._debug_print( "Window changed." )
		self._apply_active_rules( )

	def _apply_active_rules( self ):
		for device_prefix in self.config:
			matching_devices = self._get_matching_devices( device_prefix )
			if len( matching_devices ) > 0:
				self._debug_print( 'Using ruleset "%s".' % device_prefix )
				ruleset = self._order_ruleset( self.config[device_prefix] )
				for rule_name, rule in ruleset:
					if self._is_rule_active( rule ):
						self._debug_print( 'Applying rule "%s".' % rule_name )
						self._apply_rule( rule, matching_devices )

	def _get_matching_devices( self, prefix ):
		return [dev for dev in self._devices.values( ) if
			dev.name.startswith( prefix )  ]

	def _order_ruleset( self, ruleset ):
		# Order rules from least specific to most specific (more matchers)
		return sorted( ruleset.items( ),
			key=lambda r: len( [k for k in self._Match_Keys if k in r[1]] ) )

	def _apply_rule( self, rule, devices ):
		if 'mapping' in rule:
			self._apply_mapping( rule['mapping'], devices )

		opt_targets = (
			('pad','PAD'),
			('stylus','STYLUS'),
			('eraser','ERASER') )
		for opt_key, dev_type in opt_targets:
			if opt_key in rule:
				self._apply_options( rule[opt_key],
					[dev for dev in devices if dev.dev_type == dev_type] )

	def _is_rule_active( self, rule ):
		# All matchers must return true.
		for k in (k for k in self._Match_Keys if k in rule):
			if not self._active_window:
				return False
			if not self._Match_Window_Operators[k]( self._active_window,
					rule[k] ):
				return False
		return True

	def _apply_mapping( self, mapping_type, devices ):
		output_area = self._get_mapping_output_area( mapping_type )
		if output_area != None:
			for dev in devices:
				if dev.initial_area is not None:
					self._debug_print( 'Mapping "%s".' % dev.name )
					if not self._map_device( dev.dev_id, output_area,
							dev.initial_area ):
						eprint( "Failed to map area on device %s." % dev.name )

	def _apply_options( self, opts, devices ):
		for dev in devices:
			self._debug_print( 'Setting options for "%s".' % dev.name )
			for opt in opts:
				if not Wacom.set_raw_opt( dev.dev_id, opt ):
					eprint( 'Failed to set option "%s" on device "%s".'
						% (opt,dev.name) )

	def _get_mapping_output_area( self, mapping_type ):
		if mapping_type == 'window':
			if self._active_window != None:
				return XUtil.get_window_bounds( self._active_window,
					include_frame=True )
		else:
			if isinstance( mapping_type, int ) or \
					re.match( r'\d+', mapping_type ):
				display_index = int( mapping_type )
				display_id = XUtil.get_active_display_by_index( display_index )
				if display_id is None:
					eprint( "Could not find an active display at index %d."
						% display_index )
			else:
				display_id = mapping_type
			self._debug_print( "Using monitor %s output area." % display_id )
			return XUtil.get_display_bounds( display_id )
		return None

	def _map_device( self, device_id, output_area, device_area ):
		fitted_area = self.fit_bounds( output_area, device_area )
		if abs( fitted_area.aspect - output_area.aspect ) > 0.01:
			eprint( "Fitted aspect ratio does not match output." )
		if Wacom.set_output_area( device_id, output_area ) and \
				Wacom.set_area( device_id, fitted_area ):
			self._debug_print( "Mapped device %s: %s -> %s" % (device_id,
				fitted_area, output_area) )
			return True
		return False

	@staticmethod
	def list_devices( ):
		for dev_id, dev_name, dev_type in Wacom.get_devices( ):
			print( 'NAME: "%s", ID: %s, TYPE: %s' % (dev_name, dev_id, dev_type) )

	@staticmethod
	def fit_bounds( screen, device ):
		w = 0
		h = 0
		if screen.aspect >= device.aspect:
			w = device.width * min( 1.0, screen.aspect / device.aspect )
			h = device.height / screen.aspect * (w / device.height )
		else:
			h = device.height * min( 1.0, device.aspect / screen.aspect )
			w = device.width * screen.aspect / (device.width / h)
		w = min( device.width, math.ceil( w ) )
		h = min( device.height, math.ceil( h ) )
		dx = device.min_x + int( (device.width - w) / 2 )
		dy = device.min_y + int( (device.height - h) / 2 )
		return Bounds(
			max( device.min_x, min( device.max_x, dx ) ),
			max( device.min_y, min( device.max_y, dy ) ),
			max( device.min_x, min( device.max_x, dx + w ) ),
			max( device.min_y, min( device.max_y, dy + h ) ) )

if __name__ == "__main__":
	arg_parser = argparse.ArgumentParser( )
	arg_parser.add_argument( '--list', dest='list_devices',
		action='store_true', help='list devices' )
	arg_parser.add_argument( '--daemon',
		metavar='config-file', dest='daemon_config' )
	arg_parser.add_argument( '--update-rate', metavar='seconds',
		dest='update_rate', type=float, default=1.0 )
	arg_parser.add_argument( '--debug', dest='debug', action='store_true',
		default=False )
	args = arg_parser.parse_args( )

	if not args.list_devices and not args.daemon_config:
		arg_parser.print_help( )
		exit( 0 )

	if args.list_devices:
		Daemon.list_devices( )
	if args.daemon_config:
		Daemon( args.daemon_config, args.update_rate, debug=args.debug ).run( )
