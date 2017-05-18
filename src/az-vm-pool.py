#! /usr/bin/env python

import os
import sys
import string
import random
import uuid
import argparse
import json
from datetime import datetime
from datetime import timedelta
from tabulate import tabulate
import subprocess
import os.path

from azure.cli.core.application import APPLICATION, Configuration
from azure.cli.core._session import ACCOUNT, CONFIG, SESSION
import azure.cli.core.azlogging as azlogging
from azure.cli.core._environment import get_config_dir

logger = azlogging.get_az_logger(__name__)

# Azure account name constants
AZURE_ACCOUNT_NAME_MIN_LENGTH = 3
AZURE_ACCOUNT_NAME_MAX_LENGTH = 24
AZURE_ACCOUNT_NAME_CHARSET = string.ascii_lowercase + string.digits

# Azure password constants
AZURE_PASSWORD_MAX_LENGTH = 16
AZURE_PASSWORD_ALLOWED_SPECIALS = '@#$%^&*-_!+=[]{}|\\:,.?/`~()'
AZURE_PASSWORD_CHARSET = string.ascii_lowercase + string.ascii_uppercase + string.digits + AZURE_PASSWORD_ALLOWED_SPECIALS

# Some defaults
DEFAULT_SSH_KEY_DIRECTORY = 'private-pool-ssh-keys'
DEFAULT_SAS_DIRECTORY = 'secrets'
DEFAULT_VM_IMAGE = 'canonical:UbuntuServer:16.04-LTS:16.04.201703300'
DEFAULT_OS_CONTAINER_NAME = "vhds"
DEFAULT_DATA_CONTAINER_NAME = "data"
DEFAULT_CONTAINER_SAS_PREFIX = "sas_storage_container"
DEFAULT_SAS_EXPIRY_DAYS = 14
DEFAULT_POOL_FILE_PREFIX = "azure_vm_pool"
SETUP_DIRECTORY = "setup"
DEPLOY_DIRECTORY = "deploy"
TASK_DIRECTORY = "task"
SETUP_SCRIPT = "run.sh"
DEPLOY_SCRIPT = "run.sh"
TASK_SCRIPT = "run.sh"

# Set up some exit statuses
CLEAN_EXIT = 0
USER_EXIT = 1
ERROR_EXIT = 2

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description=__name__)
    parser.add_argument('resource_group',
        help='Name of VM pool resource group.')
    parser.add_argument('command', choices=['list-sizes', 'create-pool', 'delete-pool', 'show-pool', 'setup-pool', 'start-all', 'stop-all', 'deploy-task', 'start-task', 'kill-task', 'refresh-sas'])
    parser.add_argument('--num-vms', '-n', type=int,
        help='Number of VMs to create in pool.')
    parser.add_argument('--vm-size', '-s',
        help='Size of VM.')
    parser.add_argument('--min-cores',
        type=int, default=0,
        help="Restrict VM size list to VMs with a minimum number of cores.")
    parser.add_argument('--max-cores',
        type=int, default=float('inf'),
        help="Restrict VM size list to VMs with a maxmimum number of cores.")
    parser.add_argument('--min-memory',
        type=int, default=0,
        help="Restrict VM size list to VMs with a minimum amount of memory (specified in GB).")
    parser.add_argument('--max-memory',
        type=int, default=float('inf'),
        help="Restrict VM size list to VMs with a maximum amount of memory (specified in GB).")
    parser.add_argument("--sas-expiry-days", type=int,
        default = DEFAULT_SAS_EXPIRY_DAYS,
        help="Number of days the generated Shared Access Signature (SAS) access code for the VM pool storage container should be valid for.")
    parser.add_argument("--pool-directory", "-d",
        default = ".",
        help="Directory containing 'setup', 'deploy' and 'task' directories for the pool.")

    args = parser.parse_args()

    # Add some default arguments that we won't clutter up the command line with
    args.ssh_key_directory = DEFAULT_SSH_KEY_DIRECTORY
    args.sas_directory = DEFAULT_SAS_DIRECTORY
    args.vm_image = DEFAULT_VM_IMAGE
    args.os_container_name = DEFAULT_OS_CONTAINER_NAME
    args.data_container_name = DEFAULT_DATA_CONTAINER_NAME
    args.container_sas_prefix = DEFAULT_CONTAINER_SAS_PREFIX
    args.pool_file_prefix = DEFAULT_POOL_FILE_PREFIX
    args.setup_directory = SETUP_DIRECTORY
    args.deploy_directory = DEPLOY_DIRECTORY
    args.task_directory = TASK_DIRECTORY
    args.setup_script = SETUP_SCRIPT
    args.deploy_script = DEPLOY_SCRIPT
    args.task_script = TASK_SCRIPT

    azlogging.configure_logging("")

    # We use the Azure CLI 2.0 APPLICATION object to let us call functionality
    # in exactly the same manner as calling the 'az' app from the terminal. We
    # just pass an array of arguments to APPLICATION.execute(), get the output
    # from the 'result' field and assign it to a variable for further processing
    # e.g. apps = APPLICATION.execute(['ad', app', 'list']).result

    # Set up various configuration variables.
    # NOTE: Even though credential caching is not explicitly set up here, and
    # cached credentials are stored in 'accessTokens.json' rather than
    # 'azureProfile.json', ACCOUNT.load(os.path.join(azure_folder,
    # 'azureProfile.json')) is required for credential caching to work.
    azure_dir = get_config_dir()
    ensure_exists(azure_dir)
    ACCOUNT.load(os.path.join(azure_dir, 'azureProfile.json'))

    # Configure APPLICATION
    APPLICATION.initialize(Configuration())

    # Check if user has already authenticated. If not, get user to interactively authenticate
    if not(is_authenticated()):
        login()

    # We will use the default subscription for everything. To change the
    # default subscription, use set_default_subscription(name_or_id). This
    # changes the default subscription for this session only.
    # TODO: Take subscription as a commandline argument
    subscription = get_default_subscription()
    logger.warning("Using default subscription ({0} / {1})".format(subscription["name"], subscription["id"]))
    args.subscription = subscription

    if(args.command == 'show-pool'):
        show_pool(args)
    elif(args.command == 'list-sizes'):
        list_sizes(args)
    elif(args.command == 'create-pool'):
        create_pool(args)
    elif(args.command == 'setup-pool'):
        setup_pool(args)
    elif(args.command == 'start-all'):
        start_all(args)
    elif(args.command == 'stop-all'):
        shutdown_all(args)
    elif(args.command == 'deploy-task'):
        deploy_task(args)
    elif(args.command == 'start-task'):
        start_task(args)
    elif(args.command == 'kill-task'):
        kill_task(args)
    elif(args.command == 'delete-pool'):
        delete_pool(args)
    elif(args.command == 'refresh-sas'):
        refresh_sas(args)
    else:
        logger.warning("Unsupported command")

