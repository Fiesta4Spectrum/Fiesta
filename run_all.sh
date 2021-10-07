cd ..

xterm -T seednode -e python -m DecentSpec.Seed.seed 5000 &
xterm -T edge00 -e python -m DecentSpec.EdgeSim.edge &

