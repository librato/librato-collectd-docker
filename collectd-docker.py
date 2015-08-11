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
import requests
import json
import time
import datetime
import os
import sys
import re

# we should first try to grab stats via Docker's API socket
# (/var/run/docker.sock) and fallback to getting them from
# the sysfs cgroup directories
# 
# https://docs.docker.com/reference/api/docker_remote_api_v1.18/#get-container-stats-based-on-resource-usage
# 
# There are a couple blkio stats that may be useful but they're
# only exposed by sysfs, not the Docker API
# 
# blkio.throttle.io_service_bytes
# blkio.throttle.io_serviced
# 
# https://www.kernel.org/doc/Documentation/cgroups/blkio-controller.txt

try:
    HOSTNAME = os.environ['COLLECTD_HOSTNAME']
except:
    HOSTNAME = 'localhost'
try:
    INTERVAL = os.environ['COLLECTD_INTERVAL']
except:
    INTERVAL = 60
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
}

# White and Blacklisting happens before flattening
WHITELIST_STATS = {
    'docker-librato.\w+.cpu_stats.*',
    'docker-librato.\w+.memory_stats.*',
    'docker-librato.\w+.network.*',
    #'docker-librato.\w+.blkio_stats.io_service_bytes_recursive.\d+.value',
    #'docker-librato.\w+.blkio_stats.io_serviced_recursive.\d+.value',
    #'docker-librato.\w+.*',
}

BLACKLIST_STATS = {
    'docker-librato.\w+.memory_stats.stats.total_*',
    'docker-librato.\w+.cpu_stats.cpu_usage.percpu_usage.*',
}

def log(str):
    if DEBUG == True:
        ts = time.time()
        print "%s: %s" % (datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S.%f'), str)

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

def find_containers():
    log('getting container ids')
    try:
        r = requests.get('http://127.0.0.1:2375/containers/json')
        log('done getting container ids')
        result = json.loads(r.text)
        log('done translating result into json')
        return [c['Id'] for c in result]
    except:
        log('unable to get container ids')
        sys.exit(1)

def gather_stats(container_id):
    log('getting container stats')
    try:
        r = requests.get("http://127.0.0.1:2375/containers/%s/stats" % container_id, stream=True)
        log('done getting container stats')
        result = json.loads(r.raw.readline())
        log('done translating result into json')
        return result
    except:
        log('unable to get container stats')
        sys.exit(1)

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

while True:
    try:
        whitelist = compile_regex(WHITELIST_STATS)
        blacklist = compile_regex(BLACKLIST_STATS)
        for id in find_containers():
            try:
                stats = gather_stats(id)
                for i in flatten(stats, key=id[0:12], path='docker-librato').items():
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

    except KeyboardInterrupt:
        sys.exit(1)
    time.sleep(float(INTERVAL))
