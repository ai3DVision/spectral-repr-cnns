import numpy as np
import tensorflow as tf


def _tfshift(matrix, n, axis=1, invert=False):
    """Handler for shifting one axis at a time.
    Helpful for fftshift if invert is False and ifftshift otherwise
    """
    if invert:
        mid = n - (n + 1) // 2
    else:
        mid = (n + 1) // 2
    if axis == 1:
        start = [0, 0, 0, mid]
        end = [-1, -1, -1, mid]
    else:
        start = [0, 0, mid, 0]
        end = [-1, -1, mid, -1]
    out = tf.concat([tf.slice(matrix, start, [-1, -1, -1, -1]),
                     tf.slice(matrix, [0, 0, 0, 0], end)], axis + 2)
    return out


def tf_fftshift(matrix, n):
    """Performs similar function to numpy's fftshift
    Note: Takes image as a channel first numpy array of shape:
        (batch_size, channels, height, width)
    """
    mat = _tfshift(matrix, n, 1)
    mat2 = _tfshift(mat, n, 0)
    return mat2


def tf_ifftshift(matrix, n):
    """Performs similar function to numpy's ifftshift
    Note: Takes image as a channel first numpy array of shape:
        (batch_size, channels, height, width)
    """
    mat = _tfshift(matrix, n, 1, invert=True)
    mat2 = _tfshift(mat, n, 0, invert=True)
    return mat2


def spectral_pool(image, pool_size=4):
    """ Perform a single spectral pool operation.
    Args:
        image: numpy array representing an image
            shape: (num_images, channel, height, width)
        pool_size: number of dimensions to throw away in each dimension,
                   same as the filter size of max_pool
    Returns:
        An image of shape (n, n, 1) if grayscale is True or same as input
    """
    tf.reset_default_graph()
    im = tf.placeholder(shape=image.shape, dtype=tf.float32)
    # make channels first
    im_fft = tf.fft2d(tf.cast(im, tf.complex64))
    lowpass = tf.get_variable(name='lowpass',
                              initializer=get_low_pass_filter(
                                    im.get_shape().as_list(),
                                    pool_size))
    im_magnitude = tf.multiply(tf.abs(im_fft), lowpass)
    im_angles = tf.angle(im_fft)
    part1 = tf.complex(real=im_magnitude,
                       imag=tf.zeros_like(im_angles))
    part2 = tf.exp(tf.complex(real=tf.zeros_like(im_magnitude),
                              imag=im_angles))
    im_fft_lowpass = tf.multiply(part1, part2)
    im_transformed = tf.ifft2d(im_fft_lowpass)

    # make channels last and real values:
    im_channel_last = tf.real(tf.transpose(im_transformed, perm=[0, 2, 3, 1]))

    # normalize image:
    channel_max = tf.reduce_max(im_channel_last, axis=(0, 1, 2))
    channel_min = tf.reduce_min(im_channel_last, axis=(0, 1, 2))
    im_scaled = tf.divide(im_channel_last - channel_min,
                          channel_max - channel_min)
    im_out = tf.real(tf.transpose(im_scaled, perm=[0, 3, 1, 2]))

    init = tf.global_variables_initializer()
    with tf.Session() as sess:
        sess.run(init)
        im_ffto, im_new = sess.run([im_fft, im_out],
                           feed_dict={im: image})

    return im_ffto, im_new


def max_pool(image, pool_size=2):
    """ Perform a single max pool operation.
    Args:
        image: numpy array representing an image
            shape: (num_images, channel, height, width)
        pool_size: number of dimensions to throw away in each dimension,
                   same as the filter size of max_pool
    Returns:
        An image of shape (n, n, 1) if grayscale is True or same as input
    """
    imsize = image.shape[-1]

    im_channel_last = np.moveaxis(image, (0, 1), (2, 3))
    im_new = im_channel_last.copy()
    for i in range(0, imsize, pool_size):
        for j in range(0, imsize, pool_size):
            max_val = np.max(im_channel_last[i: i + pool_size,
                                             j: j + pool_size],
                                             axis=(0, 1))
            im_new[i: i + pool_size, j: j + pool_size] = max_val
    im_new = np.moveaxis(im_new, (2, 3), (0, 1))
    return im_new


def l2_loss_images(orig_images, mod_images):
    n = orig_images.shape[0]
    # convert to 2d:
    oimg = orig_images.reshape(n, -1)
    mimg = mod_images.reshape(n, -1)

    # bring to same scale if not scales already
    if oimg.max() > 2:
        oimg = oimg / 255.
    if mimg.max() > 2:
        mimg = mimg / 255.

    error_norm = np.linalg.norm(oimg - mimg, axis=0)
    base_norm = np.linalg.norm(oimg, axis=0)
    return np.mean(error_norm / base_norm)
