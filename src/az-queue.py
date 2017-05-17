#! /usr/bin/env python

import argparse
import os

from azure.servicebus import ServiceBusService, Message, Queue

DEFAULT_SAS_DIRECTORY = 'secrets'
DEFAULT_POOL_FILE_PREFIX = "azure_vm_pool"
DEFAULT_SERVICEBUS_SAS_KEY_NAME = "RootManageSharedAccessKey"
DEFAULT_SERVICEBUS_SAS_PREFIX = "sas_servicebus"

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description=__name__)
    parser.add_argument('resource_group',
        help='Name of VM pool resource group.')
    parser.add_argument('queue_name',
        help='Name of service bus queue.')
    parser.add_argument('command', choices=['create', 'status', 'fill', 'empty', 'fetch', 'delete'])
    parser.add_argument('--input-path', '-i',
        help='Path to input task file. Each line in the file will be passed to the queue as a single string.')
    parser.add_argument('--output-path', '-o',
        help='Path to output task file. The next task in the queue will written to this file as a single string on a single line.')
    parser.add_argument('--sas-path', '-t',
        help='Path to Shared Access Signature (SAS) token with full access to the queue')

    args = parser.parse_args()
    # Add some default arguments that we won't clutter up the command line with
    args.pool_file_prefix = DEFAULT_POOL_FILE_PREFIX
    args.servicebus_sas_prefix = DEFAULT_SERVICEBUS_SAS_PREFIX
    args.servicebus_sas_key_name = DEFAULT_SERVICEBUS_SAS_KEY_NAME

    if(args.command == 'create'):
        create(args)
    elif(args.command == 'status'):
        status(args)
    elif(args.command == 'fill'):
        fill(args)
    elif(args.command == 'empty'):
        empty(args)
    elif(args.command == 'fetch'):
        fetch(args)
    elif(args.command == 'delete'):
        delete(args)
    else:
        print("Unsupported command")

## ----------------
## HELPER FUNCTIONS
## ----------------
def servicebus_namespace(args):
    return args.resource_group

def servicebus_management_sas_filename(args):
    return "{:s}_{:s}_{:s}_management.txt".format(args.pool_file_prefix, args.resource_group, args.servicebus_sas_prefix)

def servicebus_queue_sas_filename(queue_name, args):
    return "{:s}_{:s}_{:s}_queue_{:s}.txt".format(args.pool_file_prefix, args.resource_group, args.servicebus_sas_prefix, queue_name)

def get_servicebus_management_sas(args):
    if(args.sas_path != None):
        filepath = args.sas_path
    else:
        filepath = os.path.join(DEFAULT_SAS_DIRECTORY, servicebus_management_sas_filename(args))
    with open(filepath, 'r') as f:
        sas = f.readline()
    return sas

def get_servicebus(args):
    namespace = servicebus_namespace(args)
    key_name = args.servicebus_sas_key_name
    key_value = get_servicebus_management_sas(args)
    bus = ServiceBusService(
        service_namespace = namespace,
        shared_access_key_name = key_name,
        shared_access_key_value = key_value
    )
    return(bus)

def queue_exists(queue_name, args):
    bus = get_servicebus(args)
    queue_name = args.queue_name
    try:
        exists = bus.get_queue(queue_name)
        # If no exception, then queue exists, but return actual return value
        # from get_queue in case this changes in future
        return exists
    except:
        # Exception is thrown if queue does not exists
        return False

def fetch_task(queue_name, args):
    bus = get_servicebus(args)
    queue_name = args.queue_name
    if(not(queue_exists(queue_name, args))):
        return False
    else:
        task = bus.receive_queue_message(queue_name, peek_lock=False, timeout = 0).body
        return task

def queue_task(task, queue_name, args):
    bus = get_servicebus(args)
    if(not(queue_exists(queue_name, args))):
        return False
    else:
        success = bus. send_queue_message(queue_name, Message(task))
        return success

