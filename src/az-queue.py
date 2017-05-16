
import argparse
import os

from azure.servicebus import ServiceBusService, Message, Queue

DEFAULT_SAS_DIRECTORY = 'private-pool-sas-tokens'
DEFAULT_POOL_FILE_PREFIX = "azure_vm_pool"
DEFAULT_SERVICEBUS_SAS_KEY_NAME = "RootManageSharedAccessKey"
DEFAULT_SERVICEBUS_SAS_PREFIX = "sas_servicebus"
DEFAULT_POOL_FILE_PREFIX = "azure_vm_pool"

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description=__name__)
    parser.add_argument('resource_group',
        help='Name of VM pool resource group.')
    parser.add_argument('queue_name',
        help='Name of service bus queue.')
    parser.add_argument('command', choices=['create', 'status', 'delete'])
    args = parser.parse_args()
    # Add some default arguments that we won't clutter up the command line with
    args.pool_file_prefix = DEFAULT_POOL_FILE_PREFIX
    args.sas_directory = DEFAULT_SAS_DIRECTORY
    args.servicebus_sas_prefix = DEFAULT_SERVICEBUS_SAS_PREFIX
    args.servicebus_sas_key_name = DEFAULT_SERVICEBUS_SAS_KEY_NAME

    if(args.command == 'create'):
        create_queue(args)
    elif(args.command == 'status'):
        queue_status(args)
    elif(args.command == 'delete'):
        delete_queue(args)
    else:
        logger.warning("Unsupported command")

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
    filepath = os.path.join(args.sas_directory, servicebus_management_sas_filename(args))
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

## ------------------
## TOP-LEVEL COMMANDS
## ------------------
def create_queue(args):
    bus = get_servicebus(args)
    queue_name = args.queue_name
    try:
        bus.get_queue(queue_name)
        print("Queue '{:s}' already exists. Skipping create.".format(queue_name))
        return
    except:
        print("Creating queue '{:s}'".format(queue_name))
        success = bus.create_queue(queue_name)
        if(success):
            print("Queue '{:s}' successfully created.".format(queue_name))
        else:
            print("Failed to create queue '{:s}'.".format(queue_name))

def queue_status(args):
    bus = get_servicebus(args)
    queue_name = args.queue_name
    queue_length = bus.get_queue(queue_name=queue_name).message_count
    print("{:d} messages in queue '{:s}'".format(queue_length, queue_name))

def delete_queue(args):
    bus = get_servicebus(args)
    queue_name = args.queue_name
    try:
        bus.get_queue(queue_name)
    except:
        print("Could not find queue '{:s}'. Skipping delete.".format(queue_name))
        return
    success = bus.delete_queue(queue_name)
    if(success):
        print("Queue '{:s}' successfully deleted.".format(queue_name))
    else:
        print("Failed to delete queue '{:s}'.".format(queue_name))

if __name__ == "__main__":
    main()
