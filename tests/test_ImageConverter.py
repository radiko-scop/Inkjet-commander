import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__) + "/../"))

import numpy as np
from ImageConverter import ImageConverter
from ImageConverter2 import ImageSlicer
from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)


def test_ThersholdedImagesAreTheSame():
    path = "ytec_logo_icon.png"
    half_dpi = 300
    cvt = ImageConverter()
    cvt.SetDPI(half_dpi*2)
    cvt.OpenFile(path)
    cvt.Threshold(128)
    cvt.ArrayToImage()
    original = cvt.image_array
    slicer = ImageSlicer(path, half_dpi)
    toto = slicer.imageArray()
    assert np.array_equal(toto[0][:, :64], original)
    breakpoint()
    pass