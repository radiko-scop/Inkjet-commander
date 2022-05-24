"""
Replacement for image converter
"""

from asyncio.log import logger
import numpy as np
import math

import os

from PIL import Image


import logging

# https://github.com/CarpenterD/python-dithering

class ImageSlicer:
    """ This class split an image in strips, to print.
        It also convert RGB / Grayscale image into dithered one that is printable *as is* by a printer.
    """
    def __init__(self, path, sweep_height=300):
        im = Image.open(path).convert("RGBA")
        new_image = Image.new("RGBA", im.size, "WHITE")
        new_image.paste(im, mask=im)
        bw = new_image.convert(mode="1", dither=Image.Dither.FLOYDSTEINBERG)
        self.im = np.asarray(bw)

        im = Image.fromarray(self.im, mode="L")
        im.save("result.png")

        self.sweep_height = sweep_height
        self.rows = self.im.shape[0]

    def sweepCount(self):
        return math.ceil(self.rows / self.sweep_height)

    def dpi(self):
        return self.sweep_height * 2

    def imageSweeps(self):
        """Givem a numpy array representing a png image, with N color channels, return the sweep corresponding to first channel (Red usually ?)
        """

        for index in range(self.sweepCount()):
            rstart = self.sweep_height*index
            rstop = self.sweep_height*(index+1)
            if rstop > self.rows :
                rstop = self.rows
                sweep = self.im[rstart:rstop, :]
                sweep = np.pad(sweep, ((0, self.sweep_height - sweep.shape[0]),(0, 0)), 'constant', constant_values=True)
            else:
                sweep = self.im[rstart:rstop, :]
            # assert sweep.shape[0] == self.sweep_height
            logging.debug(f"Sweep #{index} : {sweep.shape}")
            yield sweep.T^True # Note the XOR to change 0 into ones

    def imageArray(self):
        aggregated = []
        for sweep in self.imageSweeps():
            aggregated += [sweep]
        return aggregated

    def image(self):
        return self.im.astype(np.int8)

    def output(self):
        return (self.im*255).astype(np.int8)

if __name__ == "__main__":
    file = 'TestFiles/test600dpi.png'
    ims = ImageSlicer(file)