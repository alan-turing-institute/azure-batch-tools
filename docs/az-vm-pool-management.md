# Azure virtual machine (VM) pool management
  - [az-vm-pool.py](../src/az-vm-pool.py): Python script for creating, starting, stopping and deleting pools of Azure virtual machines (VMs).

## Initial set up
### Manually set up prerequisite Azure services
Some Azure resources need to be created via the [Azure management portal](https://portal.azure.com). In the future it is hoped we can automatically create these when creating a VM pool using the `az-vm-pool.py` command line tool. Create the following Azure resources.
  - **Resource group:** Create a resource group dedicated to this pool of virtual machines
    - From the sidebar menu, navigate to 'Resource groups' -> 'Add'
    - Enter a **globally unique** resource group name. It is important that you pick a name that no other Azure user has used to name any of the resources we will be creating to support our VM pool.
    - Azure limits some resource names to lower case letters and numbers only, and some resource names cannot start with a number. Therefore start your respurce name with a letter and only use lower case letters and numbers in the name.
    - When naming VMs and VM-specific resources, we will be adding the number of the VM in the pool as a suffix to the names, with a '-' separator.  Azure limits some resource names to 24 characters, so you will need to leave enough characters to represent the maximum number of VMs you will want to create, plus one extra charter for the '-' separator. E.g. to support up to 10,000 VMs, limit your respurce group name to 19 characters, leaving 5 characters left to represent VM-specific suffixes up to '-9999' (VM numbers start at 0).
    - Set the subscription to the one you want to pay for the VM pool
    - Select a location (we suggest `westeurope` as a good copmpromise between feature availability and geographic proximity)
  - **Storage account:**
    - From the sidebar menu, navigate to 'Storage accounts' -> 'Add'
    - Set `Name` to the name of the Resource Group
    - Set `Deployment model` to `Resource manager`
    - Set `Performance` to `Standard`
    - Set `Replication` to `Locally-redundant storage (LRS)`
    - Set `Encryption` to `Disabled`
    - Set `Subscription` to the one used for the resource group
    - Set `Resource group` to the one you created above
    - Set `Location` to the location of the resource group
  - **Virtual network:**
    - From the sidebar menu, navigate to 'New (+)' -> Networking -> Virtual network and press the 'create' button
    - Set `Name` to the name of the Resource Group you created above
    - Set `Subnet name` to the name of the Resource Group you created above
    - Set `Resource group` to the one you created above
    - Set `Location` to the location of the resource group
  - **Azure Service Bus:**
    - From the sidebar menu, navigate to 'New (+)' -> Enterprise Integration -> Service bus_service
    - Set namespace `Name` to the name of the Resource Group you created above
    - Set `Pricing tier` to `Basic`
    - Set `Subscription` to the one used for the resource group
    - Set `Resource group` to the one you created above
    - Set `Location` to the location of the resource group

### Install Azure CLI and required packages on controller machine
On the desktop or laptop you will be using to manage the VM pool, install the Azure command line client and some additional Azure python libraries for managing queues and storage on Azure.
  - `pip install --user azure-cli tabulate azure-storage azure-servicebus`


## Usage
General usage follows the pattern:

  - `python az-vm-pool.py <resource-group-name> <command> <options>`

### Create a new VM pool
`python az-vm-pool.py testpool93647 create-pool --num-vms=10 --vm-size=Standard_DS11`

The above command creates a pool of 10 VMs of size `Standard_DS11` in resource group `testpool93647`.

By default, each VM is created one at a time in sequence. You can use the `--no-wait` flag to start deploying the next VM before creation of previous VMs is complete. If you do this, you must use the `show-pool` command to ensure that all VMs in the pool have a provisioning state of `Succeeded` and a power state of `VM running` prior to running any further steps in the deployment process.

### List available VM sizes
`python az-vm-pool.py testpool93647 list-sizes --min-cores=2 --max-cores=8 --min-memory=24 --max-memory=56`

The above command lists all VM sizes available in the region of resource group `testpool93647` that have between 2 and 8 cores and 24-56 GB of memory (RAM). The min and max core/memory options filter the list of VMs to meet the specified range of cores and memory, with memory limits specified in GB (gigabytes).

### Show VMs pool
`python az-vm-pool.py testpool93647 show-pool`

The above command lists all VMs in the VM pool for resource group `testpool93647`, along with their provisionin_g and power status. To run tasks on a VM, it must have a provisioning state of `Succeeded` and a power state of `VM running`. A VM incurs full usage charges unless its power state is `VM deallocated`.

### Stop all VMs in a pool
`python az-vm-pool.py testpool93647 stop-all`

The above command stops and deallocates all VMs in the VM pool for resource group `testpool93647`, which prevents any further usage charges from being incurred.

**Note:** Azure lets you `stop` or `deallocate` a VM. Stopped VMs continue to incur the same usage charges as running VMs, while deallocated VMs do not incur any usage charges. The `stop-all` command deallocates all VMs in the pool.

By default, each VM is deallocated one at a time in sequence. You can use the `--no-wait` flag to start deallocating the next VM before deallocation of previous VMs is complete. If you do this, you must use the `show-pool` command to ensure that all VMs in the pool have a provisioning state of `Succeeded` and a power state of `VM deallocated` prior to attempting to restart the pool.

### Start all VMs in a pool
`python az-vm-pool.py testpool93647 start-all`

The above command starts all VMs in the VM pool for resourceprovisioning state of `Succeeded` and a  group `testpool93647`. Combine dwith the `stop-all` command, this lets you start and stop a VM pool to manage costs without needing to delete and create it each time.

By default, each VM is started one at a time in sequence. You can use the `--no-wait` flag to start the next VM before previous VMs have finished starting. If you do this, you must use the `show-pool` command to ensure that all VMs in the pool have a provisioning state of `Succeeded` and a power state of `VM running` prior to running any further steps in the deployment process.

### Setup all VMs in a pool
`python az-vm-pool.py testpool93647 setup-pool --pool-directory=<pool-directory>`

The above command uploads the `pooldirectory/setup/` folder to each VM and then runs the `setup/run.sh` setup script.

By default each VM is setup one at a time, waiting for the setup script to finish on each VM before starting to setup the next VM. You can use the `--no-wait` flag to start running the setup script on the next VM before setting up of previous VMs is complete. In this case, the connection to each VM is dropped after the `setup/run.sh` script is started, so you need to ensure that you wait for the setup  script to finish on all VMs before starting any tasks. To see if the setup script is still running on a VM:

  - Connect via SSH using `ssh <vm-name>.<pool-location>.cloudapp.azure.com -i <path-to-pivate-ssh-key>`
  - View the output of any running setup script using `screen`: `screen -R`

### Deploy task to all VMs in a pool
`python az-vm-pool.py testpool93647 deploy-task --pool-directory=<pool-directory>`

The above command uploads the `pooldirectory/task/` folder to each VM, deleting any existing VM `task` directory before doing so. Amend the `pooldirectory/task/run.sh` script to run your task script within the task loop. The `pooldirectory/task/run.sh` script will pull new tasks from the queue, run the task script for each task and exit when the queue is empty. Your task script is responsible for uploading any output files to Azure. You should use the following command within your task script for each file you need to upload:

- `python az-storage <resource-group> put -input_path=<file-path>`

This will upload the file to a blob with the same filename in the VM pool `data` storage container.

Note that the `az-queue.py` script will pull a new task from the queue even if the task script for the previous task failed. The failed taks will not be re-run automatically.

### Queue tasks to be processed by a VM pool
`pooldirectory/deploy/run.sh`

Amend the file in `pooldirectory/deploy/run.sh` to call your own script for generating tasks and uploading them to the VM pool Azure queue. Your script should construct each task as a single string that can be executed in the bash shell on each VM. Each task should be written as a separate line to a single tasks file. You should use the following commands to add the tasks from this file to the task queue and save the task file to the VM pool `data` storage container.

- `python az-queue.py <resource-group> <queue-name> fill --input-path=<task_file_path>`
- `python az-storage <resource-group> put -input_path=<task-file-path>`

Note that any existing file of the same name will be overwritten, so it is suggested that you make the name of your task file unique each time your task generator script is run (e.g. by pre-pending a timestamp).

If you want to ensure that any tasks already existing in the queue are discarded before your newly generated tasks are added to the queue, use the following command.

- `python az-queue.py <resource-group> <queue-name> empty`

To see how many task are currently in a queue, use the following command.

- `python az-queue.py <resource-group> <queue-name> status`

## Start a task on all VMs in a pool
`python az-vm-pool.py testpool93647 start-task`

The above command runs the `task/run.sh` script on each VM before disconnecting. We use the `screen` command on the VM for this. To view the output of a running task on a VM:

  - Connect via SSH using `ssh <vm-name>.<pool-location>.cloudapp.azure.com -i <path-to-pivate-ssh-key>`
  - View the output of any running task using `screen -R`

### Kill a task on all VMs in a pool
`python az-vm-pool.py testpool93647 kill-task`

The above command kills any running tasks by killing all `screen` processes on each VM.

### Delete a VM pool
`python az-vm-pool.py testpool93647 delete-pool`

The above command deletes the VM pool for resource group `testpool93647`. Before deletion occurs, the VMs in the pool will be listed and you will be asked to confirm the deletion. If you do not type `y` at this prompt, the deletion will be cancelled.

### Get SSH keys for VM pool management
When a new VM pool is created, the public and private SSH keys used to access the VMs in the pool are uploaded to the `sshkeys` container for the pool. The following command will download the SSH keys for the VM pool for resource group `testpool93647` and save them to the `private-pool-ssh-keys` folder in the directory the `az-vm-pool.py` script is run.

- `python az-vm-pool.py testpool93647 get-ssh`

### Get VM secrets
The `az-queue.py` and `az-storage.py` scripts are deployed onto the VMs and need to authenticate to the pool `tasks` queue and the `data` pool storage container respectively. This authentication is handled by SAS tokens. The storage token will be automatically generated and uploaded when a pool is created or the `refresh-sas` command is run. For now the queue token must be the primary key of the `RootManageSharedAccessKey` of the Service Bus containing the queue. It must also be manually uploaded to the `vmsecrets` pool storage container if it is to be fetched to a new pool management computer using the `get-secrets` command. Note that the queue SAS key file must be named `azure_vm_pool_<resource-group>_sas_servicebus_management.txt`.

- `python az-vm-pool.py testpool93647 get-secrets`

### Initialise local pool directory
The`setup-pool` and `start-task` commands require a certain directory structure, with access to the VM SAS secrets as well as access to the `az-queue.py` and `az-storage.py` scripts. Generating tasks and deploying them to the pool `tasks` queue also requires this. To set up this structure and populate it with the requried scripts and secrets, use the following command.

- `python az-vm-pool.py testpool93647 init-directory --pool-directory=<pool-directory>`

This command will copy the `az-queue.py` and `az-storage.py` scripts and the `secrets` folder from the directory the `az-vm-pool.py` script is run from to the following pool directory folders.

- `<pool-directory>/deploy`
- `<pool-directory>/setup`
- `<pool-directory>/task`
