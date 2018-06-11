from datetime import datetime
from elasticsearch import Elasticsearch
from pprint import pprint
from datetime import datetime, timedelta
import time

host = [ "elasticsearch1.chicago.kbase.us:9200" ]
es = Elasticsearch(host)

docker_index = "<logstash-collectd_docker-{now/d}>"

body = {
    "size": 10000,
    "query": {"range": {"@timestamp": {"gte": "now-10m"}}},
    "aggs": {
        "containers": {
            "terms": {"field": "container_id.keyword", "size": 10000},
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

fmt = "{docker_image}\t{container_id}\t{container_name}"
print(fmt.replace('{', '').replace('}', ''))
for b in res['aggregations']['containers']['buckets']:
    rec = b['most_recent']['hits']['hits'][0]['_source']
    print(fmt.format(**rec))