## --------------------------------
## AUTHENTICATION / LOGIN / ACCOUNT
## --------------------------------
def is_authenticated():
    # Get subscriptions. This returns an empty list if user is not authenticated.
    subscriptions = APPLICATION.execute(['account','list']).result
    if not(subscriptions):
        return False
    else:
        return True

def login():
    APPLICATION.execute(['login'])

def get_default_subscription():
    subscriptions = APPLICATION.execute(['account', 'list']).result
    default_subscription = [s for s in subscriptions if s['isDefault']][0]
    return default_subscription

## ----------------
## HELPER FUNCTIONS
## ----------------
def print_json(json_obj):
    print(json.dumps(json_obj, sort_keys=True, indent=2, separators=(',',':')))

def print_vm_list(vm_list_json, args):
    print("VMs in Resource Group '{0}':".format(args.resource_group))
    index = 0
    for vm in vm_list_json:
        index = index + 1
        print("-------".format(index))
        print("VM #{:d}".format(index))
        print("-------".format(index))
        print("Name: {0}".format(vm["name"]))
        print("ID: {0}".format(vm["vmId"]))
        print("Size: {0}".format(vm["hardwareProfile"]["vmSize"]))
        print("OS image: {0}".format(vm_image_string(vm["storageProfile"]["imageReference"])))
        print("Location: {0}".format(vm["location"]))
        print("Provisioning state: {0}".format(vm["provisioningState"]))
        print("Power state: {0}".format(vm["powerState"]))
        print(vm.powerState)

def print_vm_table(vm_list_json, args):
    print("VMs in Resource Group '{0}':".format(args.resource_group))
    headers = ["Name", "Location", "Size", "Provisioning", "Power state"]
    rows = [[
        vm["name"],
        vm["location"],
        vm["hardwareProfile"]["vmSize"],
        vm["provisioningState"],
        vm["powerState"]
        ] for vm in vm_list_json]
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))

