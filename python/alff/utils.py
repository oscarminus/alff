#!/usr/bin/python
#
# Maximilian Wilhelm <max@rfc2324.org>
#  --  Sat 04 Jan 2014 01:37:53 AM CET
#

# XXX Python 2.x style, needs update for Python 3.x
import imp
import inspect
# If we're on Python 3.3 we might want to use module "ipaddress" instead.
import ipaddr
import os

from alff.errors import *


def load_module_from_file (module_name, path):
	try:
		module = imp.load_source (module_name, path)
	except ImportError as i:
		raise AlffError ("Failed to load module from '%s': %s" % (path, i))
	except Exception as e:
		raise AlffError ("Unknowd error while loading module from '%s': %s" % (path, e))

	return module


def get_class (module, class_name):
	# Figure out module name
	try:
		module_file = module.__file__.replace ('.pyc', '.py')
	except AttributeError as a:
		raise AlffError ("Module seems to be broken or invalid.")

	# Get class
	try:
		# The attribue named <class_name> from module
		module_class = getattr (module, class_name)

		# Is it a class?
		if not inspect.isclass (module_class):
			raise AlffError ("Attribute '%s' found in module '%s' (%s) is not a class." % (class_name, module.__name__, module_file))
	except AttributeError as e:
		raise AlffError ("No class '%s' found in module '%s' (%s)." % (class_name, module.__name__, module_file))

	return module_class


def join_path (*components):
	return os.path.normpath (os.sep.join (components))


def ip_version (ip):
	if '/' in ip:
		obj = ipaddr.IPNetwork (ip)
	else:
		obj = ipaddr.IPAddress (ip)

	return obj.version