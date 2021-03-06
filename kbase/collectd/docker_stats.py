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
import collectd
import docker
import re
from os.path import basename, splitext

CLIENT = None
CONFIG_OPTIONS = dict()
LABEL = None
TYPE_INSTS = [t[0] for t in collectd.get_dataset('docker')]
IMG_REGX = re.compile('\'([\w/:.-]+)')  # Regex for matching image name from image object


log_tmpl = splitext(basename(__file__))[0] + " plugin: %s"


def log(msg):
    collectd.info(log_tmpl % msg)


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
    LABEL = list(labels)
    log("Filtering containers based on label(s) %s" % str(LABEL))

    def _list(client):
        return client.containers.list(filters={'label': LABEL})

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
        else:
            log('Unkown config key "%s"' & node.key)


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
    # Some containers don't have network stats, return 0 in that case
    try:
        net = stats['networks']['eth0']
    except KeyError:
        net = {'rx_bytes': 0, 'tx_bytes': 0}
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
    for container in list_containers(CLIENT):
        stats = get_stats(container)
        meta = build_metadata(container)
        values = [stats[k] for k in TYPE_INSTS]
        # Pack the image_name, container.name and container.short_id into the type_instance field
        # Parse out the name:tag of the running image from the image object
        # You can get the name but not tag of image from container attrs, so this
        # seems to be easiest method
        match = IMG_REGX.search(str(container.image))
        image = match.group(1)

        instance = {"image": image,
                    "name": container.name,
                    "short_id": container.short_id}
        type_instance = " ".join(["{0}={1}".format(k, v) for k, v in instance.items()])
        v = collectd.Values(type='docker',
                            type_instance=type_instance,
                            plugin='docker_stats', meta=meta)
        v.dispatch(values=values, meta=meta)


collectd.register_init(init_func)
collectd.register_read(read_func)
collectd.register_config(config_func)
