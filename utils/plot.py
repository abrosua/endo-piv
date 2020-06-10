import os
import imageio
import math
from typing import Optional, List, Union, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.cm as cm
from matplotlib import animation
from matplotlib import colors
from PIL import Image
from flowviz import colorflow, animate

import utils
import matplotlib
matplotlib.use('TkAgg')


class FlowViz:
    def __init__(self, labelpaths: List[str], netname: str, maxmotion: Optional[float] = None, vector_step: int = 1,
                 use_color: int = 0, use_quiver: bool = False, color_type: Optional[str] = None, key: str = "flow",
                 crop_window: Union[int, Tuple[int, int, int, int]] = 0, velocity_factor: float = 1.0,
                 verbose: int = 0) -> None:
        """
        Flow visualization instance
        params:
            flopaths:
            netname:
            file_extension:
            show:
            verbose:
        """
        # Input sanity checking
        assert len(labelpaths) > 0
        if color_type is not None:
            assert color_type in ["vort", "mag"]

        self.labelpaths = labelpaths
        self.netname = netname

        # Logic gate
        self.use_color = use_color
        self.use_quiver = use_quiver
        self.color_type = color_type
        self.verbose = verbose

        # Variables
        self.maxmotion = maxmotion * velocity_factor
        self.vector_step = vector_step
        self.crop_window = crop_window
        self.velocity_factor = velocity_factor
        self.key = key

        # Init.
        self.img_dir, self.keyname = "", ""
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.ax.set_xticks([])  # Erasing the axis number
        self.ax.set_yticks([])
        self.im1, self.quiver = None, None

        # Scalar mapping
        self.norm = colors.Normalize(vmin=0, vmax=maxmotion)
        self.scalar_map = cm.ScalarMappable(norm=self.norm, cmap=cm.hot_r)
        if (use_quiver and not use_color) or color_type == "mag":
            self.fig.colorbar(self.scalar_map)

        if self.use_color == 1:
            self.keyname += "c"
        elif self.use_color == 2:
            self.keyname += "t"
            self.im2 = None
        if self.use_quiver:
            self.keyname += "q"

    def plot(self, file_extension: Optional[str] = None, show: bool = False, savedir: Optional[str] = None,
             **quiver_key) -> None:
        """
        Plotting
        """
        for labelpath in self.labelpaths:
            label = utils.Label(labelpath, self.netname, verbose=self.verbose)
            bname = os.path.splitext(os.path.basename(labelpath))[0]

            # Add flow field
            flow, mask = label.get_flo(self.key)
            if flow is None or mask is None:  # Skipping label file that doesn't have the flow label!
                continue
            else:
                flow = flow * self.velocity_factor

            # Reading flow and image files
            flow_crop = utils.array_cropper(flow, self.crop_window)
            mask_crop = utils.array_cropper(mask, self.crop_window)
            img = imageio.imread(label.img_path)  # Read the raw image
            img_crop = utils.array_cropper(img, self.crop_window)

            self._init_frame(img_crop, **quiver_key)  # Initialize the frame
            self._draw_frame(flow_crop, img_crop, mask_crop)  # Drawing each frame

            if show:
                plt.show()

            if file_extension:
                # Setting up the path name
                plotdir = os.path.join("./results", self.netname, self.img_dir, "viz") if savedir is None else savedir
                os.makedirs(plotdir) if not os.path.isdir(plotdir) else None
                # Saving the plot
                plotpath = os.path.join(plotdir, bname + f"_{self.keyname}viz.{file_extension}")
                plt.savefig(plotpath, dpi=300, bbox_inches='tight')

            plt.clf()

    def video(self, flodir: str, ext: Optional[str] = None, start_at: int = 0, num_images: int = -1,
              fps: int = 1, dpi: int = 300, lossless: bool = True):
        """
        Generating video
        """
        # Flow init.
        flows, flonames = utils.read_flow_collection(flodir, start_at=start_at, num_images=num_images,
                                                     crop_window=self.crop_window)
        flows = flows * self.velocity_factor

        fname_addition = f"-{start_at}_end" if num_images < 0 else f"-{start_at}_{num_images}"
        self.img_dir = str(os.path.normpath(flodir).split(os.sep)[-2])
        imgdir = os.path.join("./frames", self.img_dir)

        # Frame looping init.
        labelpaths, imagepaths = [], []

        for i, floname in enumerate(flonames):
            bname = os.path.basename(floname).rsplit("_", 1)[0]
            imagepaths.append(os.path.join(imgdir, bname + ".tif"))

            if len(self.labelpaths) == 1:
                labelpath = self.labelpaths[0]
                labelpaths.append(labelpath)

            elif len(self.labelpaths) > 1:
                labeldir = os.path.dirname(self.labelpaths[0])
                labelpath = os.path.join(labeldir, bname + ".json")
                assert labelpath in self.labelpaths

            else:
                raise ValueError(f"Unknown labelpaths input! '{self.labelpaths}'")

            assert os.path.isfile(labelpath)

        # Initialize frame
        img_tmp = utils.array_cropper(imageio.imread(imagepaths[0]), self.crop_window)
        self._init_frame(img_tmp)

        # Generate animation writer
        flowviz_anim = animation.FuncAnimation(self.fig, self._capture_frame, fargs=(labelpaths, imagepaths, flows),
                                               interval=1000/fps, frames=num_images)
        vidname = self.img_dir + fname_addition + f"_{self.keyname}vid"

        if ext is not None:
            vidpath = os.path.join(os.path.dirname(flodir), "videos", vidname + f".{ext}")
            writer = animation.writers['ffmpeg'](fps=fps, metadata=dict(artist="Faber"), bitrate=-1)
            flowviz_anim.save(vidpath, writer=writer, dpi=dpi)

    def _capture_frame(self, idx, labelpaths: List[str], imagepaths: List[str], flows: np.array):
        """
        Iteration function for capturing vidoe frame.
        """
        labelpath = labelpaths[idx]
        imagepath = imagepaths[idx]

        # Instantiate the Label
        label = utils.Label(labelpath, netname=self.netname, verbose=self.verbose)
        _, mask = label.get_flo(self.key)

        # Gathering each frame
        img_crop = utils.array_cropper(imageio.imread(imagepath), self.crop_window)
        mask_crop = utils.array_cropper(mask, self.crop_window)

        self._draw_frame(flows[idx, :, :, :], img_crop, mask_crop)

    def _init_frame(self, image: np.array, **quiver_key):
        """
        Initializing frame for video writer.
        """
        h, w, _ = image.shape

        # Image init.
        self.im1 = self.ax.imshow(np.zeros_like(image))
        if self.use_color == 2:
            self.im2 = self.ax.imshow(np.zeros([h, w, 4], dtype=image.dtype))

        # Quiver init.
        x, y = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
        xp, yp = x[::self.vector_step, ::self.vector_step], y[::self.vector_step, ::self.vector_step]
        mag = np.hypot(xp, yp)
        width_factor = 0.004

        if not self.use_color:
            # Setting the vector color
            colormap = self.scalar_map.get_cmap()
            self.quiver = self.ax.quiver(xp, yp, np.zeros_like(xp), np.zeros_like(yp), np.zeros_like(mag),
                                         cmap=colormap, units='xy', width=width_factor*w, scale=width_factor*100)
        else:
            self.quiver = self.ax.quiver(xp, yp, np.zeros_like(xp), np.zeros_like(yp),
                                         units='xy', width=width_factor*w, scale=width_factor*100)

        qk = self.ax.quiverkey(self.quiver, **quiver_key) if quiver_key else None

    def _draw_frame(self, flow: np.array, image: np.array, mask: np.array):
        """
        Drawing each single frame.
        """
        u, v = flow[:, :, 0], flow[:, :, 1]

        # Image masking
        flow[~mask] = 0.0  # Replacing NaNs with zero to convert the value into RGB
        mag = np.linalg.norm(flow, axis=-1)  # Calculate the flow magnitude

        if self.color_type == "vort":  # TODO: create vorticity calculation function!
            flo_rgb = None
        elif self.color_type == "mag":  # TODO: fixing the magnitude color plot!
            flo_rgb = np.uint8(self.scalar_map.to_rgba(mag) * 255)[:, :, :3]
        else:
            flo_rgb = colorflow.motion_to_color(flow, maxmotion=self.maxmotion)

        # Superpose the image and flow color visualization if use_color is activated
        if self.use_color == 1:
            flo_rgb[~mask] = 0  # Merging image and plot the result
            image[mask] = 0
            self.im1.set_data(image + flo_rgb)

        elif self.use_color == 2:  # TODO: FIX the translucent color plot feature!
            flo_rgb[~mask] = 255
            alpha = np.uint8((mag - np.min(mag)) * 255 / (np.max(mag) - np.min(mag)))
            flo_rgba = np.dstack([flo_rgb, alpha])

            self.im1.set_data(image)
            self.im2.set_data(flo_rgba)

        else:
            image[mask] = 255
            self.im1.set_data(image)

        # Adding quiver plot (if necessary)
        self._q_plot(u, v, mask) if self.use_quiver else None

    def _q_plot(self, u, v, mask) -> None:
        """
        Quiver plot config.
        params:
            u: Flow displacement at x-direction.
            v: Flow displacement at y-direction.
            mask: The masking array.
        """
        # Slicing the flow vector
        up, vp = u[::self.vector_step, ::self.vector_step], v[::self.vector_step, ::self.vector_step]
        mag = self.norm(np.hypot(up, vp))

        # Plotting preparation and Masking the data
        maskp = mask[::self.vector_step, ::self.vector_step]
        up[~maskp], vp[~maskp] = np.nan, np.nan

        # Adding vector values
        if not self.use_color:
            self.quiver.set_UVC(up, -vp, C=mag)
        else:
            self.quiver.set_UVC(up, -vp)


