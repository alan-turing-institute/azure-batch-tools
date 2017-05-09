#! python
import os
import sys
import string
import random
import uuid
import argparse

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
DEFAULT_LOCATION = 'westeurope'
DEFAULT_STORAGE_SKU = 'Standard_LRS'

# Set up some exit statuses
CLEAN_EXIT = 0
USER_EXIT = 1
ERROR_EXIT = 2

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description=__name__)
    parser.add_argument('command', choices=['create'])
    parser.add_argument('--name','-n',
        required=True,
        help='Name of batch account. If creating a new batch account, this will also be used as the name of the associated resource group and storage account that will be created.')
    args = parser.parse_args()

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
    azure_folder = get_config_dir()
    if not os.path.exists(azure_folder):
        os.makedirs(azure_folder)
    ACCOUNT.load(os.path.join(azure_folder, 'azureProfile.json'))

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

    if(args.command == 'create'):
        create(args)
    else:
        warning("Unsupported command")

def create(args):
    # Generate unique ID to use for resource group, batch account, storage
    # account names
    # TODO: Potentially tke account name as a command line argument? If so,
    # we'll need to check that the name is available for all resources required
    #account_name = generate_account_name()
    account_name = args.name
    # Check name
    if(name_valid(account_name)):
        # Create resource group, batch account and storage account
        create_batch_account_group(args.name)

def create_batch_account(name, resource_group_name, location = DEFAULT_LOCATION):
    logger.warning("Creating batch account")
    name_opt = "--name={0}".format(name)
    location_opt = "--location={0}".format(location)
    resource_group_name_opt = "--resource-group={0}".format(resource_group_name)
    return APPLICATION.execute(['batch', 'account', 'create', name_opt, location_opt, resource_group_name_opt]).result

def create_batch_account_group(name, location = DEFAULT_LOCATION):
    logger.warning("Creating resource group, batch account and storage account with name '{0}'".format(name))
    resource_group = create_resource_group(name, location)
    print("Resource group: {0}".format(resource_group))
    resource_group_name = resource_group["name"]
    batch_account = create_batch_account(name, resource_group_name, location)
    print("Batch account: {0}".format(batch_account))
    storage_account = create_storage_account(name, resource_group_name, location)
    print("Storage account: {0}".format(storage_account))
    batch_account_name = batch_account["name"]
    storage_account_name = storage_account["name"]
    link_storage_account_to_batch_account(batch_account_name, storage_account_name, resource_group_name)
    print("Batch account: {0}".format(batch_account))

def create_resource_group(name, location = DEFAULT_LOCATION):
    logger.warning("Creating resource group")
    name_opt = "--name={0}".format(name)
    location_opt = "--location={0}".format(location)
    return APPLICATION.execute(['group', 'create', name_opt, location_opt]).result

def create_storage_account(name, resource_group_name, location = DEFAULT_LOCATION, sku = DEFAULT_STORAGE_SKU):
    logger.warning("Creating storage account")
    name_opt = "--name={0}".format(name)
    location_opt = "--location={0}".format(location)
    resource_group_name_opt = "--resource-group={0}".format(resource_group_name)
    sku_opt = "--sku={0}".format(sku)
    return APPLICATION.execute(['storage', 'account', 'create', name_opt, location_opt, resource_group_name_opt, sku_opt]).result

def generate_account_name():
    return random_string(AZURE_ACCOUNT_NAME_MAX_LENGTH, AZURE_ACCOUNT_NAME_CHARSET)

def generate_password():
    return random_string(AZURE_PASSWORD_MAX_LENGTH, AZURE_PASSWORD_CHARSET)

def get_default_subscription():
    subscriptions = APPLICATION.execute(['account', 'list']).result
    default_subscription = [s for s in subscriptions if s['isDefault']][0]
    return default_subscription

def link_storage_account_to_batch_account(batch_account_name, storage_account_name, resource_group_name):
    logger.warning("Linking storage account to batch account")
    batch_account_name_opt = "--name={0}".format(batch_account_name)
    storage_account_name_opt = "--storage-account={0}".format(storage_account_name)
    resource_group_name_opt = "--resource-group={0}".format(resource_group_name)
    return APPLICATION.execute(['batch', 'account', 'set', batch_account_name_opt, storage_account_name_opt, resource_group_name_opt]).result

def is_authenticated():
    # Get subscriptions. This returns an empty list if user is not authenticated.
    subscriptions = APPLICATION.execute(['account','list']).result
    if not(subscriptions):
        return False
    else:
        return True

def login():
    APPLICATION.execute(['login'])

def name_valid(name):
    name_valid = (name_length_ok(name) and name_characters_ok(name))
    return name_valid

def name_characters_ok(name):
    valid_chars = all(c in AZURE_ACCOUNT_NAME_CHARSET for c in name)
    if not(valid_chars):
        logger.warning("Account name '{0}' contains invalid characters. Valid characters are '{1}'".format(name, AZURE_ACCOUNT_NAME_CHARSET))
    return valid_chars

def name_length_ok(name):
    name_length = len(name)
    name_length_ok = (name_length >= AZURE_ACCOUNT_NAME_MIN_LENGTH and
                        name_length <= AZURE_ACCOUNT_NAME_MAX_LENGTH)
    if not(name_length_ok):
        logger.warning("Account name '{0}' length invalid at {1} characters. Length must be between {2} and {3} characters.".format(name, name_length, AZURE_ACCOUNT_NAME_MIN_LENGTH, AZURE_ACCOUNT_NAME_MAX_LENGTH))
    return name_length_ok

def random_string(length, charset):
    return ''.join(random.SystemRandom(charset).choice(charset) for _ in range(length))

def set_default_subscription(name_or_id):
    subscription_opt = "--subscription={0}".format(name_or_id)
    APPLICATION.execute(['account', 'set', subscription_opt])

def name_available(name):
    name_available = (name_available_resource_group(name) and
                        name_available_storage(name))

def name_available_resource_group(name):
    account_name_opt = "--name={0}".format(name)
    return APPLICATION.execute(['group', 'exists', account_name_opt]).result["nameAvailable"]

def name_available_storage(name):
    account_name_opt = "--name={0}".format(name)
    return APPLICATION.execute(['storage', 'account', 'check-name', account_name_opt]).result

if __name__ == "__main__":
    main()
