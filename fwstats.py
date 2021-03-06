#! /usr/bin/python

################################################################################
# flexiWAN SD-WAN software - flexiEdge, flexiManage.
# For more information go to https://flexiwan.com
#
# Copyright (C) 2019  flexiWAN Ltd.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
################################################################################

# Handle device statistics
import fwutils
import time
import loadsimulator

from fwtunnel_stats import tunnel_stats_get

# Globals
# Keep updates up to 1 hour ago
UPDATE_LIST_MAX_SIZE = 120

# Keeps the list of last updates
updates_list = []

# Keeps the VPP pids
vpp_pid = ''

# Keeps last stats
stats = {'ok':0, 'running':False, 'last':{}, 'bytes':{}, 'tunnel_stats':{}, 'period':0}

def update_stats():
    """Update statistics dictionary using values retrieved from VPP interfaces.

    :returns: None.
    """
    global stats
    global vpp_pid

    # If vpp is not running or has crashed (at least one of its process
    # IDs has changed), reset the statistics and update the vpp pids list
    current_vpp_pid = fwutils.vpp_pid()
    if not current_vpp_pid or current_vpp_pid != vpp_pid:
        reset_stats()
        vpp_pid = current_vpp_pid

    new_stats = fwutils.get_vpp_if_count()
    if new_stats['ok'] == 1:
        prev_stats = dict(stats)  # copy of prev stats
        stats['time'] = time.time()
        stats['last'] = new_stats['message']
        stats['ok'] = 1
        # Update info if previous stats valid
        if prev_stats['ok'] == 1:
            if_bytes = {}
            for intf, counts in stats['last'].items():
                prev_stats_if = prev_stats['last'].get(intf, None)
                if prev_stats_if != None:
                    rx_bytes = 1.0 * (counts['rx_bytes'] - prev_stats_if['rx_bytes'])
                    rx_pkts  = 1.0 * (counts['rx_pkts'] - prev_stats_if['rx_pkts'])
                    tx_bytes = 1.0 * (counts['tx_bytes'] - prev_stats_if['tx_bytes'])
                    tx_pkts  = 1.0 * (counts['tx_pkts'] - prev_stats_if['tx_pkts'])
                    if_bytes[intf] = {
                            'rx_bytes': rx_bytes, 
                            'rx_pkts': rx_pkts,
                            'tx_bytes': tx_bytes, 
                            'tx_pkts': tx_pkts
                        }

            stats['bytes'] = if_bytes
            stats['tunnel_stats'] = tunnel_stats_get()
            stats['period'] = stats['time'] - prev_stats['time']
            stats['running'] = True if fwutils.vpp_does_run() else False
    else:
        stats['ok'] = 0

    # Add the update to the list of updates. If the list is full,
    # remove the oldest update before pushing the new one
    if len(updates_list) is UPDATE_LIST_MAX_SIZE:
        updates_list.pop(0)
    
    updates_list.append({
            'ok': stats['ok'], 
            'running': stats['running'], 
            'stats': stats['bytes'], 
            'period': stats['period'],
            'tunnel_stats': stats['tunnel_stats'],
            'utc': time.time()
        })

def get_stats():
    """Return a new statistics dictionary.

    :returns: Statistics dictionary.
    """
    res_update_list = list(updates_list)
    del updates_list[:]

    # If the list of updates is empty, append a dummy update to 
    # set the most up-to-date status of the router. If not, update
    # the last element in the list with the current status of the router
    if loadsimulator.g.enabled():
        status = True
        state = 'running'
        reason = ''
    else:
        status = True if fwutils.vpp_does_run() else False
        (state, reason) = fwutils.get_router_state()
    if not res_update_list:
        res_update_list.append({
            'ok': stats['ok'],
            'running': status,
            'state': state,
            'stateReason': reason,
            'stats': {},
            'tunnel_stats': {},
            'period': 0,
            'utc': time.time()
        })
    else:
        res_update_list[-1]['running'] = status
        res_update_list[-1]['state'] = state
        res_update_list[-1]['stateReason'] = reason

    return {'message': res_update_list, 'ok': 1}
    
def update_state(new_state):
    """Update router state field.

    :param new_state:         New state.

    :returns: None.
    """
    stats['running'] = new_state

def reset_stats():
    """Reset statistics.

    :returns: None.
    """
    global stats
    stats = {'running': False, 'ok':0, 'last':{}, 'bytes':{}, 'tunnel_stats':{}, 'period':0}