def print_vm_size_table(vm_size_list_json, args):
    print("VM sizes available for Resource Group '{0}':".format(args.resource_group))
    headers = ["Name", "Cores", "Memory (GB)", "OS disk (GB)", "Resource disk (GB)", "Max disks"]
    rows = [[
        vm["name"],
        vm["numberOfCores"],
        vm["memoryInMb"]/1024.0,
        vm["osDiskSizeInMb"]/1024.0,
        vm["resourceDiskSizeInMb"]/1024.0,
        vm["maxDataDiskCount"]
        ] for vm in vm_size_list_json
            if vm["numberOfCores"] >= args.min_cores and
                vm["numberOfCores"] <= args.max_cores and
                vm["memoryInMb"]/1024.0 >= args.min_memory and
                vm["memoryInMb"]/1024.0 <= args.max_memory]
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))

def vm_image_string(image_json):
    return "{0}:{1}:{2}:{3}".format(image_json["publisher"], image_json["offer"], image_json["sku"], image_json["version"])

def get_vms(args):
    power_state_opt = "--show-details"
    vms = vm_pool_command(["vm", "list"], [power_state_opt], args)
    #vms = APPLICATION.execute(["vm", "list", power_state_opt]).result
    return(vms)

def vm_pool_command(command_list, option_list, args):
    # Wrapper function for calls to APPLICATION.execute() that ensures
    # that we only operate on resopurces within a single specified
    # resource group and that we always return the result field
    resource_group_opt = "--resource-group={0}".format(args.resource_group)
    option_list.append(resource_group_opt)
    command_list = command_list + option_list
    return APPLICATION.execute(command_list).result

def timedelta_string(time_delta):
    total_seconds = (time_delta.days * 24 * 3600) + time_delta.seconds
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "{:02d}h{:02d}m{:02d}s".format(hours, minutes, seconds)

def number_from_name(vm_name):
    stem, number = vm_name.split("-")
    return int(number)

def name_from_number(number, args):
    return "{0}-{1}".format(args.resource_group, number)

def next_vm_name(vms, args):
    vm_numbers = sorted([vm_number_from_name(vm["name"]) for vm in vms])
    for vm_number in vm_numbers:
        if(vm_numbers.index(vm_number) != vm_number):
            return name_from_number(vm_number - 1, args)
    return name_from_number(len(vm_numbers) + 1, args)

def ssh_private_key_filename(args):
    return "{:s}_{:s}".format(args.pool_file_prefix, args.resource_group)

def ssh_public_key_filename(args):
    return "{:s}.pub".format(ssh_private_key_filename(args))

def ssh_private_key_path(args):
    return os.path.join(args.ssh_key_directory, ssh_private_key_filename(args))

def ssh_public_key_path(args):
    return os.path.join(args.ssh_key_directory, ssh_public_key_filename(args))

def gen_ssh_keys(args):
    ensure_exists(args.ssh_key_directory)
    ssh_key_path = ssh_private_key_path(args)
    ssh_key_filename_opt = "-f{0}".format(ssh_key_path)
    ssh_type_opt = "-trsa"
    result = subprocess.call(["ssh-keygen", ssh_type_opt, ssh_key_filename_opt], stderr=subprocess.STDOUT)
    if(result != 0):
        logger.warning("Did not create new SSH key pair for new VM pool.")

def get_resource_group_location(args):
    resource_group_opt = "--name={0}".format(args.resource_group)
    resource_group = APPLICATION.execute(["group", "show", resource_group_opt]).result
    return(resource_group["location"])

def public_ip_exists(ip_name, args):
    name_opt = "--name={0}".format(ip_name)
    commands = ["network", "public-ip", "show"]
    options = [name_opt]
    result = vm_pool_command(commands, options, args)
    if(result == None):
        return False
    else:
        return True

def create_public_ip(ip_name, args):
    name_opt = "--name={0}".format(ip_name)
    location_opt = "--location={0}".format(get_resource_group_location(args))
    dns_name_opt = "--dns-name={0}".format(ip_name)
    commands = ["network", "public-ip", "create"]
    options = [name_opt, location_opt, dns_name_opt]
    result = vm_pool_command(commands, options, args)
    return(result)

def delete_public_ip(ip_name, args):
    name_opt = "--name={0}".format(ip_name)
    commands = ["network", "public-ip", "delete"]
    options = [name_opt]
    result = vm_pool_command(commands, options, args)
    return(result)

def nic_exists(nic_name, args):
    name_opt = "--name={0}".format(nic_name)
    commands = ["network", "nic", "show"]
    options = [name_opt]
    result = vm_pool_command(commands, options, args)
    if(result == None):
        return False
    else:
        return True

