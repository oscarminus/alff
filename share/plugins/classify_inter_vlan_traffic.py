#!/usr/bin/python3
#
#  Linux Firewall Framework
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
#  --  Mon 14 Apr 2014 07:55:55 PM CEST
#

import os.path
import re

from alff.errors import *
from alff.plugin import BasePlugin
from alff.utils  import *

CONFIG_DIR = "rules.d"
plugin_name = "classifyInterVlanTraffic"


class Plugin (BasePlugin):
	def __init__ (self, config, log):
		BasePlugin.__init__ (self, config, log)

		self.rules_dir = "%s/%s" % (self.config.get_config_dir (), CONFIG_DIR)

		# Get global network list
		self.networks = sorted (self.config.get_networks ())

		#
		# Plugin configuration options

		# The target to put into totally unconfigured chains
		self.default_chain_target = self.config.get_plugin_option (plugin_name, "default_chain_target", "REJECT")
		# Should we silenty ignore chains without rules?
		self.remove_empty_chains  = self.config.get_plugin_option (plugin_name, "remove_empty_chains",  True)
		# Should we create chains for traffic from network x into network x?
		self.force_x_to_x_chains  = self.config.get_plugin_option (plugin_name, "force_x_to_x_chains",  False)


	def run (self, ruleset, site):
		for src_network in self.networks:
			for dst_network in self.networks:
				# Skip x <-> x rules (if not forced otherwise)
				if src_network == dst_network and self.force_x_to_x_chains != 'yes':
					self.log.debug( "Skipping %s_to_%s" % (src_network, dst_network) )
					continue

				# If both networks are *not* behind this firewall, there is nothing we could do for them...
				if not self.config.is_filtered_network (src_network) and not self.config.is_filtered_network (dst_network):
					continue

				# Skip this traversal if there are no rule files for it at all.
				# Beware: There might be empty rule files or rule files only containig rules
				# for on protocol. We check this later and remove any created empty chain.
				if self.remove_empty_chains and not self._has_rule_files (src_network, dst_network):
					continue

				# OK, just do it[tm]
				self._classify_traffic_from_to (src_network, dst_network, ruleset, site)


	def _classify_traffic_from_to (self, src_network, dst_network, ruleset, site):
		""" Create <src_network>_to_<dst_network> chain and rules to direct traffic from any prefixes """
		""" of src_network to any prefixes of dst_network into that chain in FORWAR chain. """

		chain = "%s_to_%s" % (src_network, dst_network)

		# Try to gexplicitly et interface names for network for this site
		src_int = self.config.get_network_interface (src_network, site, use_default = False)
		dst_int = self.config.get_network_interface (dst_network, site, use_default = False)

		# If there's no interface to any network at this site, there traversion isn't relevant here.
		if not src_int and not dst_int:
			return

		# If we're still here, we got a least one interface for this site, so ask again,
		# now accepting the default interface for this site, as one of the networks may not
		# be local while the other one is.
		src_int = self.config.get_network_interface (src_network, site, use_default = True)
		dst_int = self.config.get_network_interface (dst_network, site, use_default = True)

		# Get IP prefixes of networks
		src_prefixes = self.config.get_network_prefixes (src_network)
		dst_prefixes = self.config.get_network_prefixes (dst_network)

		# Create the chains for this network transition
		ruleset.create_chain ("4", chain, "filter")
		ruleset.create_chain ("6", chain, "filter")

		# Chains created, so let's load any rules for it so when can see if there are any
		# for both protocols.
		self._load_chain_rules (src_network, dst_network, ruleset)
		rules = {}

		for protocol in (4, 6):
			rules[protocol] = ruleset.chain_has_rules (protocol, chain)
			if not rules[protocol] and self.remove_empty_chains:
				ruleset.remove_chain (protocol, chain)

		# Generate classification rules
		for src_net in src_prefixes:
			# Get src prefix version (v4/v6), strip possible leading ! (negation) before.
			src_net_version = ip_version (src_net.replace ("!", "").strip ())

			for dst_net in dst_prefixes:
				# Ignore this combinaton IF one prefix is v4 and the other is v6
				if src_net_version != ip_version (dst_net.replace ("!", "").strip ()):
					continue

				# If there are no rules for this ip protocol and remove_empty_chains
				# is set, we already remove this chain, so don't create jump rule for
				# this traversal.
				if not rules[src_net_version] and self.remove_empty_chains:
					continue

				rule = "iptables" if src_net_version == 4 else "ip6tables"
				rule += " -A FORWARD -i %s -s %s -o %s -d %s -j %s" % (src_int, src_net, dst_int, dst_net, chain)

				# Reoder parameter and negation, so ip(6)tables is happy
				rule = rule.replace ("-s !", "! -s")
				rule = rule.replace ("-d !", "! -d")

				ruleset.add_rule (rule)



	def _load_chain_rules (self, src_network, dst_network, ruleset):
		""" Load rules for <src_network>_to_<dst_network> chain from <src_network>_to_default, """
		""" default_to_<dst_network> and <<src_network>_to_<dst_network> config files OR create """
		""" rule jumping to self.default_chain_target instead IF 'remove_empty_chains' """
		""" is set. Otherwise remove any empty chain. """

		chain = "%s_to_%s" % (src_network, dst_network)

		# Load default rules from the following files in this order
		default_files = ("%s_to_default" % src_network, "default_to_%s" % dst_network)

		# Load any default files, if any
		try:
			for default_file in default_files:
				path = join_path (self.rules_dir, default_file)
				if not os.path.isfile (path):
					continue

				with open (path, "r") as fh:
					# Read rules manually here, as we have to apply some substitutians
					for line in fh.readlines ():
						# Ignore empty lines and comments starting with #
						if re.match ("^\s*$\|^\s*#", line):
							continue

						line = re.sub ("default_", "%s_" % src_network, line)
						line = re.sub ("_default", "_%s" % dst_network, line)
						ruleset.add_rule (line)

					self.log.debug ("Sucessfully loaded default rules '%s' for chain '%s'" % (default_file, chain))
		except IOError as i:
			raise RulesetError ("Failed to load default rules from '%s' for %s: %s" % (path, chain, i))

		# Load explicit chain configuration
		chain_rules_path = join_path (self.rules_dir, chain)
		if os.path.isfile (chain_rules_path):
			with open (chain_rules_path, "r") as fh:
				ruleset.add_rules_from_file (chain_rules_path)

			self.log.debug ("Sucessfully read rules from chain file '%s'" % chain)

		# Did we load rules for both the v4 and the v6 chain?
		for protocol in (4, 6):
			if not ruleset.chain_has_rules (protocol, chain) and not self.remove_empty_chains:
				self.log.debug ("""No rules found for chain %s (v%s) and 'remove_empty_chains'"
				"not set, using default_chain_target.""" % (chain, protocol))
				cmd = "iptables" if protocol == 4 else "ip6tables"
				ruleset.add_rule ("%s -A %s -j %s" % (cmd, chain, self.default_chain_target))


	def _has_rule_files (self, src_network, dst_network):
		""" Check if there is at least on file containing rules for the transition """
		""" from src_network to dst_network. """

		chain = "%s_to_%s" % (src_network, dst_network)

		files = ("%s_to_default" % src_network, "default_to_%s" % dst_network, chain)

		for f in files:
			if os.path.isfile (join_path (self.rules_dir, f)):
				# Ok found one
				return True

		# Nothing there
		return False
