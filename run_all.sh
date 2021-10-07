cd ..

# project is orgnized as a whole package, plz run the relative module the server of which you are interested in
# using xterm to open new terminal window to print log
xterm -T seednode -e    python -m DecentSpec.Seed.seed 5000 &
xterm -T miner00 -e     python -m DecentSpec.Miner.miner 8000 &
xterm -T edge00 -e      python -m DecentSpec.EdgeSim.edge &

