import os
import cv2
import math
import argparse
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from tqdm import tqdm
from PIL import Image


def normalize(img):
    img = img / 255.0
    return img

def read_image(img_path, input_shape, preprocess_fn=None):
    img = np.array(Image.open(img_path))
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    img = cv2.resize(img, input_shape[:2][::-1], interpolation=cv2.INTER_NEAREST)
    img = np.expand_dims(img, axis=0)   # (None, H, W, C)
    if preprocess_fn:
        img = preprocess_fn(img)
    else:
        img = normalize(img)
    return img

def load_model(model_path):
    if model_path == "vgg16":
        model = tf.keras.applications.VGG16()
        preprocess_fn = tf.keras.applications.vgg16.preprocess_input
    else:
        model = tf.keras.models.load_model(args.model_path)
        preprocess_fn = None
    return model, preprocess_fn


def visualize(img, model, layer_names, output_path, dpi=600):
    feat_maps = model.predict(img)
    if not isinstance(feat_maps, list):
        feat_maps = [feat_maps]

    layer_imgs = []
    for feat_map in feat_maps:
        h, w, n_imgs = feat_map.shape[1:]
        max_cols = math.ceil(n_imgs / math.log(n_imgs, 2))
        n_cols = min(n_imgs, max_cols)
        n_rows = math.ceil(n_imgs/n_cols)
        layer_img = np.zeros((h*n_rows, w*n_cols), dtype=np.uint8)
        for i in range(n_imgs):
            row_i, col_i = i//n_cols, i%n_cols
            feat_img = feat_map[0, :, :, i]
            feat_img -= feat_img.mean()
            feat_img /= (feat_img.std() or 1)   # avoid division by zero
            feat_img *= 64
            feat_img += 128
            feat_img = np.clip(feat_img, 0, 255).astype('uint8')
            layer_img[h*row_i:h*(row_i+1), w*col_i:w*(col_i+1)] = feat_img
        layer_imgs.append(layer_img)

    n_layers = len(layer_imgs)
    fig, axs = plt.subplots(n_layers, 1)
    for i, (layer_name, layer_img) in enumerate(zip(layer_names, layer_imgs)):
        ax = axs[i] if n_layers > 1 else axs
        ax.imshow(layer_img)
        ax.grid(False)
        ax.axis('off')
        ax.set_title(layer_name, fontsize=5)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=dpi)
    plt.close(fig)

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-m", "--model_path", default="vgg16", help="Model path")
    parser.add_argument("-l", "--layer_names", default=[], nargs="+", help="List of layer names for visualization (e.g. layer_1 layer_2 layer_3)")
    parser.add_argument("-i", "--input_dir", default="examples", help="Directory for input images")
    parser.add_argument("-o", "--output_dir", default="visualization", help="Directory for output visualization images")
    parser.add_argument("--dpi", type=int, default=600, help="DPI of output visualization images")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    model, preprocess_fn = load_model(args.model_path)
    model.summary()

    assert len(args.layer_names) > 0
    all_layer_names = [layer.name for layer in model.layers]
    invalid_layer_names = set(args.layer_names).difference(set(all_layer_names))
    assert len(invalid_layer_names) == 0

    layer_outputs = [model.get_layer(name).output for name in args.layer_names]
    feat_map_model = tf.keras.Model(inputs=model.input, outputs=layer_outputs)
    
    input_shape = feat_map_model.layers[0].input_shape[0][1:]
    for filename in tqdm(os.listdir(args.input_dir), desc="Process image"):
        input_path = os.path.join(args.input_dir, filename)
        output_path = os.path.join(args.output_dir, os.path.splitext(filename)[0] + "_viz.jpg")
        img = read_image(input_path, input_shape, preprocess_fn)
        visualize(img, feat_map_model, args.layer_names, output_path, args.dpi)
