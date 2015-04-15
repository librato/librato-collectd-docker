#!/bin/bash

# librato-collectd-docker
#
# This script collects container-level stats for Docker containers from the
# host system and outputs the data in a collectd-exec plugin friendly format.
#
# Author: Mike Moulton <mike@meltmedia.com>
# License: MIT
#
# Extended and adapted for use by Librato
# Jason Dixon <jdixon@librato.com>

# Location of the cgroup mount point, adjust for your system
CGROUP_MOUNT="/sys/fs/cgroup"

HOSTNAME="${COLLECTD_HOSTNAME:-localhost}"
INTERVAL="${COLLECTD_INTERVAL:-60}"

collect ()
{
  cd "$1"

  # If the directory length is 64, it's likely a docker instance
  LENGTH=$(expr length $1);
  if [ "$LENGTH" -eq "64" ]; then

    # Shorten the name to 12 for brevity, like docker does
    NAME=$(expr substr $1 1 12);

    # If we are in a cpu cgroup, we can collect cpu usage stats
    if [ -e cpu.stat ]; then
        NR_PERIODS=$(cat cpu.stat | grep '^nr_periods' | awk '{ print $2; }');
        NR_THROTTLED=$(cat cpu.stat | grep '^nr_throttled' | awk '{ print $2; }');
        THROTTLED_TIME=$(cat cpu.stat | grep '^throttled_time' | awk '{ print $2; }');
        echo "PUTVAL \"$HOSTNAME/docker-$NAME/cpu-enforce-intervals\" interval=$INTERVAL N:$NR_PERIODS"
        echo "PUTVAL \"$HOSTNAME/docker-$NAME/cpu-num-throttled\" interval=$INTERVAL N:$NR_THROTTLED"
        echo "PUTVAL \"$HOSTNAME/docker-$NAME/cpu-time-throttled\" interval=$INTERVAL N:$THROTTLED_TIME"
    fi;

    # If we are in a cpuacct cgroup, we can collect cpuacct usage stats
    if [ -e cpuacct.stat ]; then
        USER=$(cat cpuacct.stat | grep '^user' | awk '{ print $2; }');
        SYSTEM=$(cat cpuacct.stat | grep '^system' | awk '{ print $2; }');
        echo "PUTVAL \"$HOSTNAME/docker-$NAME/cpu-user\" interval=$INTERVAL N:$USER"
        echo "PUTVAL \"$HOSTNAME/docker-$NAME/cpu-system\" interval=$INTERVAL N:$SYSTEM"
    fi;

    # If we are in a memory cgroup, we can collect memory usage stats
    if [ -e memory.stat ]; then
        CACHE=$(cat memory.stat | grep '^cache' | awk '{ print $2; }');
        RSS=$(cat memory.stat | grep '^rss ' | awk '{ print $2; }');
        echo "PUTVAL \"$HOSTNAME/docker-$NAME/memory-cached\" interval=$INTERVAL N:$CACHE"
        echo "PUTVAL \"$HOSTNAME/docker-$NAME/memory-used\" interval=$INTERVAL N:$RSS"
    fi;

  fi;

  # Iterate over all sub directories
  for d in *
  do
    if [ -d "$d" ]; then
      ( collect "$d" )
    fi;
  done
}

while sleep "$INTERVAL"; do
  # Collect stats on memory usage
  ( collect "$CGROUP_MOUNT/memory" )

  # Collect stats on cpu usage
  ( collect "$CGROUP_MOUNT/cpuacct" )
done
