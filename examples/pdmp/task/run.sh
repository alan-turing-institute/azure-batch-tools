#!/bin/bash
DIR=`dirname "$BASH_SOURCE"`
resourcegroup="mortest42"
queuename="tasks"
taskfile="task.txt"
while [ 1 ]
do
	eval $("/usr/bin/env python $DIR/az-queue.py $resourcegroup $queuename fetch -o $DIR/$taskfile --sas-path $DIR/secrets/azure_vm_pool_mortest42_sas_servicebus_management.txt")
	if [[ -s "$DIR/$taskfile" ]]
	then
	    task=$(cd "$DIR" && cat "$taskfile")
	    echo "Running task"
		eval "$task"
	else
		echo "No tasks to process. Exiting."
		exit
	fi
	sleep 5
done