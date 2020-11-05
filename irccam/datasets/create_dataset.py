"""
Take the raw IRCCAM data and RGB data and create train, val, and test sets
for model training. 

This requires the `extract_irccam_data.py` script to have been run already. That
script reads the huge matlab file and stores the data for each image 
individually. This makes this script a lot faster and easier to tweak and 
experiment with. 

Basic flow:
- For each day of rgb data:
    - Read all timestamps,
    - Get irccam image corresponding to timestamp, preprocess and save
    - Get rgb image for timestamp, preprocess, create label, and save
    - Filter out black and ignored images

Still to do:
- Fix irccam processing (see todo note below)
- rgb image horizon mask (currently parts of horizon get marked as clouds)
- Split into train, val, and test folders (currently just stored as one set)

Considerations:
- Save images as numpy array instead of as images to make life easier/more uniform for import/export
- irccam data is between approx. -500 and 60, although most images at between -60, 60. What kind of grayscale to user?
"""

import os
import mat73
import datetime
import cv2
import numpy as np
from tqdm import tqdm

from datasets.dataset_filter import is_almost_black, filter_ignored
from datasets.rgb_labeling import create_rgb_label, create_label_image

PROJECT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../..")
RAW_DATA_PATH = os.path.join(PROJECT_PATH, "data/raw/davos")
DATASET_PATH = os.path.join(PROJECT_PATH, "data/datasets")


def create_dataset(dataset_name="dataset_v1", train_val_test_split=[0.6, 0.2, 0.2]):
    assert (
        sum(train_val_test_split) == 1
    ), "Invalid train_val_test_split: must sum to 1."
    vis_days = np.array(get_contained_dirs(os.path.join(RAW_DATA_PATH, "rgb")))
    vis_days = filter_ignored(vis_days)
    num_days = len(vis_days)

    rand_idx = np.random.permutation(np.arange(num_days))
    train_size = round(num_days * train_val_test_split[0])
    val_size = round(num_days * train_val_test_split[1])
    test_size = round(num_days * train_val_test_split[2])
    print(train_size, val_size, test_size)

    train_idx = rand_idx[:train_size]
    val_idx = rand_idx[train_size : train_size + val_size]
    test_idx = rand_idx[train_size + val_size :]

    train_days = vis_days[train_idx]
    val_days = vis_days[val_idx]
    test_days = vis_days[test_idx]

    print("Creating train set")
    for day in tqdm(train_days):
        process_day_data(day, dataset_name, "train")

    print("Creating val set")
    for day in tqdm(val_days):
        process_day_data(day, dataset_name, "val")

    print("Creating test set")
    for day in tqdm(test_days):
        process_day_data(day, dataset_name, "test")


# def vis_timestamps_for_day(day):
#     filenames = [file for file in get_contained_files(os.path.join(RAW_DATA_PATH, "rgb", day)) if file.endswith("_0.jpg")]
#     timestamps = [filename.replace("_0.jpg", "") for filename in filenames]
#     return timestamps

# def irccam_timestamps_for_day(day):
#     filenames = [file for file in get_contained_files(os.path.join(RAW_DATA_PATH, "irccam_extract", day, bt)) if file.endswith(".npz")]
#     timestamps = [filename.replace(".npz", "") for filename in filenames]
#     return timestamps


