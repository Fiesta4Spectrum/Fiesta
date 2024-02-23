# Fiesta

Install dependency:
```
pip install --no-cache-dir -r requirements.txt
```

Download repo:
```
git clone https://github.com/Fiesta4Spectrum/Fiesta
```

Launch seed node, Fiesta repo should be inside of the current directory:
```
python3 -m Fiesta.Seed.seed <task_type> <port_num>
```

launch miner node, Fiesta repo should be inside of the current directory:
```
python3 -m Fiesta.Miner.miner <http://seed_addr:port> <http://my_addr> <my_port> <min_block_size> <max_block_size>
```
