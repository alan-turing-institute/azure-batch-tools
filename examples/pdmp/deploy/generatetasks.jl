### PART FOR THE USER (note the arrays)

bd = Dict(
           "LATENT_D"   => 30,
           "SIGMA_R"    => [0.5,1.0,3.0],
           "SIGMA_U"    => [10.0,15.0],
           "SIGMA_V"    => [20.0,25.0],
           "LAMBDAREF"  => [.01,.05],
           "MAXNEVENTS" => 10,
           "MAXT"       => Inf
       )

###################
### PART FOR US ### (this could be a separate script further down the line)
###################

using Iterators

sk = [k for k in keys(bd) if length(bd[k])==1]
mk = [k for k in keys(bd) if length(bd[k])>1]

basestring = ""
for k in sk
    basestring *= k * " = " * string(bd[k][1]) * "; "
end

strings = String[]

for tpl in product([bd[k] for k in mk]...)
    str = "CHILDNAME = \\\"" * randstring(12) * "\\\"; "
    str *= basestring
    for (i,k) in enumerate(mk)
        str *= k * " = " * string(tpl[i]) * "; "
    end
    push!(strings, str * "include(\\\"task/generalchild.jl\\\")")
end

taskfile = Dates.format(now(), "yyyy-mm-ddTHH-MM-SS") * "_tasks.txt"
open(taskfile,"w") do f
    for s in strings
        write(f, "julia -e \""*s*"\"\n")
    end
end

resourcegroup = "mortest42"

queuename = "tasks"
queuesaspath  = "secrets/azure_vm_pool_mortest42_sas_servicebus_management.txt"
queuecommand = `python az-queue.py $resourcegroup $queuename fill -i $taskfile --sas-path $queuesaspath`
run(queuecommand)

storagesaspath  = "secrets/azure_vm_pool_mortest42_sas_storage_container_data.txt"
storagecommand = `python az-storage.py $resourcegroup put -i $taskfile --sas-path $storagesaspath`
run(storagecommand)

rm(taskfile)