def process_day_data(day, dataset_name, subset):
    # print("Processing {} for {} data".format(day, subset))
    image_filenames = get_contained_files(os.path.join(RAW_DATA_PATH, "rgb", day))
    image_filenames = [file for file in image_filenames if file.endswith("_0.jpg")]
    image_timestamps = [filename.replace("_0.jpg", "") for filename in image_filenames]
    image_timestamps = filter_ignored(image_timestamps)
    img_dir = os.path.join(DATASET_PATH, dataset_name, subset)
    count = 0
    image_timestamps.sort()
    cloud_labels = []
    for idx, timestamp in enumerate(image_timestamps):
        # Remove this to process all data
        if count > 5:
            break

        try:
            irccam_raw = get_irccam_bt_data(timestamp)
        except FileNotFoundError:
            # print("Skipping the rest of the day after {}".format(timestamp))
            # the irccam data does not exist for this image (sometimes the data is not complete for a day eg. irccam_20180511_rad.mat)
            continue
        irccam_img = process_irccam_img(irccam_raw)

        vis_img_raw = get_vis_img(timestamp)
        vis_img = process_vis_img(vis_img_raw)

        # save if all filtering was OK
        if vis_img is not None and irccam_img is not None:
            img_path = os.path.join(img_dir, day)
            if not os.path.exists(img_path):
                os.makedirs(img_path)

            irccam_img_filename = os.path.join(img_path, "{}_irc.tif".format(timestamp))
            saved = cv2.imwrite(irccam_img_filename, irccam_img)
            if not saved:
                raise Exception("Failed to save image {}".format(irccam_img_filename))
            vis_img_filename = os.path.join(img_path, "{}_vis.tif".format(timestamp))
            saved = cv2.imwrite(vis_img_filename, vis_img)
            if not saved:
                raise Exception("Failed to save image {}".format(vis_img_filename))

            label_filename = os.path.join(img_path, "{}_labels.npz".format(timestamp))
            label_img_filename = os.path.join(
                img_path, "{}_labels.tif".format(timestamp)
            )
            label = create_rgb_label(vis_img)
            label = transform_perspective(
                label, (irccam_img.shape[0], irccam_img.shape[1])
            )
            label_image = create_label_image(label)
            saved = cv2.imwrite(label_img_filename, label_image)
            if not saved:
                raise Exception("Failed to save image {}".format(label_img_filename))
            np.savez(label_filename, label)
            count += 1

    # print("Processed {} images for day {}".format(count, day))

    return count


def get_contained_dirs(path):
    return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]


def get_contained_files(path):
    return [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]


# from https://stackoverflow.com/a/23316542
def rotate_image(image, angle):
    row, col, _ = image.shape
    center = tuple(np.array([row, col]) / 2)
    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
    new_image = cv2.warpAffine(image, rot_mat, (col, row))
    return new_image


def process_irccam_img(img):
    processed_ir = normalize_irccam_image(img)
    processed_ir = cv2.flip(processed_ir, -1)
    processed_ir = processed_ir[110:530, 80:500]
    return processed_ir


# need to add masking too, but unsure about the rotations
def process_vis_img(img):
    if is_almost_black(img):
        return None
    processed_vis = cv2.resize(img, (640, 480))
    processed_vis = processed_vis[50:470, 105:525]
    processed_vis = cv2.flip(processed_vis, 1)
    processed_vis = rotate_image(processed_vis, -120)
    return processed_vis


def vis_to_irccam_timestamp(timestamp):
    vis_ts = datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S")
    ir_ts = vis_ts
    return ir_ts


"""
TODO:
this function currently reads raw irccam data and then maps to rgb range 
by taking the min and max values in the image. This is wrong though, because
it uses a different range for each image.

We should instead figure out what are suitable min and max ir values to use
over all these images. Then for each one we cap at those min and max
values and map to grayscale range.

Using 16 bit tif instead of rgb, to prevent data loss on images with outlying pixels, should rethink this too
Set the actual image to 0-60000. reserve completly white for the mask
"""


def normalize_irccam_image(img_ir_raw):
    mi = np.nanmin(img_ir_raw)
    ma = np.nanmax(img_ir_raw)
    gray_ir = img_ir_raw - mi
    gray_ir *= 60000 / (ma - mi)
    np.nan_to_num(gray_ir, copy=False, nan=(2 ** 16 - 1))
    return gray_ir.astype(np.uint16)


def get_irccam_bt_data(timestamp):
    ir_ts = vis_to_irccam_timestamp(timestamp)
    filename = os.path.join(
        RAW_DATA_PATH,
        "irccam_extract",
        ir_ts.strftime("%Y%m%d"),
        "bt",
        "{}.npz".format(ir_ts.strftime("%Y%m%d%H%M")),
    )
    return np.load(filename)["arr_0"]


def get_vis_img(timestamp):
    img_time = datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S")
    file_path = os.path.join(
        RAW_DATA_PATH, "rgb", img_time.strftime("%Y%m%d"), "{}_0.jpg".format(timestamp)
    )
    img_vis = cv2.imread(file_path)
    if img_vis is None:
        raise FileNotFoundError("Image {} not found".format(file_path))
    return img_vis


def transform_perspective(img, shape):
    matrix_file = os.path.join(PROJECT_PATH, "irccam/datasets/trans_matrix.csv")
    M = np.loadtxt(matrix_file, delimiter=",")
    return cv2.warpPerspective(img, M, shape, cv2.INTER_NEAREST)


if __name__ == "__main__":
    create_dataset()
