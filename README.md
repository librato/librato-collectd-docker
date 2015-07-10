librato-collectd-docker
=======================

This project contains a custom collectd *Exec* plugin for gathering statistics from running Docker containers using the Docker API. At this time, the installation steps are brief but manual.

The output of this plugin is formatted for the Librato monitoring service, although you could technically send it to any compatible metrics receiver. Each metric defines its `plugin_instance` in the format `librato-<container_id>`, which is then rewritten on the fly in Librato's API to extract the container identifier into Librato's *source* dimension, and to remove the `librato-` marker.

An example metric originating from the plugin might look like this:
```
collectd/docker-librato-cc899ab3e11b/cpu/kernel
```

... before being rewritten into:
```
collectd.docker.cpu.kernel
```

... with a source of `cc899ab3e11b`.

## Usage

### Dependencies

None, outside of **collectd** and its own dependencies (e.g. Python).

### Environment Variables

None required. Collectd will pass the necessary `COLLECTD_INTERVAL` and `COLLECTD_HOSTNAME` variables into the script at runtime.

### Command-Line Arguments

None.

### Installation

Docker must be reconfigured to listen on a TCP port. This allows our script to connect to the API and pull more detailed statistics than are otherwise available on the kernel filesystem. The following setting needs to be edited in `/etc/default/docker`, then the `docker` service will need to be restarted.

```
DOCKER_OPTS="-H tcp://127.0.0.1:2375 -H unix:///var/run/docker.sock"
```
```
$ sudo service docker restart
```

Then our custom plugin will need to be installed along with an updated types.db (`docker.db`); the `collectd` service can then be restarted.

```
$ git clone https://github.com/librato/librato-collectd-docker.git
$ sudo cp collectd-docker.py /usr/share/collectd/
$ sudo cp docker.db /etc/collectd/collectd.conf.d/
$ sudo service collectd restart
```

## License

This project is distributed under the MIT license.
