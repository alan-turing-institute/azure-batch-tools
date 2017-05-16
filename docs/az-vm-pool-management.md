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
  - `pip install --user azure-cli azure-queue azure-storage`


## Usage
General usage follows the pattern:

  - `python az-vm-pool.py <resource-group-name> <command> <options>`

### Create a new VM pool
`python az-vm-pool.py testpool93647 create-pool --num-vms=10 --vm-size=Standard_DS11`

The above command creates a pool of 10 VMs of size `Standard_DS11` in resource group `testpool93647`.

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

### Start all VMs in a pool
`python az-vm-pool.py testpool93647 start-all`

The above command starts all VMs in the VM pool for resource group `testpool93647`. Combine dwith the `stop-all` command, this lets you start and stop a VM pool to manage costs without needing to delete and create it each time.

### Delete a VM pool
`python az-vm-pool.py testpool93647 delete-pool`

The above command deletes the VM pool for resource group `testpool93647`. Before deletion occurs, the VMs in the pool will be listed and you will be asked to confirm the deletion. If you do not type `y` at this prompt, the deletion will be cancelled.
