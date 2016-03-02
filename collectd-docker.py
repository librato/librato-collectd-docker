#!/usr/bin/env python
# -*- coding: utf-8 -*-

__license__ = """\
    Copyright (c) 2015 Jason Dixon <jdixon@librato.com>

    Permission to use, copy, modify, and distribute this software for any
    purpose with or without fee is hereby granted, provided that the above
    copyright notice and this permission notice appear in all copies.

    THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
    WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
    MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
    ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
    WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
    ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
    OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.\
        """

import urllib2
import httplib
import json
import time
import datetime
import socket
import os
import sys
import re
from urlparse import urlsplit
from collections import Counter

# we should first try to grab stats via Docker's API socket
# (/var/run/docker.sock) and fallback to getting them from
# the sysfs cgroup directories
#
# https://docs.docker.com/reference/api/docker_remote_api_v1.18/#get-container-stats-based-on-resource-usage

try:
    HOSTNAME = os.environ['COLLECTD_HOSTNAME']
except:
    HOSTNAME = 'localhost'
try:
    INTERVAL = os.environ['COLLECTD_INTERVAL']
except:
    INTERVAL = 60
try:
    try:
        BASE_URI = os.environ['BASE_URI']
    except:
        try:
            BASE_URI = sys.argv[1]
        except:
            raise
except:
    BASE_URI = 'unix://var/run/docker.sock'
try:
    INTERVAL = os.environ['DEFAULT_SOCKET_TIMEOUT']
except:
    DEFAULT_SOCKET_TIMEOUT = 5
try:
    if os.environ['DEBUG']:
        DEBUG = True
except:
    DEBUG = False

METRICS_MAP = {
    # This dict represents a map of the original normalized metric path
    # into a flat namespace for the purpose of easier declaration.
    # In reality, we break this back out into the original dict structure
    # before retrieving the relevant attributes.

    # Total CPU time consumed.
    # Units: nanoseconds
    'cpu_stats.cpu_usage.total_usage': {
        'name': 'cpu-total'
    },
    # Time spent by tasks of the cgroup in kernel mode.
    # Units: nanoseconds
    'cpu_stats.cpu_usage.usage_in_kernelmode': {
        'name': 'cpu-kernel'
    },
    # Time spent by tasks of the cgroup in user mode.
    # Units: nanoseconds
    'cpu_stats.cpu_usage.usage_in_usermode': {
        'name': 'cpu-user'
    },
    # Number of periods when the container hit its throttling limit.
    'cpu_stats.throttling_data.throttled_periods': {
        'name': 'cpu-throttled_periods'
    },
    # Aggregate time the container was throttled for in nanoseconds.
    'cpu_stats.throttling_data.throttled_time': {
        'name': 'cpu-throttled_time'
    },
    'network.rx_bytes': {
        'name': 'network-rx_bytes'
    },
    'network.rx_dropped': {
        'name': 'network-rx_dropped'
    },
    'network.rx_errors': {
        'name': 'network-rx_errors'
    },
    'network.rx_packets': {
        'name': 'network-rx_packets'
    },
    'network.tx_bytes': {
        'name': 'network-tx_bytes'
    },
    'network.tx_dropped': {
        'name': 'network-tx_dropped'
    },
    'network.tx_errors': {
        'name': 'network-tx_errors'
    },
    'network.tx_packets': {
        'name': 'network-tx_packets'
    },
    'memory_stats.limit': {
        'name': 'memory-limit'
    },
    'memory_stats.max_usage': {
        'name': 'memory-max_usage'
    },
    'memory_stats.stats.active_anon': {
        'name': 'memory-active_anon'
    },
    'memory_stats.stats.active_file': {
        'name': 'memory-active_file'
    },
    'memory_stats.stats.cache': {
        'name': 'memory-cache'
    },
    'memory_stats.stats.hierarchical_memory_limit': {
        'name': 'memory-hierarchical_limit'
    },
    'memory_stats.stats.inactive_anon': {
        'name': 'memory-inactive_anon'
    },
    'memory_stats.stats.inactive_file': {
        'name': 'memory-inactive_file'
    },
    'memory_stats.stats.mapped_file': {
        'name': 'memory-mapped_file'
    },
    'memory_stats.stats.pgfault': {
        'name': 'memory-page_faults'
    },
    'memory_stats.stats.pgmajfault': {
        'name': 'memory-page_major_faults'
    },
    'memory_stats.stats.pgpgin': {
        'name': 'memory-paged_in'
    },
    'memory_stats.stats.pgpgout': {
        'name': 'memory-paged_out'
    },
    'memory_stats.stats.rss': {
        'name': 'memory-rss'
    },
    'memory_stats.stats.rss_huge': {
        'name': 'memory-rss_huge'
    },
    'blkio_stats.io_service_bytes_recursive.read': {
        'name': 'blkio-io_service_bytes_read'
    },
    'blkio_stats.io_service_bytes_recursive.write': {
        'name': 'blkio-io_service_bytes_write'
    },
    'blkio_stats.io_service_bytes_recursive.sync': {
        'name': 'blkio-io_service_bytes_sync'
    },
    'blkio_stats.io_service_bytes_recursive.async': {
        'name': 'blkio-io_service_bytes_async'
    },
    'blkio_stats.io_service_bytes_recursive.total': {
        'name': 'blkio-io_service_bytes_total'
    },
    'blkio_stats.io_serviced_recursive.read': {
        'name': 'blkio-io_serviced_read'
    },
    'blkio_stats.io_serviced_recursive.write': {
        'name': 'blkio-io_serviced_write'
    },
    'blkio_stats.io_serviced_recursive.sync': {
        'name': 'blkio-io_serviced_sync'
    },
    'blkio_stats.io_serviced_recursive.async': {
        'name': 'blkio-io_serviced_async'
    },
    'blkio_stats.io_serviced_recursive.total': {
        'name': 'blkio-io_serviced_total'
    },
    'info.images': {
        'name': 'images-total'
    },
    'info.containers': {
        'name': 'containers-total'
    },
    'info.containersrunning': {
        'name': 'containers-running'
    },
    'info.containersstopped': {
        'name': 'containers-stopped'
    },
    'info.containerspaused': {
        'name': 'containers-paused'
    },
}

