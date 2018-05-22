"""
A collectd plugin for gathering Docker stats from labelled containers.

By default, this plugin will collect data on all containers running on a
system. This plugin can be configured to collect data on only containers
with specified labels. These labels can be specified in the plugin config
file using the key "labels". All values listed will be used to screen
containers.

Example config file:

labels   module_id, user


Written by Andrew Tritt, ajtritt@lbl.gov
"""
import sys
import collectd
import docker


CLIENT = None
CONFIG_OPTIONS = dict()
LABEL = None
TYPE_INSTS = [t[0] for t in collectd.get_dataset('docker')]


def init_func():
    global CLIENT
    CLIENT = docker.from_env()


def config(key):
    """
    Designate a function for processing a configuration option

    Args:
        key (str): the collectd config option

    """
    def dec(func):
        CONFIG_OPTIONS[key] = func
    return dec


def list_containers(client):
    """
    A function to get containers from Docker

    This will be overwritten by config_labels if more than one
    label is listed in the collectd config file

    """
    return client.containers.list()


def build_metadata(container):
    """
    A function to build the metadata record for this container

    This will be overwritten by config_labels if one or more labels
    is listed in the collectd config file

    """
    return {'container_id': container.id}


@config('labels')
def process_labels(values):
    """
    The labels that must be attached to a Docker container for its data to be
    logged. These labels will be attached (as metadata) to dispacted data.

    """
    global LABEL
    global list_containers
    global build_metadata
    labels = values[:]
    _list = None
    _meta = None
    if len(labels) == 1:
        LABEL = labels[0]
        def _list(client):
            return client.containers.list(label=LABEL)
        def _meta(container):
            return {'container_id': container.id,
                    LABEL: container.labels[label]}
    else:
        LABEL = labels
        def _list(client):
            return [c for c in client.containers.list() if all(l in c.labels for l in LABEL)]
        def _meta(container):
            ret = {l: container.labels[l] for l in LABEL}
            ret['container_id'] = container.id
            return ret
    list_containers = _list
    build_metadata = _meta


def config_func(config):
    """
    Read collectd configuration files.

    Config options:
        labels: the

    """
    global CONFIG_OPTIONS
    for node in config.children:
        func = CONFIG_OPTIONS.get(node.key)
        if func:
            func(node.values)


def max_mem(stats):
    """
    Get maximum memory usage

    Args:
        stats (dict): a Docker container stats dict

    Returns:
        max memory usage TODO figure out units

    """
    return stats['memory_stats']['max_usage']


def cpu_usage(stats):
    """
    Get total CPU usage

    Args:
        stats (dict): a Docker container stats dict

    Returns:
        total cpu usage TODO figure out units

    """
    return stats['cpu_stats']['cpu_usage']['total_usage']


def blkio(stats):
    """
    Get network I/O statistics

    Args:
        stats (dict): a Docker container stats dict

    Returns:
        a tuple of read bytes and written bytes

    """
    blkio = stats['blkio_stats']['io_service_bytes_recursive']
    blk_in = 0
    blk_out = 0
    for d in blkio:
        if d['op'] == 'Read':
            blk_in = d['value']
        elif d['op'] == 'Write':
            blk_out = d['value']
    return blk_in, blk_out


def network(stats):
    """
    Get network I/O statistics

    Args:
        stats (dict): a Docker container stats dict

    Returns:
        a tuple of received bytes and transmitted bytes

    """
    net = stats['networks']['eth0']
    return net['rx_bytes'], net['tx_bytes']


def get_stats(container):
    """
    Get and format Docker stats that we care about

    Args:
        container (Container): the Docker Container object

    Returns:
        a dict with stats we care about

    """
    stats = container.stats(stream=False)
    blk_in, blk_out = blkio(stats)
    net_in, net_out = network(stats)
    mystats = {
        "cpu_usage": cpu_usage(stats),
        "max_mem": max_mem(stats),
        "blk_in": blk_in,
        "blk_out": blk_out,
        "net_in": net_in,
        "net_out": net_out,
        "blk_in_rate": blk_in,
        "blk_out_rate": blk_out,
        "net_in_rate": net_in,
        "net_out_rate": net_out,
    }
    return mystats


def read_func():
    """
    Iterate over all containers

    """
    cts = list_containers(CLIENT)
    for container in list_containers(CLIENT):
        stats = get_stats(container)
        meta = build_metadata(container)
        values = [stats[k] for k in TYPE_INSTS]
        collectd.Values(type='docker', type_instance=container.id, plugin='docker_stats', meta=meta).dispatch(values=values)


collectd.register_init(init_func)
collectd.register_read(read_func, 1)
collectd.register_config(config_func)
