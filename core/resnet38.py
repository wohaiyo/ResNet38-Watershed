#from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import numpy as np

import nn
import sys
import os
sys.path.append("..")
import data_utils as dt

class ResNet38:
    def __init__(self, params):

        ## use pre-trained A1 model on Cityscapes unless specified
        weight_path = params.get('feed_weight', '../data/trained_weights/pretrained_ResNet38a1_imgnet.npy')
        self._weight_dict = dt.load_weight(weight_path)
        self._var_dict = {}

        self._num_classes = params.get('num_classes', 19)

    def _build_model(self, image, sem_gt, is_train=False):
        '''If is_train, save weight to self._var_dict,
           otherwise, don't save weights
           image: [1, H, W, 3]
           sem_gt: [1, H/8, W/8]'''
        model = {}
        feed_dict = self._weight_dict
        if is_train:
            var_dict = self._var_dict
        else:
            var_dict = None

        if is_train:
            dropout = True
        else:
            dropout = False

        shape_dict = {}
        shape_dict['B0'] = [3,3,3,64]

        # The sharable conv features: 36 conv layers
        with tf.variable_scope('shared'):
            # B0: [H,W,3] -> [H,W,64]
            with tf.variable_scope('B0'):
                model['B0'] = nn.conv_layer(image, feed_dict, 1, 'SAME',
                                            shape_dict['B0'], var_dict)

            # B2_1: [H,W,64] -> [H/2, W/2, 128]
            shape_dict['B2'] = {}
            shape_dict['B2']['side'] = [1,1,64,128]
            shape_dict['B2']['convs'] = [[3,3,64,128],[3,3,128,128]]
            with tf.variable_scope('B2_1'):
                model['B2_1'] = nn.ResUnit_downsample_2convs(model['B0'],
                                                             feed_dict,
                                                             shape_dict['B2'],
                                                             var_dict=var_dict)
            # B2_2, B2_3: [H/2, W/2, 128]
            for i in range(2):
                with tf.variable_scope('B2_'+str(i+2)):
                    model['B2_'+str(i+2)] = nn.ResUnit_2convs(model['B2_'+str(i+1)], feed_dict,
                                                              shape_dict['B2']['convs'][1],
                                                              var_dict=var_dict)

            # B3_1: [H/2, W/2, 128] -> [H/4, W/4, 256]
            shape_dict['B3'] = {}
            shape_dict['B3']['side'] = [1,1,128,256]
            shape_dict['B3']['convs'] = [[3,3,128,256],[3,3,256,256]]
            with tf.variable_scope('B3_1'):
                model['B3_1'] = nn.ResUnit_downsample_2convs(model['B2_3'],
                                                             feed_dict,
                                                             shape_dict['B3'],
                                                             var_dict=var_dict)
            # B3_2, B3_3: [H/4, W/4, 256]
            for i in range(2):
                with tf.variable_scope('B3_'+str(i+2)):
                    model['B3_'+str(i+2)] = nn.ResUnit_2convs(model['B3_'+str(i+1)], feed_dict,
                                                              shape_dict['B3']['convs'][1],
                                                              var_dict=var_dict)
            # B4_1: [H/4, W/4, 256] -> [H/8, W/8, 512]
            shape_dict['B4'] = {}
            shape_dict['B4']['side'] = [1,1,256,512]
            shape_dict['B4']['convs'] = [[3,3,256,512],[3,3,512,512]]
            with tf.variable_scope('B4_1'):
                model['B4_1'] = nn.ResUnit_downsample_2convs(model['B3_3'],
                                                                 feed_dict,
                                                                 shape_dict['B4'],
                                                                 var_dict=var_dict)
            # B4_2 ~ B4_6: [H/8, W/8, 512]
            for i in range(5):
                with tf.variable_scope('B4_'+str(i+2)):
                    model['B4_'+str(i+2)] = nn.ResUnit_2convs(model['B4_'+str(i+1)],
                                                                   feed_dict,
                                                                   shape_dict['B4']['convs'][1],
                                                                   var_dict=var_dict)
            # B5_1: [H/8, W/8, 512] -> [H/8, W/8, 1024]
            shape_dict['B5_1'] = {}
            shape_dict['B5_1']['side'] = [1,1,512,1024]
            shape_dict['B5_1']['convs'] = [[3,3,512,512],[3,3,512,1024]]
            with tf.variable_scope('B5_1'):
                model['B5_1'] = nn.ResUnit_hybrid_dilate_2conv(model['B4_6'],
                                                                   feed_dict,
                                                                   shape_dict['B5_1'],
                                                                   var_dict=var_dict)
            # B5_2, B5_3: [H/8, W/8, 1024]
            # Shape for B5_2, B5_3
            shape_dict['B5_2_3'] = [[3,3,1024,512],[3,3,512,1024]]
            for i in range(2):
                with tf.variable_scope('B5_'+str(i+2)):
                    model['B5_'+str(i+2)] = nn.ResUnit_full_dilate_2convs(model['B5_'+str(i+1)],
                                                      feed_dict, shape_dict['B5_2_3'],
                                                      var_dict=var_dict)

            # B6: [H/8, W/8, 1024] -> [H/8, W/8, 2048]
            shape_dict['B6'] = [[1,1,1024,512],[3,3,512,1024],[1,1,1024,2048]]
            with tf.variable_scope('B6'):
                model['B6'] = nn.ResUnit_hybrid_dilate_3conv(model['B5_3'],
                                                                 feed_dict,
                                                                 shape_dict['B6'],
                                                                 dropout=dropout,
                                                                 var_dict=var_dict)
            # B7: [H/8, W/8, 2048] -> [H/8, W/8, 4096]
            shape_dict['B7'] = [[1,1,2048,1024],[3,3,1024,2048],[1,1,2048,4096]]
            with tf.variable_scope('B7'):
                model['B7'] = nn.ResUnit_hybrid_dilate_3conv(model['B6'],
                                                                 feed_dict,
                                                                 shape_dict['B7'],
                                                                 dropout=dropout,
                                                                 var_dict=var_dict)

        # The graddir unique part: conv1 + conv2 + 3*conv3(kernel: [1x1])
        # Gating operation, need semantic GT
        gated_feat = self._gate(sem_gt, model['B7'])

        with tf.variable_scope("graddir"):
            # The normal feature layers
            shape_dict['grad_convs1'] = [[3,3,4096,512],[3,3,512,512]]
            with tf.variable_scope('convs'):
                model['grad_convs1'] = nn.grad_convs(gated_feat, feed_dict,
                                                   shape_dict['grad_convs1'], var_dict)
            # The norm layers to normalize the output to have same magnitude as grad GT
            shape_dict['grad_convs2'] = [[1,1,512,256],[1,1,256,256],[1,1,256,2]]
            with tf.variable_scope('norm'):
                model['grad_convs2'] = nn.grad_norm(model['grad_convs1'], feed_fict,
                                                 shape_dict['grad_convs2'], var_dict)
            # Normalize the output to have unit vectors
            model['grad_norm'] = nn.norm(model['grad_convs2'])

        return model

    def _gate(self, sem_input, feat_input):
        ''' This function takes inputs as semantic result and feature maps,
            returns gated feature maps, where non-relevant classes on the
            feature maps are set to zero
            Input: sem_input [1, H, W]
                   feat_input [1, H, W, 4096]
            Output: gated feature maps [1, H, W, 4096]'''

        # TODO: Only gate class car, car label
        sem_bool = tf.equal(sem_out, 13)
        sem_bin = tf.cast(sem_bool, tf.float32)

        gated_feat = tf.multiply(feat_input, sem_bin)

        return gated_feat

    def _upsample(self, input_tensor, new_size):
        ''' Upsampling using Bilinear interpolation
            Input: A tensor [batch_size, H, W, C]
                   new_size: python/numpy array [new_H, new_W]
            Return: upsampled tensor
        '''
        with tf.variable_scope('Bilinear'):
            upsampled = nn.bilinear_upscore_layer(input_tensor, new_size)

        return upsampled

    def _weight_decay(self, decay_rate):
        '''Compute weight decay loss for convolution kernel and fully connected
        weigths, excluding trainable variables of BN layer'''

        l2_losses = []
        for var in tf.trainable_variables():
            if var.op.name.find('kernel') or var.op.name.find('bias'):
                l2_losses.append(tf.nn.l2_loss(var))

        return tf.multiply(decay_rate, tf.add_n(l2_losses))

    def num_parameters(self):
        '''Compute the number of trainable parameters. Note that it MUST be called after the graph is built'''

        return np.sum([np.product([xi.value for xi in x.get_shape()]) for x in tf.trainable_variables()])

        # update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        # with tf.control_dependencies(update_ops):
             # default learning rate for Adam: 0.001
            # train_op = tf.train.AdamOptimizer().minimize(total_loss)

    def train_grad(self, image, sem_gt, label, params):
        '''This function only trains graddir branch.
            Input: image [1, H, W, 3]
                   sem_gt [1, H, W], need to be downsample by 8
                   label [1, H, W, 2], the graddir
                   params: decay_rate, lr
        '''
        # NOTE: train on downsampled results

        ## downsample sem_gt by 8
        sem_shape = tf.shape(sem_gt)
        new_size = [sem_shape[1]/8, sem_shape[2]/8]
        new_size = tf.cast(new_size, tf.int32)
        sem_gt = tf.reshape(sem_gt, [sem_shape[0], sem_shape[1], sem_shape[2], 1])
        sem_gt = tf.image.resize_images(sem_gt, new_size, tf.image.ResizeMethod.NEAREST_NEIGHBOR)
        sem_gt = tf.squeeze(sem_gt, axis=0)

        model = self._build_model(image, sem_gt, is_train=True)
        pred = model['grad_norm']

        ## downsample graddir label by 8
        # remove the first dim
        pred = tf.squeeze(pred)
        label = tf.squeeze(label)
        label = tf.image.resize_images(label, new_size)

        # The predicted graddir and GT are already normalized
        product = tf.reduce_sum(tf.multiply(pred,label), axis=2)
        cos_out = tf.acos(product)
        loss_grad = tf.square(tf.norm(cos_out))
        loss_total = loss_grad + self._weight_decay(params['decay_rate'])

        update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        with tf.control_dependencies(update_ops):
            train_step = tf.train.AdamOptimizer(params['lr']).minimize(loss_total)

        return train_step, loss_total

    def inf(self, image, sem_gt):
        ''' Input: image [1, H, W, C]
                   sem_gt [1, H, W]
            Output: upsampled graddir result [1, 1024, 2048, 2]'''

        model = self._build_model(image, sem_gt, is_train=False)
        pred = model['grad_norm']
        pred = self._upsample(pred, [1024,2048])

        return pred