def create_nic(nic_name, args):
    vnet_name = args.resource_group
    subnet_name = vnet_name
    public_ip_name = nic_name
    name_opt = "--name={0}".format(nic_name)
    location_opt = "--location={0}".format(get_resource_group_location(args))
    vnet_name_opt = "--vnet-name={0}".format(vnet_name)
    subnet_opt = "--subnet={0}".format(subnet_name)
    public_ip_opt = "--public-ip-address={0}".format(public_ip_name)
    commands = ["network", "nic", "create"]
    options = [name_opt, location_opt, vnet_name_opt, subnet_opt, public_ip_opt]
    result = vm_pool_command(commands, options, args)
    return(result)

def delete_nic(nic_name, args):
    name_opt = "--name={0}".format(nic_name)
    commands = ["network", "nic", "delete"]
    options = [name_opt]
    result = vm_pool_command(commands, options, args)
    return(result)

def vm_os_disk_blob_exists(vm_name, args):
    blob_name = vm_os_disk_name(vm_name, args)
    container_name = pool_os_container_name(args)
    connection_string = pool_storage_account_connection_string(args)
    name_opt = "--name={0}".format(blob_name)
    container_name_opt = "--container-name={0}".format(container_name)
    connection_string_opt = "--connection-string={0}".format(connection_string)
    commands = ["storage", "blob", "exists"]
    options = [name_opt, container_name_opt, connection_string_opt]
    return APPLICATION.execute(commands + options).result["exists"]

def delete_vm_os_disk_blob(vm_name, args):
    blob_name = vm_os_disk_name(vm_name, args)
    container_name = pool_os_container_name(args)
    connection_string = pool_storage_account_connection_string(args)
    name_opt = "--name={0}.vhd".format(blob_name)
    container_name_opt = "--container-name={0}".format(container_name)
    connection_string_opt = "--connection-string={0}".format(connection_string)
    commands = ["storage", "blob", "delete"]
    options = [name_opt, container_name_opt, connection_string_opt]
    result = APPLICATION.execute(commands + options).result

def vm_os_disk_name(vm_name, args):
    return "{0}_os_disk".format(vm_name)

def pool_os_container_name(args, with_extension = False):
    return "{:s}".format(args.os_container_name)

def pool_data_container_name(args):
    return "{:s}".format(args.data_container_name)

def create_pool_data_container(args):
    connection_string = pool_storage_account_connection_string(args)
    storage_container_name = pool_data_container_name(args)
    container_name_opt = "--name={0}".format(storage_container_name)
    connection_string_opt = "--connection-string={0}".format(connection_string)
    commands = ["storage", "container", "create"]
    options = [container_name_opt, connection_string_opt]
    result = APPLICATION.execute(commands + options)

def delete_pool_os_container(args):
    # Get Storage account connection string to authenticate container delete
    connection_string = pool_storage_account_connection_string(args)
    # Delete storage container containing virtual hard drives for pool OS disks
    storage_container_name = pool_os_container_name(args)
    container_name_opt = "--name={0}".format(storage_container_name)
    connection_string_opt = "--connection-string={0}".format(connection_string)
    commands = ["storage", "container", "delete"]
    options = [container_name_opt, connection_string_opt]
    result = APPLICATION.execute(commands + options).result

def container_sas_filename(container_name, args):
    return "{:s}_{:s}_{:s}_{:s}.txt".format(args.pool_file_prefix, args.resource_group, args.container_sas_prefix, container_name)

def pool_storage_account_connection_string(args):
    storage_account_name = args.resource_group
    account_name_opt = "--name={0}".format(storage_account_name)
    commands = ["storage", "account", "show-connection-string"]
    options = [account_name_opt]
    return vm_pool_command(commands, options, args)["connectionString"]

def pool_data_container_sas(args):
    container_name = pool_data_container_name(args)
    connection_string = pool_storage_account_connection_string(args)
    name_opt = "--name={0}".format(container_name)
    connection_string_opt = "--connection-string={0}".format(connection_string)
    permissions_opt = "--permissions=lrwd"
    https_opt = "--https-only"
    expiry_datetime = datetime.utcnow() + timedelta(days = args.sas_expiry_days)
    expiry_opt = "--expiry={:%Y-%m-%dT%H:%MZ}".format(expiry_datetime)
    commands = ["storage", "container", "generate-sas"]
    options = [name_opt, connection_string_opt, permissions_opt, https_opt, expiry_opt]
    result = APPLICATION.execute(commands + options).result
    ensure_exists(args.sas_directory)
    filepath = os.path.join(args.sas_directory, container_sas_filename(container_name, args))
    with open(filepath, 'w+') as f:
        f.write(result)
        logger.warning("New SAS token for pool data container '{:s}' written to '{:s}'. SAS token exires on {:%Y-%m-%dT%H:%MZ}.".format(container_name, filepath, expiry_datetime))
    return result

