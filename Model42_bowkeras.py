#auxiliary package
import platform as plat
from tqdm import tqdm
import numpy as np
import random
import os
import time

#algorithm package
import tensorflow as tf
import keras.backend as k
from keras.layers import *
from keras import optimizers
from keras.regularizers import l2
from keras.activations import softmax
from keras.losses import categorical_crossentropy
from keras.models import Model

#self-made package
from general_func.gen_func import Comapare2
# from debug.readdata_bowelmulti import DataSpeech
from readdata_bowel import DataSpeech
from readdata_bowel import AUDIO_LENGTH, AUDIO_FEATURE_LENGTH, CLASS_NUM
from help_func.FL_keras import focal_loss
from help_func.utilties import plot_confusion_matrix


# The codes reference to the https://github.com/km1414/CNN-models/blob/master/googlenet-lite/googlenet-lite.py

# Inception module - main building block
def inception_model(input, filters_1x1, filters_3x3_reduce, filters_3x3, filters_5x5_reduce, filters_5x5, filters_pool_proj):
    #1*1 convolutions
    conv_1x1 = Conv2D(filters=filters_1x1, kernel_size=(1, 1), padding='same', activation='relu', kernel_regularizer=l2(0.01))(input)
    #3*3 convolutions
    conv_3x3_reduce = Conv2D(filters=filters_3x3_reduce, kernel_size=(1, 1), padding='same', activation='relu', kernel_regularizer=l2(0.01))(input)
    conv_3x3 = Conv2D(filters=filters_3x3, kernel_size=(3, 3), padding='same', activation='relu', kernel_regularizer=l2(0.01))(conv_3x3_reduce)
    #5*5 convolutions
    conv_5x5_reduce  = Conv2D(filters=filters_5x5_reduce, kernel_size=(1, 1), padding='same', activation='relu', kernel_regularizer=l2(0.01))(input)
    conv_5x5 = Conv2D(filters=filters_5x5, kernel_size=(5, 5), padding='same', activation='relu', kernel_regularizer=l2(0.01))(conv_5x5_reduce)
    #1*1 convolutions with maxpooling
    maxpool = MaxPooling2D(pool_size=(3, 3), strides=(1, 1), padding='same')(input)
    maxpool_proj = Conv2D(filters=filters_pool_proj, kernel_size=(1, 1), strides=(1, 1), padding='same', activation='relu', kernel_regularizer=l2(0.01))(maxpool)

    inception_output = concatenate([conv_1x1, conv_3x3, conv_5x5, maxpool_proj], axis=3)  # use tf as backend

    return inception_output



