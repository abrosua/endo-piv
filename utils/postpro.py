import os
import json
from glob import glob
from typing import Optional, List, Tuple

import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from labelme.utils import shape_to_mask

import utils
import matplotlib
matplotlib.use('TkAgg')


class Label:
    def __init__(self, labelpath: str, netname: str, verbose: int = 0) -> None:
        """
        Acquiring all the available label as a dictionary.
        params:
            labelpath:
            labeldir:
            verbose:
        """
        self.label_path = labelpath
        self.verbose = verbose
        self.label = {}

        # Importing the Labels
        if not os.path.isfile(labelpath):  # Label file checking
            raise ValueError(f"Label file at '{labelpath}' is NOT FOUND!")

        with open(labelpath) as json_file:
            data = json.load(json_file)
            self.img_shape = [data['imageHeight'], data['imageWidth']]

            # Image path
            imname = os.path.basename(data["imagePath"])
            self.img_dir = os.path.basename(os.path.dirname(data["imagePath"]))
            self.img_path = os.path.join("./frames", self.img_dir, imname)

            for d in data['shapes']:
                self.label[d['label']] = {'points': d['points'],
                                          'shape_type': d['shape_type']
                                          }

        # Importing the Flow files
        floname = os.path.splitext(imname)[0] + "_out.flo"
        basedir = self.img_dir
        self.flopath = os.path.join("./results", netname, basedir, "flow", floname)

        if not os.path.isfile(self.flopath):  # Flow file checking
            raise ValueError(f"Flow file at '{self.flopath}' is NOT FOUND!")

    def get_column(self) -> Optional[float]:
        """
        Returning the lowest point of the air column occurrence.
        """
        if 'column' in self.label.keys():
            points = np.array(self.label['column']['points'])
            y_points = points[:, 1]
            return y_points.min()
        else:
            print(f"The Air Column label is NOT found in '{self.label_path}'") if self.verbose else None
            return None

    def get_flo(self, key, fill_with: Optional[float] = None) -> Tuple[Optional[np.array], Optional[np.array]]:
        """
        Acquiring the masked flow vector and its respective mask array.
        params:
            key: The label key of the flow to obtain (e.g., 'flow', 'v1', 'v2')
            fill_with: Filling value to the masked vector.
        """
        if key in self.label.keys():
            flow_label = self.label[key]
            mask = shape_to_mask(self.img_shape, flow_label['points'], shape_type=flow_label['shape_type'])
            out_flow = utils.read_flow(self.flopath)

            # Filling the masked flow array
            mask_flow = np.empty(out_flow.shape)
            mask_flow[:] = np.nan if fill_with is None else fill_with
            mask_flow[mask] = out_flow[mask]

            return mask_flow, mask
        else:
            print(f"The '{key}' label is NOT found in '{self.label_path}'") if self.verbose else None
            return None, None


def velo_mean(flo: np.array, mask: Optional[np.array] = None):
    if mask is None:
        flo_mag = np.linalg.norm(flo, axis=-1)
        flo_mag_clean = flo_mag[~np.isnan(flo_mag)]

    else:
        flo_clean = flo[mask]
        flo_mag_clean = np.linalg.norm(flo_clean, axis=-1)

    return np.mean(flo_mag_clean)


def checkstat(data):
    sns.distplot(data, hist=True, kde=True,
                 bins=int(180 / 5), color='darkblue',
                 hist_kws={'edgecolor': 'black'},
                 kde_kws={'linewidth': 4})
    plt.show()


def column_diff():
    #TODO: Create a function to acquire the column points label, and plot the change in points. Returning as an Array!
    pass


if __name__ == '__main__':
    # <------------ Use flowviz (uncomment for usage) ------------>
    # flodir = "./results/Hui-LiteFlowNet/Test 03 L3 EDTA 22000 fpstif/flow"
    # imdir = "./frames/Test 03 L3 EDTA 22000 fpstif"
    # use_flowviz(flodir, imdir, start_at=4900, num_images=50, lossless=False)

    # <------------ Use get_label (uncomment for usage) ------------>
    netname = "Hui-LiteFlowNet"
    labelpaths = sorted(glob(os.path.join("./labels/Test 03 L3 NAOCL 22000 fpstif", "*")))

    # Variable init.
    v1, v2, flow, air_column = {}, {}, {}, {}

    for labelpath in labelpaths:
        labels = Label(labelpath, netname)

        v1_tmp, _ = labels.get_flo('v1')
        if v1_tmp is not None:
            v1[labelpath] = v1_tmp

        v2_tmp, _ = labels.get_flo('v2')
        if v2_tmp is not None:
            v2[labelpath] = v2_tmp

        flow_tmp, _ = labels.get_flo('flow')
        if flow_tmp is not None:
            flow[labelpath] = flow_tmp

        air_column_tmp = labels.get_column()
        if air_column_tmp is not None:
            air_column[labelpath] = air_column_tmp

    # Data post-processing (i.e., calculate mean, deviation, etc)
    # v1_mean = velo_mean(v1['flo'], mask=v1['mask'])

    print('DONE!')