def get_image(basename, imdir, crop_window: Union[int, Tuple[int, int, int, int]] = 0) -> np.array:
    imname = basename + ".tif"
    impath = os.path.join(imdir, imname)
    img = imageio.imread(impath)

    return utils.array_cropper(img, crop_window)


def vid_flowviz(flodir, imdir, start_at: int = 0, num_images: int = -1, lossless: bool = True):
    """
    Visualization using flowviz module
    """
    print("Optical flow visualization using flowviz by marximus...")

    # Obtaining the flo files and file basename
    flows, flonames = utils.read_flow_collection(flodir, start_at=start_at, num_images=num_images)
    fname_addition = f"-{start_at}_all" if num_images < 0 else f"-{start_at}_{num_images}"
    fname = os.path.basename(os.path.dirname(flodir)) + fname_addition

    # Manage the input images
    video_list = []
    for floname in flonames:
        filename = str(os.path.basename(floname).rsplit('_', 1)[0]) + ".tif"
        filepath = os.path.join(imdir, filename)
        video_list.append(imageio.imread(filepath))
        # video_list.append(Image.open(filepath).convert('RGB'))

    video = np.array(video_list)

    # Previewing the files
    print('Video shape: {}'.format(video.shape))
    print('Flows shape: {}'.format(flows.shape))

    # Define the output files
    colors = colorflow.motion_to_color(flows)
    flowanim = animate.FlowAnimation(video=video, video2=colors, vector=flows, vector_step=10,
                                     video2_alpha=0.5)

    # Saving the video
    viddir = os.path.join(os.path.dirname(flodir), "videos")
    if not os.path.isdir(viddir):
        os.makedirs(viddir)

    if lossless:
        vidpath = os.path.join(viddir, fname + ".avi")
        flowanim.save(vidpath, codec="ffv1")
    else:
        vidpath = os.path.join(viddir, fname + ".mp4")
        flowanim.save(vidpath)
    print(f"Finish saving the video file ({vidpath})!")