class ModelSpeech():  # 模型类
    def __init__(self, datapath):
        '''
        初始化
        默认输出四类：normal,wheezes,crackles,both
        '''
        self.datapath = datapath
        self.slash = ''
        system_type = plat.system()  # 由于不同的系统的文件路径表示不一样，需要进行判断
        if (system_type == 'Windows'):
            self.slash = '\\'  # 反斜杠
        elif (system_type == 'Linux'):
            self.slash = '/'  # 正斜杠
        else:
            print('*[Message] Unknown System\n')
            self.slash = '/'  # 正斜杠
        if (self.slash != self.datapath[-1]):  # 在目录路径末尾增加斜杠
            self.datapath = self.datapath + self.slash

        # self.model = self.CreateInceptionModel(input_shape=(AUDIO_LENGTH, AUDIO_FEATURE_LENGTH, 1), classes=CLASS_NUM)
        # self.model = self.CreateLSTMModel(input_shape=(AUDIO_LENGTH, AUDIO_FEATURE_LENGTH, 1), classes=CLASS_NUM)
        self.model = self.CreateClassicModel(input_shape=(AUDIO_LENGTH, AUDIO_FEATURE_LENGTH, 1), classes=CLASS_NUM)
        self.metrics = {'type': 'eval', 'sensitivity': 0, 'specificity': 0, 'score': 0, 'accuracy': 0, 'epoch': 0}

    def CreateClassicModel(self,input_shape, classes):

        X_input = Input(name='the_input', shape=input_shape)

        layer_h1 = Conv2D(32, (3, 3), use_bias=True, activation='relu', padding='same', kernel_initializer='he_normal')(X_input)  # 卷积层
        # layer_h1 = Dropout(0.1)(layer_h1)
        layer_h2 = Conv2D(32, (3, 3), use_bias=True, activation='relu', padding='same', kernel_initializer='he_normal')(layer_h1)  # 卷积层
        layer_h3 = MaxPooling2D(pool_size=2, strides=None, padding="valid")(layer_h2)  # 池化层

        # layer_h3 = Dropout(0.1)(layer_h3)
        layer_h4 = Conv2D(64, (3, 3), use_bias=True, activation='relu', padding='same', kernel_initializer='he_normal')(layer_h3)  # 卷积层
        # layer_h4 = Dropout(0.2)(layer_h4)
        layer_h5 = Conv2D(64, (3, 3), use_bias=True, activation='relu', padding='same', kernel_initializer='he_normal')(layer_h4)  # 卷积层
        layer_h6 = MaxPooling2D(pool_size=2, strides=None, padding="valid")(layer_h5)  # 池化层

        # layer_h6 = Dropout(0.2)(layer_h6)
        layer_h7 = Conv2D(128, (3, 3), use_bias=True, activation='relu', padding='same',kernel_initializer='he_normal')(layer_h6)  # 卷积层
        # layer_h7 = Dropout(0.2)(layer_h7)
        layer_h8 = Conv2D(128, (3, 3), use_bias=True, activation='relu', padding='same',kernel_initializer='he_normal')(layer_h7)  # 卷积层
        layer_h9 = MaxPooling2D(pool_size=2, strides=None, padding="valid")(layer_h8)  # 池化层

        # layer_h9 = Dropout(0.3)(layer_h9)
        layer_h10 = Conv2D(128, (3, 3), use_bias=True, activation='relu', padding='same',kernel_initializer='he_normal')(layer_h9)  # 卷积层
        # layer_h10 = Dropout(0.4)(layer_h10)
        layer_h11 = Conv2D(128, (3, 3), use_bias=True, activation='relu', padding='same',kernel_initializer='he_normal')(layer_h10)  # 卷积层

        flayer = Flatten()(layer_h11)
        # flayer = Dropout(0.4)(flayer)
        fc1 = Dense(units=128, activation = "relu", use_bias = True, kernel_initializer = 'he_normal')(flayer)
        # fc1 = Dropout(0.5)(fc1)
        fc2 = Dense(classes, use_bias=True, kernel_initializer='he_normal')(fc1)  # 全连接层
        y_pred = Activation('softmax', name='Activation0')(fc2)

        model = Model(inputs=X_input, outputs=y_pred)
        optimizer = optimizers.Adadelta()
        # model.compile(optimizer=optimizer, loss='binary_crossentropy')# [focal_loss])
        model.compile(optimizer=optimizer, loss=[focal_loss(alpha=0.25, gamma=2)])
        return model

    def CreateLSTMModel(self,input_shape, classes):
        X_input = Input(name='the_input',shape=input_shape)
        y = Reshape((197, 200),name='squeeze')(X_input)
        y = LSTM(128, return_sequences=False)(y) #computation complexity
        y = Dense(classes, activation='softmax')(y)

        model = Model(inputs=X_input, outputs=y)
        optimizer = optimizers.Adadelta()
        model.compile(optimizer=optimizer, loss='binary_crossentropy')
        return model


    #inception module
    def CreateInceptionModel(self,input_shape, classes):

        # Define the input layer
        X_input = Input(name='the_input',shape=input_shape)

        # Stage 1 - layers before inception modules
        conv1_7x7_s2 = Conv2D(filters=64, kernel_size=(7, 7), strides=(2, 2), padding='same', activation='relu', kernel_regularizer=l2(0.01))(X_input)
        maxpool1_3x3_s2 = MaxPooling2D(pool_size=(3, 3), strides=(2, 2), padding='same')(conv1_7x7_s2)
        conv2_3x3_reduce = Conv2D(filters=64, kernel_size=(1, 1), padding='same', activation='relu', kernel_regularizer=l2(0.01))(maxpool1_3x3_s2)
        conv2_3x3 = Conv2D(filters=192, kernel_size=(3, 3), padding='same', activation='relu', kernel_regularizer=l2(0.01))(conv2_3x3_reduce)
        maxpool2_3x3_s2 = MaxPooling2D(pool_size=(3, 3), strides=(2, 2), padding='same')(conv2_3x3)

        # Stage 2 - 2 inception modules and max pooling
        inception_3a = inception_model(input=maxpool2_3x3_s2, filters_1x1=64, filters_3x3_reduce=96, filters_3x3=128,filters_5x5_reduce=16, filters_5x5=32, filters_pool_proj=32)
        inception_3b = inception_model(input=inception_3a, filters_1x1=128, filters_3x3_reduce=128, filters_3x3=192, filters_5x5_reduce=32, filters_5x5=96, filters_pool_proj=64) #224*25*480

        # Stage 3 - another type of ending layers.
        # drop1 = Dropout(rate=0.4)(inception_3b)
        # transmute = core.Flatten()(drop1)
        # linear = Dense(units=classes, activation='softmax', kernel_regularizer=l2(0.01))(transmute)
        # last = linear

        # Stage 3 - ending layers
        conv_1x1 = Conv2D(filters=classes, kernel_size=(1, 1), padding='same', activation='relu',kernel_regularizer=l2(0.01))(inception_3b)
        last = GlobalAveragePooling2D()(conv_1x1)
        last = Activation(softmax)(last)

        # Create model
        model = Model(inputs=X_input, outputs=last)
        optimizer = optimizers.Adadelta()
        model.compile(optimizer=optimizer,loss =[focal_loss])
        # model.compile(optimizer=optimizer,loss=categorical_crossentropy)

        return model

    def TrainModel(self, datapath, epoch=2, batch_size=32, load_model=False, filename='model_set/speech_model25'):
        #1. info checking..
        assert (batch_size % 2 == 0)
        data = DataSpeech(datapath, 'train')
        num_data = sum(data.DataNum)  # 获取数据的数量

        os.system('pkill tensorboard')
        os.system('rm -rf ./checkpoints/files_summary/* ')
        train_writter = tf.summary.FileWriter(os.path.join(os.getcwd(), 'checkpoints', 'files_summary'))
        os.system('tensorboard --logdir=/home/zhaok14/example/PycharmProjects/setsail/individual_spp/checkpoints/files_summary/ &')
        print('\n')
        print(90 * '*')
        print(90 * '*')

        iterations_per_epoch = min(data.DataNum) // (batch_size // CLASS_NUM) + 1
        # iterations_per_epoch = 2
        print('trainer info:')
        print('training data size: %d' % num_data)
        print('increased epoches: ', epoch)
        print('minibatch size: %d' % batch_size)
        print('iterations per epoch: %d' % iterations_per_epoch)

        with k.get_session() as sess:
            train_writter.add_graph(sess.graph)

            saver = tf.train.Saver(max_to_keep=1)
            if load_model == True:
                try:
                    saver.restore(sess, os.path.join(os.getcwd(), 'checkpoints', 'files_model','speech-f' + str(0) + '.module'))  # two files in a folder.
                except:
                    print('Loading weights failed. Train from scratch.')
            sess.run(tf.global_variables_initializer())

            best_score = 0
            for i in range(0, epoch):
                iteration = 0
                yielddatas = data.data_genetator(batch_size,epoch)
                pbar = tqdm(yielddatas)
                for input, labels in pbar:
                    loss = self.model.train_on_batch(input[0],labels)
                    train_summary = tf.Summary()
                    train_summary.value.add(tag='loss', simple_value=loss)
                    train_writter.add_summary(train_summary, iteration + i * iterations_per_epoch)
                    pr = 'epoch:%d/%d,iteration: %d/%d ,loss: %s' % (epoch, i, iterations_per_epoch, iteration, loss)
                    pbar.set_description(pr)
                    if iteration == iterations_per_epoch:
                        break
                    else:
                        iteration += 1
                pbar.close()
                if i % 1 == 0:
                    self.TestModel(sess=sess, datapath=self.datapath, str_dataset='train', data_count=1000, out_report=False, writer=train_writter, step=i)
                    metrics = self.TestModel(sess=sess, datapath=self.datapath, str_dataset='eval', data_count=-1, out_report=False, writer=train_writter, step=i)
                    if (metrics['score'] > best_score and i > 0):
                        self.metrics = metrics
                        self.metrics['epoch'] = i
                        best_score = metrics['score']
                        saver.save(sess, os.path.join(os.getcwd(), 'checkpoints', 'files_model','speech-f' + str(0) + '.module'), global_step=i)

        print('The best metrics took place in the epoch: ', self.metrics['epoch'])
        print('Sensitivity: {}; Specificity: {}; Score: {}; Accuracy: {}'.format(self.metrics['sensitivity'],self.metrics['specificity'],self.metrics['score'],self.metrics['accuracy']))

    def TestModel(self, sess, writer, datapath='', str_dataset='eval', data_count=32, out_report=False, show_ratio=True, step=0):
        '''
        测试检验模型效果
        '''
        data = DataSpeech(self.datapath, str_dataset)
        # data.LoadDataList(str_dataset)
        num_data = sum(data.DataNum)  # 获取数据的数量
        if (data_count <= 0 or data_count > num_data):  # 当data_count为小于等于0或者大于测试数据量的值时，则使用全部数据来测试
            data_count = num_data

        try:
            ran_num = random.randint(0, num_data - 1)  # 获取一个随机数
            overall_p = 0
            overall_n = 0
            overall_tp = 0
            overall_tn = 0
            accuracy = 0
            sensitivity = 0
            specificity = 0
            score = 0

            nowtime = time.strftime('%Y%m%d_%H%M%S', time.localtime(time.time()))
            txt_obj = []
            if (out_report == True):
                txt_obj = open('Test_Report_' + str_dataset + '_' + nowtime + '.txt', 'w', encoding='UTF-8')  # 打开文件并读入

            start = time.time()
            cm_pre = []
            cm_lab = []
            map = {0: 'normal', 1: 'bowel sounds'}
            # data_count = 200
            for i in tqdm(range(data_count)):
                data_input, data_labels = data.GetData((ran_num + i) % num_data, mode='non-repetitive')  # 从随机数开始连续向后取一定数量数据

                predictions = []
                if len(data_input) <= AUDIO_LENGTH:
                    data_in = np.zeros((1, AUDIO_LENGTH, AUDIO_FEATURE_LENGTH, 1), dtype=np.float)
                    data_in[0, 0:len(data_input)] = data_input
                    data_pre = self.model.predict_on_batch(data_in)
                    predictions = np.argmax(data_pre[0], axis=0)
                else:
                    assert(0)

                # print('predictions:',predictions)
                # print('data_pre:',np.argmax(data_pre[0], axis=0))
                # print ('data_label:',data_labels[0])

                cm_pre.append(map[predictions])
                cm_lab.append(map[data_labels[0]])

                tp, fp, tn, fn = Comapare2(predictions, data_labels[0])  # 计算metrics
                overall_p += tp + fn
                overall_n += tn + fp
                overall_tp += tp
                overall_tn += tn

                txt = ''
                if (out_report == True):
                    txt += str(i) + '\n'
                    txt += 'True:\t' + str(data_labels) + '\n'
                    txt += 'Pred:\t' + str(data_pre) + '\n'
                    txt += '\n'
                    txt_obj.write(txt)

            if overall_p != 0:
                sensitivity = overall_tp / overall_p * 100
                sensitivity = round(sensitivity, 2)
            else:
                sensitivity = 'None'
            if overall_n != 0:
                specificity = overall_tn / overall_n * 100
                specificity = round(specificity, 2)
            else:
                specificity = 'None'
            if sensitivity != 'None' and specificity != 'None':
                score = (sensitivity + specificity) / 2
                score = round(score, 2)
            else:
                score = 'None'
            accuracy = (overall_tp + overall_tn) / (overall_p + overall_n) * 100
            accuracy = round(accuracy, 2)
            end = time.time()
            dtime = round(end - start, 2)
            # print('*[测试结果] 片段识别 ' + str_dataset + ' 敏感度：', sensitivity, '%, 特异度： ', specificity, '%, 得分： ', score, ', 准确度： ', accuracy, '%, 用时: ', dtime, 's.')
            strg = '*[测试结果] 片段识别 {0} 敏感度：{1}%, 特异度： {2}%, 得分： {3}, 准确度： {4}%, 用时: {5}s.'.format(str_dataset,
                                                                                                sensitivity,
                                                                                                specificity, score,
                                                                                                accuracy, dtime)
            tqdm.write(strg)

            assert (len(cm_lab) == len(cm_pre))
            img_cm = plot_confusion_matrix(cm_lab, cm_pre, list(map.values()),tensor_name='MyFigure/cm', normalize=False)
            writer.add_summary(img_cm, global_step=step)
            summary = tf.Summary()
            summary.value.add(tag=str_dataset + '/sensitivity', simple_value=sensitivity)
            summary.value.add(tag=str_dataset + '/specificity', simple_value=specificity)
            summary.value.add(tag=str_dataset + '/score', simple_value=score)
            summary.value.add(tag=str_dataset + '/accuracy', simple_value=accuracy)
            writer.add_summary(summary, global_step=step)

            if (out_report == True):
                txt = '*[测试结果] 片段识别 ' + str_dataset + ' 敏感度：' + sensitivity + '%, 特异度： ' + specificity + '%, 得分： ' + score + ', 准确度： ' + accuracy + '%, 用时: ' + dtime + 's.'
                txt_obj.write(txt)
                txt_obj.close()

            metrics = {'data_set': str_dataset, 'sensitivity': sensitivity, 'specificity': specificity, 'score': score,
                       'accuracy': accuracy}

            return metrics

        except StopIteration:
            print('[Error] Model Test Error. please check data format.')
