####    IMPORTS
import os
import boto3
import logging
import platform

from subprocess import run
from subprocess import call
from subprocess import PIPE

import docker

logging.basicConfig(filename="/tmp/output_swarm.log", level=logging.INFO, format="%(asctime)s " + platform.node() + ": %(message)s")
docker_client = docker.from_env()

ec2 = boto3.client('ec2')
role = os.environ['ROLE']
current_instance = os.environ['INSTANCE']
hostname = platform.node()

def add_tag(tags):
    return ec2.create_tags(Resources=[current_instance], Tags=tags)

def count_nodes(nodes):
    count = 0
    instances_list = []
    for ins in nodes:
        count += len(ins['Instances'])
        for obj in ins['Instances']:
            instances_list.append(obj)
    return count, instances_list


managers_running = ec2.describe_instances(Filters=[
    {'Name': 'tag:Name', 'Values': ['swarm-manager']},
    {'Name': 'instance-state-name', 'Values': ['running']},
    {'Name': 'tag:Init', 'Values': ['true']}])

instances_count, instances = count_nodes(managers_running['Reservations'])


if instances_count > 0 or role == 'worker':
    manager = instances[0]['PrivateIpAddress']
    logging.info("'Here I join to the cluster {}'".format(manager))
    token = run(["docker", "-H {}:2376".format(manager), "swarm", "join-token", "-q", role], stdout=PIPE)
    call(['docker', 'swarm', 'join', '{}:2377'.format(manager), '--token', token.stdout.decode('utf-8').replace('\n', '')])

    add_tag([{'Key': 'Hostname', 'Value': hostname}])
    if role == 'manager':
        add_tag([{'Key': 'Init', 'Value': 'true'}])

else:
    try:
        docker_client.swarm.init()
        logging.info("Init the new Cluster")
    except Exception as e:
        logging.error("Swarm Init Error: " + str(e))

    hostname = run(['hostname'], stdout=PIPE)
    add_tag([
        {'Key': 'Init', 'Value': 'true'},
        {'Key': 'Hostname', 'Value': hostname}])