def vm_url(vm, args):
    return("{:s}.{:s}.cloudapp.azure.com".format(vm["name"], vm["location"]))

def vm_run_script(vm, script, args, detach=False):
    ssh_key_opt = "{:s}".format(ssh_private_key_path(args))
    host_opt = "{:s}".format(vm_url(vm, args))
    if(detach):
        script_opt = "screen -d -m {:s}".format(script)
    else:
        script_opt = script
    command = ["ssh", host_opt, "-i", ssh_key_opt, script_opt]
    result = subprocess.call(command, stderr=subprocess.STDOUT)
    return(result == 0)

def local_run_script(script, args):
    command = [script]
    result = subprocess.call(command, stderr=subprocess.STDOUT)
    return(result == 0)

def local_make_exec(script, args):
    command = ["chmod", "+x", script]
    result = subprocess.call(command, stderr=subprocess.STDOUT)
    return(result == 0)

def vm_make_exec(vm, script, args):
    exec_script = "chmod +x {:s}".format(script)
    return(vm_run_script(vm, exec_script, args))

def vm_upload_dir(vm, source_dir, dest_dir, args):
    ssh_key_opt = "{:s}".format(ssh_private_key_path(args))
    source_opt = source_dir
    dest_opt = "{:s}:{:s}".format(vm_url(vm, args) ,dest_dir)
    command = ["scp", "-i", ssh_key_opt, "-r", source_opt, dest_opt]
    # First remove directory if it exists already
    remove_dir_script = "rm -r {:s}".format(dest_dir)
    vm_run_script(vm, remove_dir_script, args)
    result = subprocess.call(command, stderr=subprocess.STDOUT)
    return(result == 0)

def ensure_exists(directory):
    if(directory and not os.path.exists(directory)):
        os.makedirs(directory)

## ------------------
## TOP-LEVEL COMMANDS
## ------------------
def list_sizes(args):
    location_opt = "--location={0}".format(get_resource_group_location(args))
    result = APPLICATION.execute(["vm", "list-sizes", location_opt]).result
    print_vm_size_table(result, args)

def create_pool(args):
    vms = get_vms(args)
    num_existing_vms = len(vms)
    if(num_existing_vms > 0):
        print_vm_table(vms, args)
        logger.warning("VM pool already exists containing the above VMs. Use 'delete-pool' command to remove this pool before creating a new pool.")
    else:
        start_time = datetime.now()
        logger.warning("{:%Hh%Mm%Ss}: Creating pool of {:d} VMs for Resource Group '{:s}'.".format(datetime.now(), args.num_vms, args.resource_group))
        gen_ssh_keys(args)
        logger.warning("{:%Hh%Mm%Ss}: Creating pool data container '{:s}' if it doesn't already exist.".format(datetime.now(), pool_data_container_name(args)))
        create_pool_data_container(args)
        result = [create_vm(i, args) for i in range(0, args.num_vms)]
        # Refresh VMs and print pool  info
        vms = get_vms(args)
        print_vm_table(vms, args)
        logger.warning("{:%Hh%Mm%Ss}: Pool of {:d} VMs for Resource Group '{:s}' created in {:s}.".format(datetime.now(), args.num_vms, args.resource_group, timedelta_string(datetime.now() - start_time)))

