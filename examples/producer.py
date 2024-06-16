#!/usr/bin/env python
#
# Copyright 2016 Confluent Inc.
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
#

#
# Example Kafka Producer.
# Reads lines from stdin and sends to Kafka.
#
# python3 producer.py ../kafka-confluent/config-kafka.ini
#

from confluent_kafka import Producer
import sys
import json

from config import settings
from argparse import ArgumentParser, FileType
from configparser import ConfigParser

if __name__ == '__main__':
    # if len(sys.argv) != 3:
    #     sys.stderr.write('Usage: %s <bootstrap-brokers> <topic>\n' % sys.argv[0])
    #     sys.exit(1)

    # broker = sys.argv[1]
    # topic = sys.argv[2]

    if len(sys.argv) != 2:
        sys.stderr.write('Usage: %s <config file>\n' % sys.argv[0])
        sys.exit(1)

    parser = ArgumentParser()
    parser.add_argument('config_file', type=FileType('r'))
    args = parser.parse_args()

    config_parser = ConfigParser()
    config_parser.read_file(args.config_file)
    config = dict(config_parser['default'])
    config.update(config_parser['producer'])
    # config["ssl.ca.location"] = certifi.where()

    broker = config['bootstrap.servers']
    topic = settings.kafka_topic_debug

    print(f"broker: {broker}")
    print(f"topic: {topic}")

    # Producer configuration
    # See https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md
    # conf = {'bootstrap.servers': broker}

    # Create Producer instance
    # p = Producer(**conf)
    p = Producer(config)
    p.init_transactions()
    p.begin_transaction()

    # Optional per-message delivery callback (triggered by poll() or flush())
    # when a message has been successfully delivered or permanently
    # failed delivery (after retries).
    def delivery_callback(err, msg):
        if err:
            sys.stderr.write('%% Message failed delivery: %s\n' % err)
        else:
            # value_json = json.loads(msg.value().decode('utf-8'))
            # key_json = json.loads(msg.key().decode('utf-8'))
            value = msg.value()

            sys.stderr.write('%% Message delivered to %s partition [%d] @ offset %d, msg: %s\n' %
                             (msg.topic(), msg.partition(), msg.offset(), value))

    # Read lines from stdin, produce each line to Kafka
    for line in sys.stdin:
        try:
            # Produce line (without newline)
            p.produce(topic, line.rstrip(), callback=delivery_callback)

        except BufferError:
            sys.stderr.write('%% Local producer queue is full (%d messages awaiting delivery): try again\n' %
                             len(p))

        # Serve delivery callback queue.
        # NOTE: Since produce() is an asynchronous API this poll() call
        #       will most likely not serve the delivery callback for the
        #       last produce()d message.
        p.poll(0)

    # Wait until all messages have been delivered
    sys.stderr.write('%% Waiting for %d deliveries\n' % len(p))
    p.flush()
    p.commit_transaction()