# White and Blacklisting happens before flattening
WHITELIST_STATS = {
    'docker-librato.\w+.cpu_stats.*',
    'docker-librato.\w+.memory_stats.*',
    'docker-librato.\w+.network.*',
    'docker-librato.\w+.networks.*',
    'docker-librato.\w+.blkio_stats.*',
    'docker-librato.\w+.info.*',
}

BLACKLIST_STATS = {
    'docker-librato.\w+.memory_stats.stats.total_*',
    'docker-librato.\w+.cpu_stats.cpu_usage.percpu_usage.*',
}

class UnixHTTPConnection(httplib.HTTPConnection):

    socket_timeout = DEFAULT_SOCKET_TIMEOUT

    def __init__(self, unix_socket):
        self._unix_socket = unix_socket

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self._unix_socket)
        sock.settimeout(self.socket_timeout)
        self.sock = sock

    def __call__(self, *args, **kwargs):
        httplib.HTTPConnection.__init__(self, *args, **kwargs)
        return self

# monkeypatch UNIX socket support into urllib2
class UnixSocketHandler(urllib2.AbstractHTTPHandler):
    def unix_open(self, req):
        full_path = "%s%s" % urlsplit(req.get_full_url())[1:3]
        path = os.path.sep
        for part in full_path.split('/'):
            path = os.path.join(path, part)
            if not os.path.exists(path):
                break
            unix_socket = path
        # urllib2 needs an actual hostname or it complains
        url = req.get_full_url().replace(unix_socket, '/localhost')
        unix_req = urllib2.Request(url, req.get_data(), dict(req.header_items()))
        unix_req.timeout = req.timeout
        return self.do_open(UnixHTTPConnection(unix_socket), unix_req)

    unix_request = urllib2.AbstractHTTPHandler.do_request_

