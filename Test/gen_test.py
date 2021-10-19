import sys
import random
import string
import os
import math
import DecentSpec.Common.config as CONFIG

'''
useage:
    python gen_test.py {1} {2} {3} {4} {5} {6}
    {1} - int, num of miner
    {2} - int, num of edge device
    {3} - float, percentage of test set 
    {4} - int, num of fl round
    {5} - int, num of local model collection per round
    {6} - subdata set distribution: 
            total: AAAABBBBCCCCDDDD
            "seq"   - AAAA BBBB CCCC DDDD
            "rr"    - ABCD ABCD ABCD ABCD
            "rand"  - randomly
            "muji"  - use the pre-generated, fixed "test_muji" dataset
'''

FULL_DATASET = "../Dataset/GPS-power.dat"

def genName(num=5):
    salt = ''.join(random.sample(string.ascii_letters + string.digits, num))
    return salt

def genShell(tag):
    path = "test_{}".format(tag)

    shell_file = open("run_test_{}.sh".format(test_id), "w")
    shell_file.write("cd ../..\n")
    shell_file.write("xterm -T seednode -e python -m DecentSpec.Seed.seed 5000 &\n")
    shell_file.write("sleep 1\n")
    for i in range(0, miner_num):
        shell_file.write("xterm -T miner{} -e python -m DecentSpec.Miner.miner {} {} {} &\n".format(i, CONFIG.SEED_ADDR, 8000+i, pool_size))
    shell_file.write("sleep 1\n")

    for i in range(0, edge_num):
        train_file_path = "DecentSpec/Test/{}/train_{}.dat".format(path, i)
        shell_file.write("xterm -T edge{} -e python -m DecentSpec.EdgeSim.edge train {} {} {} &\n".format(i, train_file_path, 0, round))         #  size zero refers to full set

    test_file_path = "DecentSpec/Test/{}/test.dat".format(path)
    shell_file.write("xterm -T loss_tester -e python -m DecentSpec.EdgeSim.edge test {} {} {} &\n".format(test_file_path, 0, round))            #  size zero refers to full set
    shell_file.write("cd DecentSpec/Test\n")
    shell_file.close()
    print("- done, plz run 'source run_test_{}.sh' ".format(test_id))

if len(sys.argv) == 7:
    miner_num = int(sys.argv[1])
    edge_num = int(sys.argv[2])
    test_percent = float(sys.argv[3])
    round = int(sys.argv[4])
    pool_size = int(sys.argv[5])
    policy = sys.argv[6]
    if test_percent > 0.5:
        print("test set oversize")
        exit()
    if not policy in ["rr", "muji", "seq", "rand"]:
        print("unrecognized policy")
        exit()
else:
    print("check usage plz")
    exit()

test_id = genName()
print("- test id: " + test_id)
print("- {} miners, {} edge devices, total {} rounds, {} local weights per round".format(miner_num, edge_num, round, pool_size))
print("- dataset generation policy: " + policy)

if policy != "muji":

    path = "test_{}".format(test_id)
    os.mkdir(path)

    full_file = open(FULL_DATASET, "r")
    full_list = full_file.readlines()
    full_file.close()
    print("- {} records in total".format(len(full_list)))

    # ========== gen global test set
    test_file = open("{}/test.dat".format(path), "w")
    test_list = random.sample(full_list, int(len(full_list) * test_percent))
    test_file.writelines(test_list)
    test_file.close()
    print("- {} records for test set".format(len(test_list)))

    # ========== gather the rest as train set
    train_list = []
    for line in full_list:
        if line in test_list:
            continue
        else:
            train_list.append(line)
    subtrain_size = math.ceil(len(train_list)/edge_num)
    print("- {} records per sub_train set".format(subtrain_size))

    # ========== create train set files
    train_files = []
    for i in range(0, edge_num):
        new_path = "{}/train_{}.dat".format(path, i)
        new_file = open(new_path, "w")
        train_files.append(new_file)

    # ========== gen sub train set
    if policy == "rr":
        for i in range(0, len(train_list)):
            train_files[i % edge_num].write(train_list[i])
    if policy == "rand":
        random.shuffle(train_list)
        for i in range(0, edge_num):
            train_files[i].writelines(train_list[i*subtrain_size : (i+1)*subtrain_size])
    if policy == "seq":
        for i in range(0, edge_num):
            train_files[i].writelines(train_list[i*subtrain_size : (i+1)*subtrain_size])
    
    # ========== save train set files
    for i in range(0, edge_num):
        train_files[i].close()


    # ========== gen one-click script
    genShell(test_id)

else:
    genShell("muji")

