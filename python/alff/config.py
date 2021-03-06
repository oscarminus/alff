#!/usr/bin/python3
#
#  A Linux Firewall Framework
#
#  Copyright (C) 2014 Maximilian Wilhelm <max@rfc2324.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Maximilian Wilhelm <max@rfc2324.org>
#  --  Sat 04 Jan 2014 01:17:22 AM CET
#

import os.path
import re
import sys
from xml.etree import ElementTree

from alff.errors import *
from alff.utils import *

DEFAULT_CONFIG_DIR = "/etc/alff/default"
CONFIG_DIRS = ( 'plugin.d', 'rules.d', 'services.d' )
CONFIG_FILE_NAME = "alff.conf"

CACHE_BASE_DIR = "/var/cache/alff"

class Config (object):

	def __init__ (self, config_dir = DEFAULT_CONFIG_DIR):
		# Remeber which config dir was used for the current run
		self.config_dir = config_dir

		# We have to cache the generated rules for pushing them later.
		# Therefore we use a separate rules directory for every config directory and site
		# we were called with to maintain the principle of least surprise for the user,
		# who may even use the same site and firewall names in the different configurations.
		self.rules_base_dir = "%s/%s/rules/" % (CACHE_BASE_DIR, config_dir.replace ("/", "_"))

		self._check_config_dir (config_dir)

		self.config = Parser (self.config_file).get_config ()

		self._get_security_classes ()



	def _check_config_dir (self, dir):
		if not os.path.isdir (dir):
			raise ConfigError ("Directory '%s' does not exist." % dir)

		self.config_dir = dir

		# Check subdirs
		for subdir in CONFIG_DIRS:
			if not os.path.isdir (os.path.join (dir, subdir)):
				raise ConfigError ("Directory '%s' missing in '%s'" % (subdir, dir))

		self.config_file = os.path.join (dir, CONFIG_FILE_NAME)

		if not os.path.isfile (self.config_file):
			raise ConfigError ("No '%s' found in '%s'." % (CONFIG_FILE_NAME, dir))

	def _get_security_classes (self):
		all_sec_classes = {
			'filtered' : 1,
			'trusted' : 1,
		}

		for network_id in self.config['networks'].keys ():
			network = self.config['networks'][network_id]

			for sec_class in network['security_class']:
				all_sec_classes[sec_class] = 1

			for magic_class in ('filtered', 'trusted'):
				if magic_class in network and re.search ('yes|true', network[magic_class], re.I):
					network['security_class'].append (magic_class)

		self.security_classes = all_sec_classes.keys ()


	########################################
	# global stuff
	########################################

	def get_config_dir (self):
		return self.config_dir

	def get_rules_base_dir (self):
		return self.rules_base_dir

	def get_option (self, option, default = None):
		if option in self.config['options']:
			return self.config['options'][option]

		if default != None:
			return default

		raise ConfigError ("Unknown option '%s'" % option)


	""" Get a list of all DHCP servers found in the configuration file """
	def get_dhcp_servers (self):
		return self.config['options']['dhcp_server']


	def get_security_classes (self):
		return self.security_classes

	def is_valid_security_class (self, sec_class):
		return sec_class in self.security_classes


	########################################
	# site handling
	########################################

	def get_sites (self):
		return self.config['sites'].keys ()

	def is_valid_site (self, site_id):
		return site_id in self.config['sites']

	def get_default_interface (self, site):
		if not self.is_valid_site (site):
			raise RuntimeError ("Invalid site id '%s'." % site)

		def_int = self.config['sites'][site]['interface_map'].get ('default')

		return def_int['interface'] if def_int else None


	########################################
	# network handling
	########################################

	def get_vlans (self):
		AlffDeprecated ("get_vlans()", "get_networks()")
		return self.get_networks ()
	def get_networks (self):
		return self.config['networks'].keys ()


	def is_valid_vlan (self, vlan):
		AlffDeprecated ("is_valid_vlan()", "is_valid_network()")
		return self.is_valid_network (vlan)
	def is_valid_network (self, network):
		return network in self.config['networks']


	def get_vlans_of_security_class (self, sec_class):
		AlffDeprecated ("get_vlans_of_security_class()", "get_networks_of_security_class()")
		return self.get_networks_of_security_class (sec_class)
	def get_networks_of_security_class (self, sec_class):
		return [network for network in self.config['networks'].keys () if sec_class in self.config['networks'][network]['security_class']]


	def get_filtered_vlans (self):
		AlffDeprecated ("get_filtered_vlans()", "get_filtered_networks()")
		return self.get_filtered_networks ()
	def get_filtered_networks (self):
		return self.get_networks_of_security_class ("filtered")


	def get_trusted_vlans (self):
		AlffDeprecated ("get_trusted_vlans()", "get_trusted_networks()")
		return self.get_trusted_networks ()
	def get_trusted_networks (self):
		return self.get_networks_of_security_class ("trusted")


	def is_filtered_vlan (self, vlan):
		AlffDeprecated ("is_filtered_vlan()", "is_filtered_network()")
		return self.is_filtered_network (vlan)
	def is_filtered_network (self, network):
		if not self.is_valid_network (network):
			raise RuntimeError ("Invalid network id '%s'." % network)

		return "filtered" in self.config['networks'][network]['security_class']


	def get_vlan_interface (self, vlan, site, use_default = False):
		AlffDeprecated ("get_vlan_interface()", "get_network_interface()")
		return self.get_network_interface (vlan, site, use_default)
	def get_network_interface (self, network, site, use_default = False):
		if not self.is_valid_network (network):
			raise RuntimeError ("Invalid network id '%s'." % network)

		if not self.is_valid_site (site):
			raise RuntimeError ("Invalid site id '%s'." % site)

		iface = self.config['sites'][site]['interface_map'].get (network)

		if iface is None:
			if use_default:
				return self.get_default_interface (site)
			else:
				return None

		return iface['interface']


	def get_vlan_networks (self, vlan):
		AlffDeprecated ("get_vlan_networks()", "get_network_prefixes()")
		return self.get_network_prefixes (vlan)
	def get_network_prefixes (self, network):
		if not self.is_valid_network (network):
			raise RuntimeError ("Invalid network id '%s'." % network)

		return self.config['networks'][network]['prefix']

	def get_security_classes_of_vlan (self, vlan):
		AlffDeprecated ("get_security_classes_of_vlan()", "get_security_classes_of_network()")
		return self.get_security_classes_of_network (vlan)
	def get_security_classes_of_network (self, network):
		if not self.is_valid_network (network):
			raise RuntimeError ("Invalid network id '%s'." % network)

		return self.config['networks'][network]['security_class']



	########################################
	# Machine handling
	########################################

	def get_machine_ids (self, site):
		if not self.is_valid_site (site):
			raise RuntimeError ("Invalid site id '%s'!" % site)

		return self.config['sites'][site]['machines'].keys ()


	def is_valid_machine_id (self, machine, site):
		if not self.is_valid_site (site):
			raise RuntimeError ("Invalid site id '%s'!" % site)

		return machine in self.config['sites'][site]['machines']


	def get_machine_hostname (self, machine, site):
		if not self.is_valid_machine_id (machine, site):
			raise RuntimeError ("Invalid machine id '%s' in site '%s'!" %  (machine, site))

		return self.config['sites'][site]['machines'][machine].get ('hostname')


	def get_machine_ip (self, machine, site):
		if not self.is_valid_machine_id (machine, site):
			raise RuntimeError ("Invalid machine id '%s' in site '%s'!" %  (machine, site))

		return self.config['sites'][site]['machines'][machine].get ('ip')


	def get_machine_ip6 (self, machine, site):
		if not self.is_valid_machine_id (machine, site):
			raise RuntimeError ("Invalid machine id '%s' in site '%s'!" %  (machine, site))

		return self.config['sites'][site]['machines'][machine].get ('ip6')


	########################################
	# Plugin configuration
	########################################

	def get_plugin_option (self, plugin, option, default = None):
		if plugin not in self.config['plugins']:
			return None

		return self.config['plugins'][plugin].get (option, default)