def log(str):
    ts = time.time()
    print "%s: %s" % (datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S.%f'), str)

def debug(str):
    if DEBUG == True:
        log(str)

def flatten(structure, key="", path="", flattened=None):
    if flattened is None:
        flattened = {}
    if type(structure) not in(dict, list):
        flattened[((path + ".") if path else "") + key] = structure
    elif isinstance(structure, list):
        for i, item in enumerate(structure):
            flatten(item, "%d" % i, path + "." + key, flattened)
    else:
        for new_key, value in structure.items():
            flatten(value, new_key, path + "." + key, flattened)
    return flattened

def api_version():
    debug('getting API version')
    try:
        uri = "%s/version" % BASE_URI
        req = urllib2.Request(uri)
        opener = urllib2.build_opener(UnixSocketHandler())
        request = opener.open(req)
        result = json.loads(request.readline())
        debug('done getting API version')
        return result['ApiVersion']
    except:
        log('unable to get API version')
        sys.exit(1)

def info():
    debug('getting info')
    try:
        uri = "%s/info" % BASE_URI
        req = urllib2.Request(uri)
        opener = urllib2.build_opener(UnixSocketHandler())
        request = opener.open(req)
        result = json.loads(request.readline())
        debug('done getting info')
        return result
    except:
        log('unable to get info')
        sys.exit(1)

def find_containers():
    debug('getting container ids')
    try:
        uri = "%s/containers/json" % BASE_URI
        req = urllib2.Request(uri)
        opener = urllib2.build_opener(UnixSocketHandler())
        request = opener.open(req)
        result = json.loads(request.read())
        debug('done getting container ids')
        return [c['Id'] for c in result]
    except urllib2.URLError as e:
        log('unable to get container ids')
        if re.match('^.*\[Errno 13\].*$', str(e)):
            log('insufficient permissions to read socket')
        sys.exit(1)

def gather_stats(container_id):
    debug('getting container stats')
    try:
        uri = "%s/containers/%s/stats" % (BASE_URI, container_id)
        req = urllib2.Request(uri)
        opener = urllib2.build_opener(UnixSocketHandler())
        request = opener.open(req)
        result = json.loads(request.readline())
        debug('done getting container stats')
        return result
    except:
        log('unable to get container stats')
        sys.exit(1)

def build_info_stats():
    info_stats = {}
    stats = {}

    for key, val in info().iteritems():
        if key in ['Images', 'Containers', 'ContainersRunning', 'ContainersStopped', 'ContainersPaused']:
          info_stats[key.lower()] = val

    stats['info'] = info_stats

    submit_values(stats, 'global')

def build_network_stats_for(stats):
    network_stats = {
        'rx_bytes':   0,
        'rx_dropped': 0,
        'rx_errors':  0,
        'rx_packets': 0,
        'tx_bytes':   0,
        'tx_dropped': 0,
        'tx_errors':  0,
        'tx_packets': 0,
    }

    aggregated_interface_stats = {}

    for interface, interface_stats in stats['networks'].iteritems():
        aggregated_interface_stats = dict(Counter(aggregated_interface_stats) + Counter(interface_stats))
        network_stats.update(aggregated_interface_stats)

    stats['networks'] = {}
    stats['network'] = {}
    stats['network'] = network_stats

def build_blkio_stats_for(stats):
    blkio_stats = {}
    for key, val in stats['blkio_stats'].iteritems():
        tmp = {}
        for op in val:
            tmp[op.get('op').lower()] = op.get('value')
        blkio_stats[key] = tmp
    stats['blkio_stats'] = {}
    stats['blkio_stats'] = blkio_stats

def format_stats(stats):
    build_blkio_stats_for(stats)
    if api_version() >= '1.21':
        build_network_stats_for(stats)

def compile_regex(list):
    regexes = []
    for l in list:
        regexes.append(re.compile(l))
    return regexes

def prettify_name(metric):
    prefix = '-'.join(metric.split('.')[0:2])
    suffix = '.'.join(metric.split('.')[2:])

    try:
        # strip off the docker.<id> prefix and look for our metric
        if METRICS_MAP[suffix]['name']:
            return "%s.%s" % (prefix, METRICS_MAP[suffix]['name'])
    except:
        return "%s.%s" % (prefix, suffix)

def collectd_output(metric, value):
    fmt_metric = metric.replace('.', '/')
    return "PUTVAL \"%s/%s\" interval=%s N:%s" % (HOSTNAME, fmt_metric, INTERVAL, value)

def submit_values(stats, container_id=''):
    try:
        whitelist = compile_regex(WHITELIST_STATS)
        blacklist = compile_regex(BLACKLIST_STATS)
        for i in flatten(stats, key=container_id, path='docker-librato').items():
            blacklisted = False
            for r in blacklist:
                if r.match(i[0].encode('ascii')):
                    blacklisted = True
                    break
            if blacklisted == False:
                for r in whitelist:
                    metric = i[0].encode('ascii')
                    if r.match(metric):
                        print collectd_output(prettify_name(metric), i[1])
                        break
    except:
        sys.exit(1)

while True:
    try:
        if api_version() >= '1.22':
            build_info_stats()
        for id in find_containers():
            stats = gather_stats(id)
            format_stats(stats)
            submit_values(stats, id[0:12])
    except KeyboardInterrupt:
        sys.exit(1)
    time.sleep(float(INTERVAL))
