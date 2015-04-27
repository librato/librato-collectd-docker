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
import pprint
import fileinput
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
    SYSMOUNT = os.environ['CGROUP_MOUNT']
except:
    SYSMOUNT = '/sys/fs/cgroup'

CGROUP_STATS = {
    'cpu.stat': {
        'nr_periods': 'enforce-intervals',
        'nr_throttled': 'num-throttled',
        'throttled_time': 'time-throttled',
    },
    'cpu_stats': {
        'user': 'user',
        'system': 'system',
    },
    'memory_stats': {
        'cache': 'cached',
        'rss': 'used',
        'mapped_file': 'mapped-file',
        'pgpgin': 'pgpgin',
        'pgpgout': 'pgpgout',
        'pgfault': 'pgfault',
        'pgmajfault': 'pgmajfault',
        'active_anon': 'active-anon',
        'inactive_anon': 'inactive-anon',
        'active_file': 'active-file',
        'inactive_file': 'inactive-file',
        'unevictable': 'unevictable',
        'hierarchical_memory_limit': 'hierarchical-limit',
    },
    'network': {
        
    }
}

def logging(str):
    ts = time.time()
    print "%s: %s" % (datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'), str)

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
    #response = urllib2.urlopen('http://127.0.0.1:2375/containers/json')
    #result = json.loads(response.read())
    #response.close()
    r = requests.get('http://127.0.0.1:2375/containers/json')
    result = json.loads(r.text)
    return [c['Id'] for c in result]

def gather_stats(container_id):
    #response = urllib2.urlopen("http://127.0.0.1:2375/containers/%s/stats" % container_id)
    # This takes 4-5s to complete, not sure why it doesn't immediately return
    #result = json.loads(response.readline())
    #response.close()
    r = requests.get("http://127.0.0.1:2375/containers/%s/stats" % container_id, stream=True)
    result = json.loads(r.raw.readline())
    return result

def shorten_id(container_id):
    return container_id[0:12]

try:
    find_containers()
    for id in find_containers():
        try:
            stats = gather_stats(id)
            for i in flatten(stats, key=id[0:12], path='docker-librato').items():
                print "metric %s has value %s" % (i[0].encode('ascii'), i[1])
        except:
            sys.exit(1)

except KeyboardInterrupt:
    sys.exit(1)