def create_vm(vm_number, args):
    # Set VM name from number and use VM name to name IP and NIC resources
    vm_name = name_from_number(vm_number, args)
    ip_name = vm_name
    nic_name = vm_name
    os_disk_name = vm_os_disk_name(vm_name, args)
    storage_account_name = args.resource_group
    os_container_name = pool_os_container_name(args)
    # Start the clock for timing VM creation
    start_time = datetime.now()
    # Create public IP address
    if(not(public_ip_exists(ip_name, args))):
        logger.warning("{:%Hh%Mm%Ss}: Creating Public IP '{:s}'.".format(datetime.now(), ip_name))
        create_public_ip(ip_name, args)
    else:
        logger.warning("{:%Hh%Mm%Ss}: Public IP '{:s}' already exists. Skipping create.".format(datetime.now(), ip_name))
    # Create Network Interface Card (NIC)
    if(not(nic_exists(nic_name, args))):
        logger.warning("{:%Hh%Mm%Ss}: Creating NIC '{:s}'.".format(datetime.now(), nic_name))
        create_nic(nic_name, args)
    else:
        logger.warning("{:%Hh%Mm%Ss}: NIC '{:s}' already exists. Skipping create.".format(datetime.now(), nic_name))
    # Delete any existing OS disk storage blob
    if(vm_os_disk_blob_exists(vm_name, args)):
        logger.warning("{:%Hh%Mm%Ss}: Deleting existing OS disk blob '{:s}'".format(datetime.now(), os_disk_name))
        delete_vm_os_disk_blob(vm_name, args)
    # Set up VM creation options
    name_opt = "--name={0}".format(vm_name)
    ssh_opt = "--ssh-key-value={0}".format(ssh_public_key_path(args))
    image_opt = "--image={0}".format(args.vm_image)
    location_opt = "--location={0}".format(get_resource_group_location(args))
    size_opt = "--size={0}".format(args.vm_size)
    nics_opt = "--nics={0}".format(nic_name)
    unmanaged_opt = "--use-unmanaged-disk"
    storage_account_opt = "--storage-account={0}".format(storage_account_name)
    storage_container_opt = "--storage-container-name={0}".format(os_container_name)
    os_disk_name_opt = "--os-disk-name={0}".format(os_disk_name)
    # Construct commands and options
    commands = ["vm", "create"]
    options = [name_opt, ssh_opt, image_opt, location_opt, size_opt, nics_opt, unmanaged_opt, storage_account_opt, storage_container_opt, os_disk_name_opt]
    # Create VM
    logger.warning("{:%Hh%Mm%Ss}: Creating VM '{:s}'.".format(datetime.now(), vm_name))
    result = vm_pool_command(commands, options, args)
    logger.warning("{:%Hh%Mm%Ss}: VM '{:s}' created in {:s}".format(datetime.now(), vm_name, timedelta_string(datetime.now() - start_time)))
    return(result)

def setup_pool(args):
    vms = get_vms(args)
    num_vms = len(vms)
    if(num_vms == 0):
        print_vm_table(vms, args)
        logger.warning("No VM pool exists. Use 'create-pool' command to create a new pool.")
    else:
        start_time = datetime.now()
        logger.warning("{:%Hh%Mm%Ss}: Initiating setup for pool of {:d} VMs for Resource Group '{:s}'.".format(datetime.now(), num_vms, args.resource_group))
        result = [setup_vm(vm, args) for vm in vms]
        logger.warning("{:%Hh%Mm%Ss}: Setup initiated for pool of {:d} VMs for Resource Group '{:s}' in {:s}.".format(datetime.now(), num_vms, args.resource_group, timedelta_string(datetime.now() - start_time)))

def setup_vm(vm, args):
    vm_name = vm["name"]
    source_dir = os.path.join(args.pool_directory, args.setup_directory)
    dest_dir = args.setup_directory
    setup_script = os.path.join(dest_dir, args.setup_script)
    # Copy setup directory to VM
    logger.warning("Copying setup directory '{:s}' to directory '{:s}' on VM '{:s}'.".format(source_dir, dest_dir, vm_name))
    success = vm_upload_dir(vm, source_dir, dest_dir, args)
    if(success):
        logger.warning("Successfully copied setup directory '{:s}' to directory '{:s}' on VM '{:s}'.".format(source_dir, dest_dir, vm_name))
    else:
        logger.warning("Failed to copy setup directory '{:s}' to directory '{:s}' on VM '{:s}'.".format(source_dir, dest_dir, vm_name))
    # Make setup script executable
    success = vm_make_exec(vm, setup_script, args)
    # Run setup script
    success = vm_run_script(vm, setup_script, args, detach=True)
    if(success):
        logger.warning("Successfully initiated setup script '{:s}' on VM '{:s}'.".format(setup_script, vm_name))
    else:
        logger.warning("Failed to initiate setup script '{:s}' on VM '{:s}'.".format(setup_script, vm_name))

def deploy_task(args):
    vms = get_vms(args)
    num_vms = len(vms)
    if(num_vms == 0):
        print_vm_table(vms, args)
        logger.warning("No VM pool exists. Use 'create-pool' command to create a new pool.")
    else:
        start_time = datetime.now()
        # Kill any running task
        kill_task(args)
        # Copy task to VMs
        logger.warning("{:%Hh%Mm%Ss}: Deploying task to pool of {:d} VMs for Resource Group '{:s}'.".format(datetime.now(), num_vms, args.resource_group))
        result = [deploy_task_vm(vm, args) for vm in vms]
        logger.warning("{:%Hh%Mm%Ss}: Task deployed to pool of {:d} VMs for Resource Group '{:s}' in {:s}. Fill the 'tasks' queue and then run 'start-task' to run the task.".format(datetime.now(), num_vms, args.resource_group, timedelta_string(datetime.now() - start_time)))

