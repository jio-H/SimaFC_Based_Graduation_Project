from __future__ import absolute_import, print_function

import os
import sys
sys.path.append('..')

import torch
from torch.utils.data import DataLoader


from got10k.datasets import ImageNetVID, GOT10k
from pairwise import Pairwise
from tracker import TrackerSiamFC



if __name__ == '__main__':
    # setup dataset
    root_dir = '/root/autodl-tmp/GOT10k/'
    seq_dataset = GOT10k(root_dir, subset='train')

    pair_dataset = Pairwise(seq_dataset)

    # setup data loader
    cuda = torch.cuda.is_available()
    # DataLoader是PyTorch中的一个数据加载器，它提供了对数据集的自动批处理、采样、多线程数据预读等功能
    loader = DataLoader(pair_dataset, batch_size=8, shuffle=True, pin_memory=cuda, drop_last=True, num_workers=4)

    # setup tracker
    tracker = TrackerSiamFC()

    # path for saving checkpoints
    net_dir = 'pretrained/siamfc_new'
    if not os.path.exists(net_dir): os.makedirs(net_dir)

    # training loop
    epoch_num = 20
    for epoch in range(epoch_num):
        for step, batch in enumerate(loader):

            loss = tracker.step(batch, backward=True, update_lr=(step == 0))
            if step % 20 == 0:
                print('Epoch [{}][{}/{}]: Loss: {:.3f}'.format(epoch + 1, step + 1, len(loader), loss))
                sys.stdout.flush()

        # save checkpoint
        net_path = os.path.join(net_dir, 'model_e%d_%d.pth' % (epoch + 1, 400))
        torch.save(tracker.net.state_dict(), net_path)
