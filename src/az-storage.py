#! /usr/bin/env python

import argparse
import os

from azure.storage import CloudStorageAccount

DEFAULT_SAS_DIRECTORY = 'secrets'
DEFAULT_POOL_FILE_PREFIX = "azure_vm_pool"
DEFAULT_STORAGE_SAS_PREFIX = "sas_storage"
DEFAULT_DATA_CONTAINER_NAME = "data"
DEFAULT_CONTAINER_SAS_PREFIX = "sas_storage_container"

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description=__name__)
    parser.add_argument('resource_group',
        help='Name of VM pool resource group.')
    parser.add_argument('command', choices=['list', 'put', 'fetch', 'delete'])
    parser.add_argument('--container', '-c',
        default=DEFAULT_DATA_CONTAINER_NAME,
        help='Name of container.')
    parser.add_argument('--blob', '-b',
            help='Name of blob.')
    parser.add_argument('--input-path', '-i',
        help='Path of file to upload.')
    parser.add_argument('--output-path', '-o',
        help='Destination path for downloaded file.')
    parser.add_argument('--sas-path', '-t',
        help='Path to Shared Access Signature (SAS) token with full access to the storage account')

    args = parser.parse_args()
    # Add some default arguments that we won't clutter up the command line with
    args.pool_file_prefix = DEFAULT_POOL_FILE_PREFIX
    args.container_sas_prefix = DEFAULT_CONTAINER_SAS_PREFIX

    # Enforce conditional required arguments
    if(args.command in ['fetch', 'delete'] and args.blob == None):
        parser.error("Blob name required for command '{:s}'. Please provide using '-b' or '--blob'".format(args.command))
    if(args.command in ['put'] and args.input_path == None):
        parser.error("Input path required for command '{:s}'. Please provide using '-i' or '--input-path'".format(args.command))

    if(args.command == 'list'):
        list_blobs(args)
    elif(args.command == 'put'):
        put_blob(args)
    elif(args.command == 'fetch'):
        fetch_blob(args)
    elif(args.command == 'delete'):
        delete_blob(args)
    else:
        print("Unsupported command")

## ----------------
## HELPER FUNCTIONS
## ----------------
def container_sas_filename(args):
    container_name = args.container
    return "{:s}_{:s}_{:s}_{:s}.txt".format(args.pool_file_prefix, args.resource_group, args.container_sas_prefix, container_name)

def get_storage_sas(args):
    if(args.sas_path != None):
        filepath = args.sas_path
    else:
        filepath = os.path.join(DEFAULT_SAS_DIRECTORY, container_sas_filename(args))
    with open(filepath, 'r') as f:
        sas = f.readline()
    return sas

def get_storage_account(args):
    account_name = args.resource_group
    sas = get_storage_sas(args)
    return(CloudStorageAccount(account_name = account_name, sas_token = sas))

def get_blob_service(args):
    account = get_storage_account(args)
    return account.create_block_blob_service()

## ------------------
## TOP-LEVEL COMMANDS
## ------------------
def list_blobs(args):
    blob_service = get_blob_service(args)
    container_name = args.container
    blobs = list(blob_service.list_blobs(container_name))
    for blob in blobs:
        print(blob.name)

def put_blob(args):
    blob_service = get_blob_service(args)
    container_name = args.container
    input_path = args.input_path
    blob_name = os.path.basename(input_path)
    success = blob_service.create_blob_from_path(container_name, blob_name, input_path)
    print("Blob '{:s}' uploaded to container '{:s}' from file '{:s}'.".format(blob_name, container_name, input_path))

def fetch_blob(args):
    blob_service = get_blob_service(args)
    container_name = args.container
    blob_name = args.blob
    if(args.output_path == None):
        output_path = blob_name
    else:
        output_path = args.output_path
    if(not(blob_service.exists(container_name, blob_name))):
        print("Blob '{:s}' does not exist in container '{:s}'. Skipping fetch.".format(blob_name, container_name))
    else:
        output_dir = os.path.dirname(output_path)
        if(not os.path.exists(output_dir)):
            os.makedirs(output_dir)
        blob_service.get_blob_to_path(container_name, blob_name, output_path)
        print("Blob '{:s}' fetched from container '{:s}' to file '{:s}'.".format(blob_name, container_name, output_path))

def delete_blob(args):
    blob_service = get_blob_service(args)
    container_name = args.container
    blob_name = args.blob
    if(not(blob_service.exists(container_name, blob_name))):
        print("Blob '{:s}' does not exist in container '{:s}'. Skipping delete.".format(blob_name, container_name))
    else:
        blob_service.delete_blob(container_name, blob_name)
        print("Blob '{:s}' deleted from container '{:s}'.".format(blob_name, container_name))


if __name__ == "__main__":
    main()
