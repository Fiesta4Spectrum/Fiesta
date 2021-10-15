import sys
import random
import string
import os

'''
useage:
    python gen_test.py {1} {2} {3} {4} {5}
    {1} - int, num of miner
    {2} - int, num of edge device
    {3} - float, percentage of test set 
    {4} - int, num of fl round
    {5} - POOL_MINE_THRESHOLD
'''

def genName(num=5):
    salt = ''.join(random.sample(string.ascii_letters + string.digits, num))
    return salt

FULL_DATASET = "../Dataset/GPS-power.dat"

if len(sys.argv) == 6:
    miner_num = int(sys.argv[1])
    edge_num = int(sys.argv[2])
    test_percent = float(sys.argv[3])
    round = int(sys.argv[4])
    pool_size = int(sys.argv[5])
    if test_percent > 0.5:
        print("test set oversize")
        exit()
else:
    print("check usage plz")
    exit()

test_id = genName()
print("- test id: " + test_id)
print("- {} miners, {} edge devices, total {} rounds, {} local weights per round".format(miner_num, edge_num, round, pool_size))
path = "test_{}".format(test_id)
os.mkdir(path)

full_file = open(FULL_DATASET, "r")
full_list = full_file.readlines()
full_file.close()
print("- {} records in total".format(len(full_list)))

test_file_path = "{}/test_{}.dat".format(path, test_id)
test_file = open(test_file_path, "w")
test_list = random.sample(full_list, int(len(full_list) * test_percent))
test_file.writelines(test_list)
test_file.close()
print("- {} records for test set".format(len(test_list)))

train_list = []
for line in full_list:
    if line in test_list:
        continue
    else:
        train_list.append(line)
train_files = []
for i in range(0, edge_num):
    new_path = "{}/train_{}_{}.dat".format(path, i, test_id)
    new_file = open(new_path, "w")
    train_files.append(new_file)
for i in range(0, len(train_list)):
    train_files[i % edge_num].write(train_list[i])
for i in range(0, edge_num):
    train_files[i].close()
print("- {} records per sub_train set".format(int(len(train_list)/edge_num)))

train_size_per_round = int(len(train_list)/edge_num/round) + 1

shell_file = open("run_test_{}.sh".format(test_id), "w")
shell_file.write("cd ../..\n")
shell_file.write("xterm -T seednode -e python -m DecentSpec.Seed.seed 5000 &\n")
shell_file.write("sleep 1\n")
for i in range(0, miner_num):
    shell_file.write("xterm -T miner{} -e python -m DecentSpec.Miner.miner http://api.decentspec.org {} {}&\n".format(i, 8000+i, pool_size))
shell_file.write("sleep 1\n")

for i in range(0, edge_num):
    train_file_path = "DecentSpec/Test/{}/train_{}_{}.dat".format(path, i, test_id)
    shell_file.write("xterm -T edge{} -e python -m DecentSpec.EdgeSim.edge {} {}&\n".format(i, train_file_path, train_size_per_round))

test_file_path = "DecentSpec/Test/{}".format(test_file_path)
shell_file.write("xterm -T loss_tester -e python -m DecentSpec.EdgeSim.edge {} {}&\n".format(test_file_path, 0))            # train size zero refers to tester edge
shell_file.write("cd DecentSpec/Test\n")
shell_file.close()
print("- done, plz run 'source run_test_{}.sh' ".format(test_id))


