"""
Test SiamFC & DaSiamRPN on GOT-10k
@ fansiqi  2020.4.21
"""
from __future__ import absolute_import
import os
import argparse

from got10k.experiments import *

from DaSiamRPN.tracker import TrackerDaSiamRPN
from tracker import TrackerSiamFC


for i in range(1, 21):

    path = './results/GOT-10k/SiamFC{}'.format(i)
    if not os.path.exists(path):
        os.makedirs(path)
    # setup tracker
    tracker = TrackerSiamFC(net_path="./pretrained/siamfc_new/model_e{}_500.pth".format(i))
    # setup experiments
    experiments = [
        ExperimentGOT10k('/root/autodl-tmp/GOT10k', subset='test')
    ]

    # run tracking experiments and report performance
    for e in experiments:
        e.run(tracker, visualize=False)
        e.report([tracker.name + str(i)])