def create_queue(queue_name, args):
    bus = get_servicebus(args)
    if(queue_exists(queue_name, args)):
        return(True)
    else:
        success = bus.create_queue(queue_name)
        return(success)

def delete_queue(queue_name, args):
    bus = get_servicebus(args)
    if(not(queue_exists(queue_name, args))):
        return(True)
    else:
        success = bus.delete_queue(queue_name)
        return(success)

def fill_queue(queue_name, task_file_path, args):
    bus = get_servicebus(args)
    if(not(queue_exists(queue_name, args))):
        return(False)
    else:
        with open(task_file_path, 'r') as f:
            tasks = f.readlines()
        [queue_task(task, queue_name, args) for task in tasks]

def empty_queue(queue_name, args):
    bus = get_servicebus(args)
    if(not(queue_exists(queue_name, args))):
        return(True)
    else:
        while(has_tasks(queue_name, args)):
            fetch_task(queue_name, args)

def queue_length(queue_name, args):
    bus = get_servicebus(args)
    return bus.get_queue(queue_name=queue_name).message_count

def has_tasks(queue_name, args):
    num_msgs = queue_length(queue_name, args)
    return(num_msgs > 0)

## ------------------
## TOP-LEVEL COMMANDS
## ------------------
def create(args):
    queue_name = args.queue_name
    if(queue_exists(queue_name, args)):
        print("Queue '{:s}' already exists. Skipping create.".format(queue_name))
    else:
        success = create_queue(queue_name, args)
        if(success):
            print("Queue '{:s}' successfully created.".format(queue_name))
        else:
            print("Failed to create queue '{:s}'.".format(queue_name))

def status(args):
    queue_name = args.queue_name
    if(not(queue_exists(queue_name, args))):
        print("Could not find queue '{:s}'. Skipping status check.".format(queue_name))
    num_tasks = queue_length(queue_name, args)
    print("{:d} messages in queue '{:s}'".format(num_tasks, queue_name))

def delete(args):
    bus = get_servicebus(args)
    queue_name = args.queue_name
    if(not(queue_exists(queue_name, args))):
        print("Could not find queue '{:s}'. Skipping delete.".format(queue_name))
    else:
        success = bus.delete_queue(queue_name)
        if(success):
            print("Queue '{:s}' successfully deleted.".format(queue_name))
        else:
            print("Failed to delete queue '{:s}'.".format(queue_name))

def fill(args):
    bus = get_servicebus(args)
    queue_name = args.queue_name
    task_file_path = args.input_path
    print("Filling queue '{:s}' with parameters from '{:s}'.".format(queue_name, task_file_path))
    if(not(queue_exists(queue_name, args))):
        print("Could not find queue '{:s}'. Skipping fill.".format(queue_name))
    else:
        fill_queue(queue_name, task_file_path, args)
        print("{:d} messages in queue '{:s}'".format(queue_length(queue_name, args), queue_name))

def empty(args):
    bus = get_servicebus(args)
    queue_name = args.queue_name
    print("Emptying {:d} messages from queue '{:s}'.".format(queue_length(queue_name, args), queue_name))
    if(not(queue_exists(queue_name, args))):
        print("Could not find queue '{:s}'. Skipping empty.".format(queue_name))
    else:
        empty_queue(queue_name, args)
        print("{:d} messages in queue '{:s}'".format(queue_length(queue_name, args), queue_name))

def fetch(args):
    queue_name = args.queue_name
    task_file_path = args.output_path
    print("Getting next task from queue '{:s}' and saving to '{:s}'.".format(queue_name, task_file_path))
    if(not(queue_exists(queue_name, args))):
        print("Could not find queue '{:s}'. Skipping task fetch.".format(queue_name))
    else:
        task = fetch_task(queue_name, args)
        if(task == None):
            print("No tasks to fetch")
        else:
            with open(task_file_path, 'w+') as f:
                f.write(task)
        print("{:d} messages in queue '{:s}'".format(queue_length(queue_name, args), queue_name))


if __name__ == "__main__":
    main()
