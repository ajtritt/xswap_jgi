from datetime import datetime
from elasticsearch import Elasticsearch
from pprint import pprint
from datetime import datetime, timedelta
import time

es = Elasticsearch()

docker_index = "docker"

body = {
    "size": 0,
    "aggs": {
        "containers": {
            "terms": {
                "field": "type_instance.keyword"
            },
            "aggs": {
                "last_update": {"max": {"field": "@timestamp"}},
                "max_mem": {"max": {"field": "max_mem"}},
                "cpu_usage": {"max": {"field": "cpu_usage"}},
                "net_in": {"max": {"field": "net_in"}},
                "net_out": {"max": {"field": "net_out"}},
                "blk_in": {"max": {"field": "blk_in"}},
                "blk_out": {"max": {"field": "blk_out"}},
                "max_net_in_rate": {"max": {"field": "net_in_rate"}},
                "max_net_out_rate": {"max": {"field": "net_out_rate"}},
                "max_blk_in_rate": {"max": {"field": "blk_in_rate"}},
                "max_blk_out_rate": {"max": {"field": "blk_out_rate"}}
            }
        }
    }
}
aggs = { "most_recent": {
                    "top_hits": {
                        "sort": [
                            {
                                "@timestamp": {
                                    "order": "desc"
                                }
                            }
                        ],
                        "size" : 1
       }}}


date = (time.time() - 600) * 1000
body = {
    "size": 0,
    "query": {"range": {"@timestamp": {"gte": date}}},
    "aggs": {
        "containers": {
            "terms": {"field": "type_instance.keyword"},
            "aggs": {
                "most_recent": {
                    "top_hits": {
                        "sort": [{"@timestamp": {"order": "desc"}}],
                        "size" : 1
                    }
                }
            }
        }
    }
}

res = es.search(index=docker_index, body=body)
pprint(res)

res['aggregations']['containers']['buckets']



