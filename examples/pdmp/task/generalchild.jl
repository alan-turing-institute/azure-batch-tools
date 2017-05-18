# following variables need to be set before inclusion of this script
# CHILDNAME
# LATENT_D
# SIGMA_U
# SIGMA_V
# SIGMA_R
# LAMBDAREF
# MAXNEVENTS
# MAXT

using PDMP, JLD

params = Dict(
    "CHILDNAME"  => CHILDNAME,
    "LATENT_D"   => LATENT_D,
    "SIGMA_U"    => SIGMA_U,
    "SIGMA_V"    => SIGMA_V,
    "SIGMA_R"    => SIGMA_R,
    "LAMBDAREF"  => LAMBDAREF,
    "MAXNEVENTS" => MAXNEVENTS,
    "MAXT"       => MAXT
)

start = time()

a = readdlm("data/ratings.csv", ',', Int)
R = a[:,1:3]

println("($(time()-start)s) -- read the data")

# srand(135)
latentD = LATENT_D     # dimension of latent space
sigmaU  = SIGMA_U
sigmaV  = SIGMA_V
sigmaR  = SIGMA_R

### there may be discrepancy with lines missing etc.
# -> use unique
nU = maximum(R[:,1])
nV = maximum(R[:,2])

# factors: create N factors for the users,
mvgU             = MvDiagonalGaussian(zeros(latentD), sigmaU)
gllU(x)          = gradloglik(mvgU, x)
nexteventU(x, v) = nextevent_bps(mvgU, x, v)
factorU(k)       = Factor(nexteventU, gllU, k)

allfactors = [factorU(k) for k in 1:nU]

# factors: create M factors for the movies,
mvgV             = MvDiagonalGaussian(zeros(latentD), sigmaV)
gllV(x)          = gradloglik(mvgV, x)
nexteventV(x, v) = nextevent_bps(mvgV, x, v)
factorV(k)       = Factor(nexteventV, gllV, nU+k)

allV = [factorV(k) for k in 1:nV]

push!(allfactors, allV...)

# factors: create nz(R) factors for the ratings
maskU(x) = x[1:latentD]
maskV(x) = x[latentD+1:end]

# each factor connected to its own var
structure = [[k] for k in 1:(nU+nV)]

# -----------------------------
# factors  variables
#  fU1       U1 = [1]
#  ...       ...
#  fUnU      UnU = [nU]
#  fV1       V1  = [nU+1]
#  ...       ...
#  fVnV      VnV = [1+nV]
# (for appropriate ij)
#  fRij      Ui,Vj = [i, nU+j]
# -----------------------------

for k in 1:size(R,1)
    i,j, rij = R[k,:]
    # the likelihood
    gij = PMFGaussian(rij, sigmaR, latentD)
    # the factor
    fij = Factor( (x,w)->nextevent_bps(gij,x,w),
                   x->gradloglik(gij, x),
                   nU+nV+k )
    push!(allfactors, fij)
    push!(structure, [i, j+nU])
end

fg = FactorGraph(structure, allfactors)

lambdaref  = LAMBDAREF
maxnevents = MAXNEVENTS
T          = MAXT

nvars      = nU+nV

x0 = [randn(latentD) for i in 1:nvars]
v0 = [randn(latentD) for i in 1:nvars]
v0 = map(v->v/norm(v), v0)

lsim = LocalSimulation(fg, x0, v0, T, maxnevents, lambdaref)

println("($(time()-start)s) -- created the graph + sim")

(all_evlist, details) = simulate(lsim)

println("($(time()-start)s) -- finished the simulation")

filename = "child_$(CHILDNAME).jld"
save(filename,
        "evlist", all_evlist.evl,
        "details", details,
        "params", params)

println("($(time()-start)s) -- saved the results")

resourcegroup = "mortest42"
saspath  = "secrets/azure_vm_pool_mortest42_sas_servicebus_management.txt"
pushcommand = `/usr/bin/env python az-storage.py $resourcegroup put -i $filename --sas-path $saspath`

run(pushcommand)

println("($(time()-start)s) -- pushed the results to Azure")