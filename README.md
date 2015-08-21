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

The custom plugin will need to be installed along with an updated types.db (`docker.db`). Additionally, we need to add a non-superuser user to the `docker` system group for access to the UNIX socket where the Docker API is listening. For our purposes, we've chosen the unprivileged `nobody` system user, although you can adjust this as needed for your environment. The `collectd` service can then be restarted.

```
$ git clone https://github.com/librato/librato-collectd-docker.git
$ sudo cp collectd-docker.py /usr/share/collectd/
$ sudo cp docker.conf /etc/collectd/collectd.conf.d/
$ sudo cp docker.db /etc/collectd/collectd.conf.d/
$ sudo usermod -a -G docker nobody
$ sudo service collectd restart
```

### Configuration

The included `docker.conf` should either be installed into your collectd configurations directory as demonstrated above, or lacking that capability, the following configuration should be enabled in your `collectd.conf`. Any configuration changes will need to be followed with a service restart.

```
LoadPlugin exec
<Plugin exec>
  Exec "nobody:docker" "/usr/share/collectd/collectd-docker.py"
</Plugin>

# Add custom TypesDB for network counter stats
TypesDB "/usr/share/collectd/types.db" "/etc/collectd/collectd.conf.d/docker.db"
```

Note that the script supports connections to the Docker API via either the default UNIX socket at `unix://var/run/docker.sock` or a TCP port. To change the default URL, simply edit the `Exec` line above to include the URL as an argument. For example, if your Docker API is listening via TCP on port 2375, you'll want to edit the line as such:

```
  Exec "nobody" "/usr/share/collectd/collectd-docker.py" "http://127.0.0.1:2375"
```

## License

This project is distributed under the MIT license.
