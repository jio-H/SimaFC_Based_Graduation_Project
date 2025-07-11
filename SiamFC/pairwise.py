from __future__ import absolute_import, division

import numpy as np
from collections import namedtuple
from torch.utils.data import Dataset
from torchvision.transforms import Compose, CenterCrop, RandomCrop, ToTensor
from PIL import Image, ImageStat, ImageOps

#双线性插值方法(??)
class RandomStretch(object):
    """
        图像随机延展
        max_stretch: 最大延展比例
        interpolation:插值方法
    """
    #双线性插值方法
    def __init__(self, max_stretch=0.05, interpolation='bilinear'):
        #为假抛出错误 assert condition, message
        assert interpolation in ['bilinear', 'bicubic']

        self.max_stretch = max_stretch
        self.interpolation = interpolation

    def __call__(self, img):
        scale = 1.0 + np.random.uniform(
            -self.max_stretch, self.max_stretch)
        size = np.round(np.array(img.size, float) * scale).astype(int)
        if self.interpolation == 'bilinear':
            method = Image.BILINEAR
        elif self.interpolation == 'bicubic':
            method = Image.BICUBIC
        return img.resize(tuple(size), method)

#继承GOT10k类
class Pairwise(Dataset):
    """

    """
    def __init__(self, seq_dataset, **kargs):
        super(Pairwise, self).__init__()
        # 参数设置
        self.cfg = self.parse_args(**kargs)
        
        self.seq_dataset = seq_dataset
        # 生成随机序列索引
        self.indices = np.random.permutation(len(seq_dataset))
        # 数据增强 augmentation for exemplar and instance images
        self.transform_z = Compose([
            # 图像随机延展
            RandomStretch(max_stretch=0.05),
            # 下面三个操作的意义??
            # 对输入图像从中心点裁剪出指定大小的图像
            CenterCrop(self.cfg.instance_sz - 8),

            RandomCrop(self.cfg.instance_sz - 2 * 8),

            CenterCrop(self.cfg.exemplar_sz),
            # 数据类型转化为tensor数据类型，并执行归一化操作
            ToTensor()])

        self.transform_x = Compose([
            RandomStretch(max_stretch=0.05),
            # 只做两次操作 ？？
            CenterCrop(self.cfg.instance_sz - 8),
            RandomCrop(self.cfg.instance_sz - 2 * 8),
            ToTensor()])

    def parse_args(self, **kargs):
        """
        参数设置
        """
        # default parameters
        cfg = {
            'pairs_per_seq': 10,
            'max_dist': 100,
            'exemplar_sz': 127,
            'instance_sz': 255,
            'context': 0.5}

        for key, val in kargs.items():
            if key in cfg:
                cfg.update({key: val})
        return namedtuple('GenericDict', cfg.keys())(**cfg)
        #namedtuple能够用来创建类似于元祖的数据类型，除了能够用索引来访问数据，能够迭代，还能够方便的通过属性名来访问数据

    def __getitem__(self, index):
        # 获取index对应的图片与标签
        index = self.indices[index % len(self.seq_dataset)]
        img_files, anno = self.seq_dataset[index]

        # remove too small objects
        valid = anno[:, 2:].prod(axis=1) >= 10
        img_files = np.array(img_files)[valid]
        anno = anno[valid, :]

        rand_z, rand_x = self._sample_pair(len(img_files))

        exemplar_image = Image.open(img_files[rand_z])
        instance_image = Image.open(img_files[rand_x])
        exemplar_image = self._crop_and_resize(exemplar_image, anno[rand_z])
        instance_image = self._crop_and_resize(instance_image, anno[rand_x])
        exemplar_image = 255.0 * self.transform_z(exemplar_image)
        instance_image = 255.0 * self.transform_x(instance_image)

        return exemplar_image, instance_image

    def __len__(self):
        return self.cfg.pairs_per_seq * len(self.seq_dataset)

    # 如果有效索引大于2个的话，就从中随机挑选两个索引，这里取的间隔不超过T = 100
    def _sample_pair(self, n):
        assert n > 0
        if n == 1:
            return 0, 0
        elif n == 2:
            return 0, 1
        else:
            max_dist = min(n - 1, self.cfg.max_dist)
            rand_dist = np.random.choice(max_dist) + 1
            rand_z = np.random.choice(n - rand_dist)
            rand_x = rand_z + rand_dist

        return rand_z, rand_x

    # crop一块以object为中心的，边长为size大小的patch
    def _crop_and_resize(self, image, box):
        # convert box to 0-indexed and center based
        box = np.array([
            box[0] - 1 + (box[2] - 1) / 2,
            box[1] - 1 + (box[3] - 1) / 2,
            box[2], box[3]], dtype=np.float32)
        center, target_sz = box[:2], box[2:]

        # exemplar and search sizes
        context = self.cfg.context * np.sum(target_sz)
        # 裁剪区域边长
        z_sz = np.sqrt(np.prod(target_sz + context))
        x_sz = z_sz * self.cfg.instance_sz / self.cfg.exemplar_sz

        # convert box to corners (0-indexed)
        size = round(x_sz)
        corners = np.concatenate((
            np.round(center - (size - 1) / 2),
            np.round(center - (size - 1) / 2) + size))
        corners = np.round(corners).astype(int)

        # pad image if necessary
        pads = np.concatenate((
            -corners[:2], corners[2:] - image.size))
        npad = max(0, int(pads.max()))
        if npad > 0:
            avg_color = ImageStat.Stat(image).mean
            # PIL doesn't support float RGB image
            avg_color = tuple(int(round(c)) for c in avg_color)
            image = ImageOps.expand(image, border=npad, fill=avg_color)

        # crop image patch
        corners = tuple((corners + npad).astype(int))
        patch = image.crop(corners)

        # resize to instance_sz
        out_size = (self.cfg.instance_sz, self.cfg.instance_sz)
        patch = patch.resize(out_size, Image.BILINEAR)

        return patch
