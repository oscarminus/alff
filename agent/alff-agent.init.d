#!/bin/sh
#
# /etc/init.d/alff
#
# Alff-Agent start/stop script for init
#
# Maximilian Wilhelm <max@rfc2324.org>
#  -- Sat, 17 Jun 2006 23:19:08 +0200
#

# Check if run interactivly or from init
function interactive_run() { #{{{
	if [ -x /bin/readlink ]; then
		tty=`readlink --silent /proc/self/fd/0`
		if [ -z "${tty}" -o "${tty}" == "/dev/console" ]; then
			return 1
		fi
	fi
} #}}}

# Flush all chains
function flush_all() { #{{{
	# Reset filter chains #{{{
	iptables -t filter -P INPUT ACCEPT
	iptables -t filter -P OUTPUT ACCEPT
	iptables -t filter -P FORWARD ACCEPT
	iptables -t filter -F
	iptables -t filter -X
	iptables -t filter -Z
	#}}}

	# Reset nat chains #{{{
	iptables -t nat -P PREROUTING ACCEPT
	iptables -t nat -P POSTROUTING ACCEPT
	iptables -t nat -P OUTPUT ACCEPT
	iptables -t nat -F
	iptables -t nat -X
	iptables -t nat -Z
	#}}}

	# Reset mangle chains #{{{
	iptables -t mangle -F
	iptables -t mangle -X
	iptables -t mangle -Z
	#}}}
}
#}}}

# Load current rules via alff-cat
function load_rules() { #{{{
	# First check for an existing DELETE_ME_FILE, to be aware of a reboot while
	# alff-cat was running. Maybe something went wrong.
	if [ -f "${DELETE_ME_FILE}" ]; then
		echo "It seems that this machine was rebooted while loading new rules." >&2
		echo "Trying to load the old rules to avoid trouble..." >&2
		if [ -f "${OLD_RULES_FILE}" ]; then
			iptables-restore < "${OLD_RULES_FILE}"
		fi

	# OK, everything looks good, just load the ruleset if there is any
	elif [ -f "${CURRENT_RULES_FILE}" ]; then
			sh "${CURRENT_RULES_FILE}"

	# No rules :-(
	else
		echo "Error: No ruleset found."
		exit 1
	fi
}
#}}}

# Check the configuration
check_config() { #{{{
	if [ -z "${RULES_DIR}" ]; then
		return 1
	fi
} #}}}

if [ -f /etc/alff/alff-agent.conf ]; then
	. /etc/alff/alff-agent.conf
fi


NAME="alff-agent"
DATE="`date +%Y-%m-%d_%H%M`"


case "${1}" in
	# Startup alff
	start)
		echo -n "Starting Alff agent: "
		LOGFILE="/var/log/${NAME}.startup.${DATE}"

		if ! check_config; then
			echo "No configuration provided!"
			exit 1
		fi

		if interactive_run && [ "${ALFF_INIT_VERBOSE}" == 'true' ]; then
			load_rules 2>&1 | tee "${LOGFILE}" && echo "Rules successfully loaded." || echo "FAILED!"
		else
			load_rules 2>&1 > "${LOGFILE}" && echo "Rules successfully loaded." || echo "FAILED!"
		fi

		if [ "${MAIL_LOG}" ]; then
			mail -s "Alff agent startup log" ${MAIL_LOG} < "${LOGFILE}"
		fi
		;;

	# Stop the whole firewall system
	stop)
		echo -n "Stopping firewall: "
		LOGFILE="/var/log/${NAME}.shutdown.${DATE}"

		if interactive_run; then
			flush_all 2>&1 | tee "${LOGFILE}" && echo "done." || echo "FAILED!"
		else
			flush_all 2>&1 > "${LOGFILE}" && echo "done." || echo "FAILED!"
		fi

		if [ "${MAIL_LOG}" ]; then
			mail -s "Alff shutdown!" ${MAIL_LOG} < "${LOGFILE}"
		fi
		;;

	# Restart the whole firewall system
	restart)
		$0 stop
		$0 start
		;;

	# Reload services definitions and rules
	reload)
		$0 start
		;;
	*)
		echo "Usage: $0 { start | stop | reload | restart }" >&2
		exit 1
		;;
esac

# vim:foldmethod=marker:ft=sh