################################################################################
#                          XML config file parser                              #
################################################################################

class Parser (object):
	default_options = {
		'fw_type' : 'router',
		'allow_icmp' : 'all',
		'allow_traceroute_udp' : False,
		'support_ipv6_nat': False,
		'suppress_empty_chains' : False,
		'suppress_unreferenced_chains' : False,
		'dhcp_server' : [],
	}

	multi_opt = ('dhcp_server')

	def __init__ (self, config_file):
		try:
			tree = ElementTree.parse (config_file)
			self.root = tree.getroot ()
		except Exception as e:
			raise ConfigError (e)


	def get_config (self):
		config = {
			'options'  : self._get_options (),
			'plugins'  : self._get_plugin_options (),
			'networks' : self._get_networks (),
			'sites'    : self._get_sites (),
		}

		return config


	""" Parse global options """
	def _get_options (self):
		# Get default options and get out if there is no options section in the config
		options = Parser.default_options

		opts_elem = self.root.find ('options')
		if opts_elem is not None:
			for opt_elem in opts_elem:
				if opt_elem.tag in Parser.multi_opt:
					options[opt_elem.tag].append (opt_elem.text.strip ())
				else:
					# If we have a default value and it's a boolean, except value to be boolean
					if opt_elem.tag in options and type (options[opt_elem.tag]) == bool:
						options[opt_elem.tag] = self.__get_true_false (opt_elem.text)
					else:
						options[opt_elem.tag] = opt_elem.text.strip ()
		return options


	""" Parse plugin options """
	def _get_plugin_options (self):
		plugins = {}

		plugins_tree = self.root.find ('plugins')
		if plugins_tree is not None:
			for p_elem in plugins_tree:
				plugins[p_elem.tag] = {}
				self.__get_text_elements (p_elem, plugins[p_elem.tag])

		return plugins


	""" Parse network list """
	def _get_networks (self):
		networks = {}

		xml_networks = self.root.findall ('network')

		vlans = self.root.findall ('vlan')
		if len (vlans):
			xml_networks.extend (vlans)
			AlffDeprecated ("Config tag <vlan>", "<network>")

		for network in xml_networks:
			network_dict = {
				'network' : [],
				'prefix' : [],
				'security_class' : [],
			}

			# Fetch network elements
			for elem in list (network):
				if elem.tag in ('network', 'prefix', 'security_class'):
					network_dict[elem.tag].append (elem.text.strip ())
				else:
					network_dict[elem.tag] = elem.text.strip ()

			if len (network_dict['network']):
				AlffDeprecated ("Old <vlan> element <network>", "<prefix>")
				network_dict['prefix'].extend (network_dict['network'])

			del network_dict['network']

			# Fetch network attributes (if any)
			self.__get_attributes (network, network_dict)

			if 'id' not in network_dict:
				raise ConfigError ("No ID found for network!")

			networks[network_dict['id']] = network_dict

		return networks


	""" Parse sites """
	def _get_sites (self):
		sites = {}

		sites_tree = self.root.find ('sites')
		if sites_tree is None:
			raise ConfigError ("No sites found in configuration!")

		for site in list (sites_tree):
			site_dict = {
				'machines' : {},
				'interface_map' : {},
			}

			# Fetch attributes (if any)
			self.__get_attributes (site, site_dict)

			# Get id (if not given as attribute)
			id_elem = site.find ('id')
			if id_elem is not None:
				site_dict['id'] = id_elem.text.strip ()

			if 'id' not in site_dict:
				raise ConfigError ("Site with no 'id' found!")

			site_id = site_dict['id']

			# Get machine information
			machines = site.findall ("machines/machine")
			if len (machines) == 0:
				raise ConfigError ("No machines defined in site %s!" % site_id)

			for machine in machines:
				machine_dict = {}

				self.__get_attributes (machine, machine_dict)
				self.__get_text_elements (machine, machine_dict)

				if 'id' not in machine_dict:
					raise ConfigError ("Machine without 'id' found in site '%s'!" % site_id)

				machine_id = machine_dict['id']

				if machine_id in machines:
					raise ConfigError ("Duplicate machine id '%s' found in site '%s'" % (machine_id, site_id))

				site_dict['machines'][machine_id] = machine_dict

			# Get interface_map
			int_map = site_dict['interface_map']
			networks = site.findall ("interface_map/network")
			# Compatibility glue
			vlan_networks = site.findall ("interface_map/vlan")
			if len (vlan_networks):
				networks.extend (vlan_networks)
				AlffDeprecated ("<vlan>", "<network>")

			if len (networks) == 0:
				raise ConfigError ("Empty interface map for site %s!" % site_id)

			for network in networks:
				network_dict = {}

				self.__get_attributes (network, network_dict)
				self.__get_text_elements (network, network_dict)

				if 'id' not in network_dict:
					raise ConfigError ("Network without 'id' found in site '%s'!" % site_id)

				network_id = network_dict['id']

				if 'interface' not in network_dict:
					raise ConfigError ("No 'interface' specified for network '%s' at site '%s'!" % (network_id, site_id))

				if network_id in int_map:
					raise ConfigError ("Duplicate network id '%s' found in interface map for site '%s'!" (network_id, site_id))

				int_map[network_id] = network_dict

				# Default interace found?
				if 'default' in network_dict:
					if 'default' in int_map:
						raise ConfigError ("Duplicate default interface found: '%s' vs. '%s'!" % (int_map['default']['interface'], network_dict['interface']))

					int_map['default'] = {
						'id' : 'default',
						'interface' : network_dict['interface'],
						'orig_network' : network_dict['id'],
					}

			# Store this site
			sites[site_dict['id']] = site_dict

		return sites


	def __get_attributes (self, elem, dst_dict):
		for attr in elem.attrib.keys ():
			dst_dict[attr] = elem.attrib[attr].strip ()

	def __get_text_elements (self, elem, dst_dict):
		for subelem in list (elem):
			if subelem.text is not None:
				# Try to convert boolean text value into real boolean (if any)
				dst_dict[subelem.tag] = self.__get_true_false (subelem.text, noerror = True)
			else:
				# If there is no text value we assume that it's a boolean
				dst_dict[subelem.tag] = True

	def __get_true_false (self, string, noerror = False):
		match = string.strip ()

		if re.search ("^(yes|true)$", match, re.I):
			return True
		elif re.search ("^(no|false)$", match, re.I):
			return False

		if noerror:
			return match

		raise ConfigError ("Expected boolean value ('yes', 'no'), got '%s'" % string)
