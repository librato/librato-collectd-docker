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

WHITELIST_STATS = {
    'docker-librato.\w+.cpu_stats.*',
    'docker-librato.\w+.memory_stats.*',
    'docker-librato.\w+.network.*',
    #'docker-librato.\w+.*',
}

BLACKLIST_STATS = {
    'docker-librato.\w+.memory_stats.stats.total_*',
}

def logging(str):
    if DEBUG == True:
        ts = time.time()
        print "%s: %s" % (datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S.%f'), str)

def flatten(structure, key="", path="", flattened=None):
    logging('flattening metric')
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
    logging('done flattening metric')
    return flattened

def find_containers():
    logging('getting container ids')
    r = requests.get('http://127.0.0.1:2375/containers/json')
    logging('done getting container ids')
    result = json.loads(r.text)
    logging('done translating result into json')
    return [c['Id'] for c in result]

def gather_stats(container_id):
    logging('getting container stats')
    r = requests.get("http://127.0.0.1:2375/containers/%s/stats" % container_id, stream=True)
    logging('done getting container stats')
    result = json.loads(r.raw.readline())
    logging('done translating result into json')
    return result

def shorten_id(container_id):
    return container_id[0:12]

def compile_regex(list):
    regexes = []
    for l in list:
        regexes.append(re.compile(l))
    return regexes

try:
    find_containers()
    whitelist = compile_regex(WHITELIST_STATS)
    blacklist = compile_regex(BLACKLIST_STATS)
    for id in find_containers():
        try:
            stats = gather_stats(id)
            for i in flatten(stats, key=id[0:12], path='docker-librato').items():
                blacklisted = False
                for r in blacklist:
                    if r.match(i[0].encode('ascii')):
                        logging('skipping blacklisted metric')
                        blacklisted = True
                        break
                if blacklisted == False:
                    for r in whitelist:
                        if r.match(i[0].encode('ascii')):
                            print "metric %s has value %s" % (i[0].encode('ascii'), i[1])
                            logging('done flattening metric')
                            break
        except:
            sys.exit(1)

except KeyboardInterrupt:
    sys.exit(1)
