import sys
import docker
import argparse
import os
from pprint import pprint


def max_mem(stats):
    return stats['memory_stats']['max_usage']


def cpu_usage(stats):
    return stats['cpu_stats']['cpu_usage']['total_usage']


def blkio(stats):
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
    net = stats['networks']['eth0']
    return net['rx_bytes'], net['tx_bytes']


def get_stats(container):
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
    }
    mystats.update(container.labels)
    return mystats


if __name__ == '__main__':

    desc = "Retrieve statistics for a KBase Docker container"
    epi = "Statistics are printed in JSON format to stdout"
    parser = argparse.ArgumentParser(usage="%(prog)s container_id",
                                     description=desc, epilog=epi)
    parser.add_argument('container_id', type=str,
                        help='the container to get the max memory usage for')

    args = parser.parse_args()
    client = docker.from_env()
    container = client.containers.get(args.container_id)
    mystats = get_stats(container)
    pprint(mystats)