def deploy_task_vm(vm, args):
    vm_name = vm["name"]
    task_source_dir = os.path.join(args.pool_directory, args.task_directory)
    task_dest_dir = args.task_directory
    task_script = os.path.join(task_dest_dir, args.task_script)
    # Copy task directory to VM
    logger.warning("Copying task directory '{:s}' to directory '{:s}' on VM '{:s}'.".format(task_source_dir, task_dest_dir, vm_name))
    success = vm_upload_dir(vm, task_source_dir, task_dest_dir, args)
    if(success):
        logger.warning("Successfully copied setup directory '{:s}' to directory '{:s}' on VM '{:s}'.".format(task_source_dir, task_dest_dir, vm_name))
    else:
        logger.warning("Failed to copy setup directory '{:s}' to directory '{:s}' on VM '{:s}'.".format(task_source_dir, task_dest_dir, vm_name))

def start_task(args):
    vms = get_vms(args)
    num_vms = len(vms)
    if(num_vms == 0):
        print_vm_table(vms, args)
        logger.warning("No VM pool exists. Use 'create-pool' command to create a new pool.")
    else:
        start_time = datetime.now()
        logger.warning("{:%Hh%Mm%Ss}: Starting task on pool of {:d} VMs for Resource Group '{:s}'.".format(datetime.now(), num_vms, args.resource_group))
        result = [start_task_vm(vm, args) for vm in vms]
        logger.warning("{:%Hh%Mm%Ss}: Task started on pool of {:d} VMs for Resource Group '{:s}' in {:s}.".format(datetime.now(), num_vms, args.resource_group, timedelta_string(datetime.now() - start_time)))

def start_task_vm(vm, args):
    task_dest_dir = args.task_directory
    task_script = os.path.join(task_dest_dir, args.task_script)
    vm_name = vm["name"]
    # Make task script executable
    success = vm_make_exec(vm, task_script, args)
    # Run task script
    success = vm_run_script(vm, task_script, args, detach=True)
    if(success):
        logger.warning("Successfully started script '{:s}' on VM '{:s}'.".format(task_script, vm_name))
    else:
        logger.warning("Failed to start script '{:s}' on VM '{:s}'.".format(task_script, vm_name))

def kill_task(args):
    vms = get_vms(args)
    num_vms = len(vms)
    if(num_vms == 0):
        print_vm_table(vms, args)
        logger.warning("No VM pool exists. Use 'create-pool' command to create a new pool.")
    else:
        start_time = datetime.now()
        # Kill task on all poll VMs
        logger.warning("{:%Hh%Mm%Ss}: Killing task on pool of {:d} VMs for Resource Group '{:s}'.".format(datetime.now(), num_vms, args.resource_group))
        result = [kill_task_vm(vm, args) for vm in vms]
        logger.warning("{:%Hh%Mm%Ss}: Task killed on pool of {:d} VMs for Resource Group '{:s}' in {:s}.".format(datetime.now(), num_vms, args.resource_group, timedelta_string(datetime.now() - start_time)))

def kill_task_vm(vm, args):
    vm_name = vm["name"]
    # Run script to kill anything running in screen
    kill_script = "killall screen"
    success = vm_run_script(vm, kill_script, args)
    if(success):
        logger.warning("Successfully killed task on VM '{:s}'.".format(vm_name))
    else:
        logger.warning("Failed to kill task on VM '{:s}'.".format( vm_name))

def show_pool(args):
    vms = get_vms(args)
    print_vm_table(vms, args)

def start_all(args):
    vms = get_vms(args)
    num_vms = len(vms)
    start_time = datetime.now()
    logger.warning("{:%Hh%Mm%Ss}: Starting pool of {:d} VMs for Resource Group '{:s}'.".format(datetime.now(), num_vms, args.resource_group))
    result = [start_vm(vm, args) for vm in vms]
    vms = get_vms(args)
    print_vm_table(vms, args)
    logger.warning("{:%Hh%Mm%Ss}: Pool of {:d} VMs for Resource Group '{:s}' started in {:s}.".format(datetime.now(), num_vms, args.resource_group, timedelta_string(datetime.now() - start_time)))
    return result

