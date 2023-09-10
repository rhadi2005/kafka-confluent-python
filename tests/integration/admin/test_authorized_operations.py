# -*- coding: utf-8 -*-
# Copyright 2022 Confluent Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import confluent_kafka
import struct
import time
import pytest
from confluent_kafka import ConsumerGroupTopicPartitions, TopicPartition, ConsumerGroupState, KafkaException
from confluent_kafka.admin import (NewPartitions, ConfigResource,
                                   AclBinding, AclBindingFilter, ResourceType,
                                   ResourcePatternType, AclOperation, AclPermissionType,
                                   UserScramCredentialsDescription, UserScramCredentialUpsertion,
                                   UserScramCredentialDeletion, ScramCredentialInfo,
                                   ScramMechanism)
from confluent_kafka.error import ConsumeError, KafkaException, KafkaError

topic_prefix = "test-topic"

# Shared between producer and consumer tests and used to verify
# that consumed headers are what was actually produced.
produce_headers = [('foo1', 'bar'),
                   ('foo1', 'bar2'),
                   ('foo2', b'1'),
                   (u'Jämtland', u'Härjedalen'),  # automatically utf-8 encoded
                   ('nullheader', None),
                   ('empty', ''),
                   ('foobin', struct.pack('hhl', 10, 20, 30))]


def verify_commit_result(err, _):
    assert err is not None


def consume_messages(sasl_cluster, group_id, topic, num_messages=None):
    conf = {'group.id': group_id,
            'session.timeout.ms': 6000,
            'enable.auto.commit': False,
            'on_commit': verify_commit_result,
            'auto.offset.reset': 'earliest'}
    consumer = sasl_cluster.consumer(conf)
    consumer.subscribe([topic])
    read_messages = 0
    msg = None
    while True:
        try:
            msg = consumer.poll()
            if msg is None:
                raise Exception('Got timeout from poll() without a timeout set: %s' % msg)
            # Commit offset
            consumer.commit(msg, asynchronous=False)
            read_messages += 1
            if num_messages is not None and read_messages == num_messages:
                print('Read all the required messages: exiting')
                break
        except ConsumeError as e:
            print('Consumer error: %s: ignoring' % str(e))
            break
        except Exception:
            raise
    consumer.close()


def perform_admin_operation_sync(operation, *arg, **kwargs):
    future_key = arg[0][0] if len(arg) > 0 else None
    fs = operation(*arg, **kwargs)
    fs = fs[future_key] if future_key else fs 
    return fs.result()


def create_acls(admin_client, acl_bindings):
    perform_admin_operation_sync(admin_client.create_acls, acl_bindings)


def delete_acls(admin_client, acl_binding_filters):
    perform_admin_operation_sync(admin_client.delete_acls, acl_binding_filters)


def verify_provided_describe_for_authorized_operations(admin_client, describe_fn, operation_to_allow, operation_to_check, restype, resname, *arg):
    kwargs = {}
    kwargs['request_timeout'] = 10

    # Check with include_authorized_operations as False
    kwargs['include_authorized_operations'] = False
    desc = perform_admin_operation_sync(describe_fn, *arg, **kwargs)
    assert desc.authorized_operations == []

    # Check with include_authorized_operations as True
    kwargs['include_authorized_operations'] = True
    desc = perform_admin_operation_sync(describe_fn, *arg, **kwargs)
    assert len(desc.authorized_operations) > 0
    assert operation_to_check in desc.authorized_operations

    # Update Authorized Operation by creating new ACLs
    acl_binding = AclBinding(restype, resname, ResourcePatternType.LITERAL,
                               "User:sasl_user", "*", operation_to_allow, AclPermissionType.ALLOW)
    create_acls(admin_client, [acl_binding])
    time.sleep(2)

    # Check with updated authorized operations
    desc = perform_admin_operation_sync(describe_fn, *arg, **kwargs)
    assert len(desc.authorized_operations) > 0
    assert operation_to_check not in desc.authorized_operations

    # Delete Updated ACLs
    acl_binding_filter = AclBindingFilter(restype, resname, ResourcePatternType.ANY,
                                           None, None, AclOperation.ANY, AclPermissionType.ANY)
    delete_acls(admin_client, [acl_binding_filter])
    time.sleep(2)


def verify_describe_topics(admin_client, topic):
    verify_provided_describe_for_authorized_operations(admin_client, 
                            admin_client.describe_topics, 
                            AclOperation.READ, 
                            AclOperation.DELETE, 
                            ResourceType.TOPIC, 
                            topic,
                            [topic])


def verify_describe_group(cluster, admin_client, our_topic):

    # Produce some messages
    p = cluster.producer()
    p.produce(our_topic, 'Hello Python!', headers=produce_headers)
    p.produce(our_topic, key='Just a key and headers', headers=produce_headers)
    p.flush()

    # Consume some messages for the group
    group = 'test-group'
    consume_messages(cluster, group, our_topic, 2)

    # Verify Describe Consumer Groups
    verify_provided_describe_for_authorized_operations(admin_client,
                            admin_client.describe_consumer_groups,
                            AclOperation.READ,
                            AclOperation.DELETE,
                            ResourceType.GROUP, 
                            group,
                            [group])

    # Delete group
    perform_admin_operation_sync(admin_client.delete_consumer_groups, [group], request_timeout=10)


def verify_describe_cluster(admin_client):
    verify_provided_describe_for_authorized_operations(admin_client, 
                            admin_client.describe_cluster, 
                            AclOperation.ALTER, 
                            AclOperation.ALTER_CONFIGS, 
                            ResourceType.BROKER, 
                            "kafka-cluster")


def test_authorized_operations(sasl_cluster):

    admin_client = sasl_cluster.admin()

    # Verify Authorized Operations in Describe Cluster
    verify_describe_cluster(admin_client)

    # Create Topic
    topic_config = {"compression.type": "gzip"}
    our_topic = sasl_cluster.create_topic(topic_prefix,
                                        {
                                            "num_partitions": 1,
                                            "config": topic_config,
                                            "replication_factor": 1,
                                        },
                                        validate_only=False
                                        )

    # Verify Authorized Operations in Describe Topics
    verify_describe_topics(admin_client, our_topic)

    # Verify Authorized Operations in Describe Groups
    verify_describe_group(sasl_cluster, admin_client, our_topic)

    # Delete Topic
    perform_admin_operation_sync(admin_client.delete_topics, [our_topic], operation_timeout=0, request_timeout=10)
