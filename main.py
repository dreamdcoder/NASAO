from cassandra_data_mgmt import data
import json
import os
import glob2

config = json.load(open('config.json'))
print(config['cassandra']['data_path'])
path = os.getcwd() + config['cassandra']['data_path']
active_routes_count_list= config['leaf1']['active_routes_count']
print(active_routes_count_list)

print(path)
        # returns all file having pattern from a path provided
csv_files = glob2.glob(os.path.join(path, "*.csv"))

print(csv_files)

