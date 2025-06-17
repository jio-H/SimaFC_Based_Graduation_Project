"""
Test SiamFC & DaSiamRPN on GOT-10k
@ fansiqi  2020.4.21
"""
from __future__ import absolute_import

import argparse

from got10k.experiments import *

from DaSiamRPN.tracker import TrackerDaSiamRPN
from tracker import TrackerSiamFC


def test():
    for i in range(1, 21):
        # setup tracker
        tracker = TrackerSiamFC(net_path="./SiamFC/pretrained/siamfc_new/model_e{}_500.pth".format(i))
        # setup experiments
        experiments = [
            ExperimentGOT10k('/root/autodl-tmp/GOT10k', subset='test')
        ]

        # run tracking experiments and report performance
        for e in experiments:
            e.run(tracker, visualize=False)
            e.report([tracker.name + str(i)])


if __name__ == "__main__":

    model_id = 0
    model_name = "DaSiamRPN" if model_id else "SiamFC"

    print("-" * 30)
    print("Test {} model".format(model_name))

    test()
