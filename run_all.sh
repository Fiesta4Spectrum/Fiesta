cd ..

# project is orgnized as a whole package, plz run the relative module the server of which you are interested in
# using xterm to open new terminal window to print log
xterm -T seednode -e    python -m DecentSpec.Seed.seed 5000 &
sleep 1     # to make sure we have seed online

xterm -T miner0 -e     python -m DecentSpec.Miner.miner http://api.decentspec.org 8000 &
xterm -T miner1 -e     python -m DecentSpec.Miner.miner http://api.decentspec.org 8001 &
xterm -T miner2 -e     python -m DecentSpec.Miner.miner http://api.decentspec.org 8002 &
sleep 1     # to make sure we have miner and seed online

xterm -T edge0 -e      python -m DecentSpec.EdgeSim.edge &

cd DecentSpec