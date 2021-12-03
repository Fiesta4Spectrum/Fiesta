# DecentSpec

Install dependency:
```pip install --no-cache-dir -r requirements.txt```

Download repo:
```git clone https://github.com/DecentSpec/DecentSpec.git```

Launch seed node:
```python3 -m DecentSpec.Seed.seed <task_type> <port_num>```

launch miner node:
```python3 -m DecentSpec.Miner.miner <http://seed_addr:port> <http://my_addr> <my_port> <min_block_size> <max_block_size>```