def start_vm(vm, args):
    if(vm["powerState"] == "VM running"):
        logger.warning("VM '{0}' already running.".format(vm["name"]))
        return
    else:
        start_time = datetime.now()
        logger.warning("{:%Hh%Mm%Ss}: Starting VM '{:s}'.".format(datetime.now(), vm["name"]))
        name_opt = "--name={0}".format(vm["name"])
        result = vm_pool_command(["vm", "start"],[name_opt], args)
        logger.warning("{:%Hh%Mm%Ss}: VM '{:s}' started in {:s}".format(datetime.now(), vm["name"], timedelta_string(datetime.now() - start_time)))
        return(result)

def shutdown_all(args):
    vms = get_vms(args)
    num_vms = len(vms)
    start_time = datetime.now()
    logger.warning("{:%Hh%Mm%Ss}: Stopping pool of {:d} VMs for Resource Group '{:s}'.".format(datetime.now(), num_vms, args.resource_group))
    result = [shutdown_vm(vm, args) for vm in vms]
    vms = get_vms(args)
    print_vm_table(vms, args)
    logger.warning("{:%Hh%Mm%Ss}: Pool of {:d} VMs for Resource Group '{:s}' stopped in {:s}.".format(datetime.now(), num_vms, args.resource_group, timedelta_string(datetime.now() - start_time)))
    return(result)

def shutdown_vm(vm, args):
    if(vm["powerState"] == "VM deallocated"):
        logger.warning("VM '{0}' already deallocated.".format(vm["name"]))
        return
    else:
        start_time = datetime.now()
        logger.warning("{:%Hh%Mm%Ss}: Deallocating VM '{:s}'.".format(datetime.now(), vm["name"]))
        name_opt = "--name={0}".format(vm["name"])
        result = vm_pool_command(["vm", "deallocate"],[name_opt], args)
        logger.warning("{:%Hh%Mm%Ss}: VM '{:s}' deallocated in {:s}".format(datetime.now(), vm["name"], timedelta_string(datetime.now() - start_time)))
        return(result)

def delete_pool(args):
    vms = get_vms(args)
    print_vm_table(vms, args)
    num_vms = len(vms)
    if(num_vms == 0):
        logger.warning("No VMs in pool.")
        return
    resp = raw_input("Are you sure you want to delete all {0} of the above VMs? (y/n):".format(num_vms))
    if(resp == "y"):
        start_time = datetime.now()
        logger.warning("{:%Hh%Mm%Ss}: Deleting pool of {:d} VMs for Resource Group '{:s}'.".format(datetime.now(), num_vms, args.resource_group))
        result = [delete_vm(vm, args, force=True) for vm in vms]
        # Delete storage container for VM OS disk vhds
        logger.warning("{:%Hh%Mm%Ss}: Deleting VM pool OS disk storage container '{:s}'.".format(datetime.now(), pool_os_container_name(args)))
        delete_pool_os_container(args)
        # Refresh VM list and show end status
        vms = get_vms(args)
        print_vm_table(vms, args)
        logger.warning("{:%Hh%Mm%Ss}: Pool of {:d} VMs for Resource Group '{:s}' deleted in {:s}.".format(datetime.now(), num_vms, args.resource_group, timedelta_string(datetime.now() - start_time)))
        return(result)
    else:
        logger.warning("Pool delete cancelled.")

def delete_vm(vm, args, force):
    vm_name = vm["name"]
    start_time = datetime.now()
    logger.warning("{:%Hh%Mm%Ss}: Deleting VM '{:s}'.".format(datetime.now(), vm_name))
    name_opt = "--name={0}".format(vm_name)
    vm_opts = [name_opt]
    if(force):
        vm_opts.append("--yes")
    # Delete VM
    result = vm_pool_command(["vm", "delete"],vm_opts, args)
    # Delete NIC and Public IP address
    logger.warning("{:%Hh%Mm%Ss}: Deleting NIC '{:s}'.".format(datetime.now(), vm_name))
    vm_pool_command(["network", "nic", "delete"], [name_opt], args)
    logger.warning("{:%Hh%Mm%Ss}: Deleting Public IP '{:s}'.".format(datetime.now(), vm_name))
    vm_pool_command(["network", "public-ip", "delete"], [name_opt], args)
    logger.warning("{:%Hh%Mm%Ss}: Deleting OS disk blob '{:s}'.".format(datetime.now(), vm_name))
    delete_vm_os_disk_blob(vm_name, args)
    logger.warning("{:%Hh%Mm%Ss}: VM '{:s}' deleted in {:s}".format(datetime.now(), vm_name, timedelta_string(datetime.now() - start_time)))
    return(result)

def refresh_sas(args):
    pool_data_container_sas(args)

if __name__ == "__main__":
    main()