def color_map(resolution: int = 256, maxmotion: float = 1.0, show: bool = False, filename: Optional[str] = None,
              velocity_factor: float = 1.0) -> None:
    """
    Plotting the color code
    params:
        resolution: Colormap image resolution.
        maxmotion: Maximum flow motion.
        show: Option to display the plot or not.
        filename: Full file path to save the plot; use None for not saving the plot!
        resolution: To calibrate flow velocity from [pixel/frame] into [mm/second]
    Returns the flow colormap in mm/second.
    """
    # Init.
    bname = os.path.basename(filename).rsplit("_", 1)[0]

    # Color plot
    pts = np.linspace(-maxmotion, maxmotion, num=resolution)
    x, y = np.meshgrid(pts, pts)
    flo = np.dstack([x, y]) * velocity_factor  # Calibrating into real flow vector
    flo_color = colorflow.motion_to_color(flo)

    # Plotting the image
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.imshow(flo_color, extent=[-math.ceil(maxmotion), math.ceil(maxmotion),
                                 -math.ceil(maxmotion), math.ceil(maxmotion)])
    ax.set_title(f"{bname} Colormap")

    # Erasing the zeros
    func = lambda x, pos: "" if np.isclose(x, 0) else x
    plt.gca().xaxis.set_major_formatter(ticker.FuncFormatter(func))
    plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(func))

    # Putting the axis in the middle of the graph, passing through (0,0)
    ax.spines['left'].set_position('center')  # Move left y-axis and bottim x-axis to centre
    ax.spines['bottom'].set_position('center')
    ax.spines['right'].set_color('none')  # Eliminate upper and right axes
    ax.spines['top'].set_color('none')
    ax.xaxis.set_ticks_position('bottom')  # Show ticks in the left and lower axes only
    ax.yaxis.set_ticks_position('left')

    plt.show() if show else None
    plt.savefig(filename, dpi=300, bbox_inches='tight') if filename else None
    plt.clf()


if __name__ == "__main__":
    # Generate colormap
    color_map(resolution=256, maxmotion=4, show=True)

    print("DONE!")
