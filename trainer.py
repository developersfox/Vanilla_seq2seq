# import os
import res
import time
import utils
import torch
import random
import numpy as np

import Vanilla

from torch                     \
    import Tensor
from torch.multiprocessing       \
    import Pool
thisPool = Pool

from Vanilla                          \
    import update_model_rmsprop        \
    as optimize_model


    # layer struct

layer_sizes = [3,5,4] # [5, 8, 7] # [8, 12, 10] # [2, 4, 5] # [3, 5, 4]

    # basic params

epochs = 20
learning_rate = 0.001

batch_size = 400 ; data_size = batch_size * 2
data_path = 'samples.pkl'

train_basic = True

    # advanced params

rms_alpha = 0.9

rmsadv_alpha_moment = 0.2
rmsadv_beta_moment = 0.8
rmsadv_alpha_accugrad = 0.9

adam_alpha_moment = 0.9
adam_alpha_accugrad = 0.999

drop_in = 0.0
drop_mid = 0.0
drop_out = 0.0

loss_fn = Vanilla.custom_distance
cube_distance = False
# Vanilla.custom_entropy

    # details

write_loss_to_txt = False


    # # #


def train_rms(model, accu_grads, data, num_epochs=1, display_details=False):

    num_samples = len(data)
    num_batches = int(num_samples / batch_size)
    num_workers = torch.multiprocessing.cpu_count()

    def batchify(data):
        return [data[_ * batch_size : (_+1) * batch_size] for _ in range(num_batches)]

    if display_details:
        print('\n'
              f'\/ Training Started : Rms \/\n'
              f'Sample Amount: {num_samples}\n'
              f'Batch Size: {batch_size}\n'
              f'Workers: {num_workers}\n'
              f'Learning Rate: {learning_rate}\n'
              f'Epochs: {num_epochs}\n')

    losses = []

    for epoch in range(num_epochs):

        start_t = time.time()

        epoch_loss = np.zeros(Vanilla.hm_outs)

        random.shuffle(data)

        for batch in batchify(data):

            # create batch

            batch_loss = np.zeros_like(epoch_loss)

            with thisPool(num_workers) as pool:

                # create procs

                results = pool.map_async(process_fn, [[model.copy(), batch[_]] for _ in range(batch_size)])

                pool.close()

                # retrieve procs

                pool.join()

                for result in results.get():
                    loss, grads = result

                    Vanilla.apply_grads(model,grads)
                    batch_loss += loss

                # handle

                epoch_loss += batch_loss

            # Vanilla.disp_grads(model)

            optimize_model(model, accu_grads, batch_size=batch_size, lr=learning_rate, alpha=rms_alpha)

            # Vanilla.disp_params(model)

        losses.append(epoch_loss)

        print('Loss: ',epoch_loss)

        # res.save_model(model, epoch, asText=True)

    return model, accu_grads, losses


def process_fn(fn_input):

    model, data = fn_input
    x_vocab, x_oct, x_dur, x_vol, y_vocab, y_oct, y_dur, y_vol = data
    generative_length = len(y_vocab)

    inp, trg = [], []

    # for _ in range(len(x_vocab)):     # multi I/O form
    #     vect = []
    #     [vect.extend(e) for e in [x_vocab[_], x_oct[_], x_dur[_], x_vol[_]]]
    #     inp.append(Tensor(vect))
    #
    # for _ in range(len(y_vocab)):
    #     vect = []
    #     [vect.extend(e) for e in [y_vocab[_], y_oct[_], y_dur[_], y_vol[_]]]
    #     trg.append(Tensor(vect))

    inp = Tensor([x_vocab, x_oct, x_dur, x_vol])

    # modified
    trg = []
    for _ in range(len(y_vocab)):
        trg.append([Tensor(e) for e in [y_vocab[_], y_oct[_], y_dur[_], y_vol[_]]])

    response = Vanilla.forward_prop(model, inp, gen_iterations=generative_length)

    # resp0, resp1, resp2, resp3 = [], [], [], []
    # for resp_t in response:
    #     resp0.append(resp_t[0])    # response[:,0]
    #     resp1.append(resp_t[1])    # response[:,1]
    #     resp2.append(resp_t[2])    # response[:,2]
    #     resp3.append(resp_t[3])    # response[:,3]

    loss_nodes = loss_fn(response, trg)

    Vanilla.update_gradients(loss_nodes)

    loss_len = len(loss_nodes)
    loss = [float(sum(e)) for e in [loss_nodes[:int(loss_len/4)],
                                    loss_nodes[int(loss_len/4) : int(loss_len/2)],
                                    loss_nodes[int(loss_len/2) : 3*int(loss_len/4)],
                                    loss_nodes[int(3*loss_len/4):]]]

    grads = Vanilla.return_grads(model)

    return loss, grads



    #   Dev Purposes   #



def floyd_out(str):
    with open('/output/progress.txt', 'a+') as f:
        f.write(str)

def floyd_out_params(weights):
    names, params = weights
    with open('/output/param_data.txt', 'a+') as f:
        for i in range(len(params)):
            name = names[i]
            param = params[i]
            f.write(str(name) + ' ' + str(param) + ' ' + '\n')


def init_accugrads(model):
    accu_grads = []
    for layer in model:
        layer_accus = []
        for _ in layer.keys():
            layer_accus.append(0)
        accu_grads.append(layer_accus)
    return accu_grads

def save_accugrads(accu_grads, model_id=None):
    model_id = '' if model_id is None else str(model_id)
    res.pickle_save(accu_grads, 'model' + model_id + '_accugrads.pkl')

def load_accugrads(model, model_id=None):
    model_id = '' if model_id is None else str(model_id)
    try:
        accu_grads = res.pickle_load('model' + model_id + '_accugrads.pkl')
        print('> accugrads.pkl loaded.')
    except:
        print('> accugrads.pkl not found.')
        accu_grads = init_accugrads(model)
    return accu_grads


def init_moments(model):
    moments = []
    for layer in model:
        layer_moments = []
        for _ in layer.keys():
            layer_moments.append(0)
        moments.append(layer_moments)
    return moments

def save_moments(moments, model_id=None):
    model_id = '' if model_id is None else str(model_id)
    res.pickle_save(moments, 'model' + model_id + '_moments.pkl')

def load_moments(model, model_id=None):
    model_id = '' if model_id is None else str(model_id)
    try:
        moments = res.pickle_load('model' + model_id + '_moments.pkl')
        print('> moments.pkl loaded.')
    except:
        print('> moments.pkl not found.')
        moments = init_moments(model)
    return moments



    #   Alternative Trainers     #



def train_rmsadv(model, accu_grads, moments, data, epoch_nr=None, num_epochs=1, display_details=False):

    num_samples = len(data)
    num_batches = int(num_samples / batch_size)
    num_workers = torch.multiprocessing.cpu_count()

    if display_details:
        print('\n'
              f'\/ Training Started : Rms_adv \/\n'
              f'Sample Amount: {num_samples}\n'
              f'Batch Size: {batch_size}\n'
              f'Workers: {num_workers}\n'
              f'Learning Rate: {learning_rate}\n'
              f'Epochs: {num_epochs}\n')

    losses = []

    for epoch in range(epochs):

        start_t = time.time()

        epoch_loss = np.zeros(Vanilla.hm_outs)

        random.shuffle(data)

        for batch in range(num_batches):

            # create batch

            batch_loss = np.zeros_like(epoch_loss)

            batch_ptr = batch * batch_size
            batch_end_ptr = (batch+1) * batch_size
            batch = np.array(data[batch_ptr:batch_end_ptr])

            # proto = model.copy()
            # utils.nesterov_step1(proto, moments) # send proto to map_async

            with thisPool(num_workers) as pool:

                # create procs

                results = pool.map_async(process_fn_alt, [[model.copy(), batch[_]] for _ in range(batch_size)])

                pool.close()

                # retrieve procs

                pool.join()

                for result in results.get():
                    loss, grads = result

                    Vanilla.apply_grads(model,grads)
                    batch_loss -= loss

                # handle

                epoch_loss += batch_loss

            utils.nesterov_step2_adaptive(model, accu_grads, moments, batch_size=batch_size, lr=learning_rate, alpha_moments=rmsadv_alpha_moment, beta_moments=rmsadv_beta_moment, alpha_accugrads=rmsadv_alpha_accugrad)

        losses.append(epoch_loss)

        if display_details:
            if write_loss_to_txt: res.write_loss(epoch_loss, as_txt=True, epoch_nr=epoch)
            else: res.write_loss(epoch_loss)
            end_t = time.time() ; end_clock = time.asctime(time.localtime(end_t)).split(' ')[3]
            print(f'@ {end_clock} : epoch {epoch+1} / {num_epochs} completed. PET: {round((end_t - start_t),0)}')

    return model, accu_grads, moments, losses


def train_adam(model, accu_grads, moments, data, epoch_nr=None, num_epochs=1, display_details=False):

    num_samples = len(data)
    num_batches = int(num_samples / batch_size)
    num_workers = torch.multiprocessing.cpu_count()

    if display_details:
        print('\n'
              f'\/ Training Started : Adam \/\n'
              f'Sample Amount: {num_samples}\n'
              f'Batch Size: {batch_size}\n'
              f'Workers: {num_workers}\n'
              f'Learning Rate: {learning_rate}\n'
              f'Epochs: {num_epochs}\n')

    losses = []

    for epoch in range(epochs):

        start_t = time.time()

        epoch_loss = np.zeros(Vanilla.hm_outs)

        random.shuffle(data)

        for batch in range(num_batches):

            # create batch

            batch_loss = np.zeros_like(epoch_loss)

            batch_ptr = batch * batch_size
            batch_end_ptr = (batch+1) * batch_size
            batch = np.array(data[batch_ptr:batch_end_ptr])

            with thisPool(num_workers) as pool:

                # create procs

                results = pool.map_async(process_fn_alt, [[model.copy(), batch[_]] for _ in range(batch_size)])

                pool.close()

                # retrieve procs

                pool.join()

                for result in results.get():
                    loss, grads = result

                    Vanilla.apply_grads(model,grads)
                    batch_loss -= loss

                # handle

                epoch_loss += batch_loss

            if epoch_nr is None: epoch_nr = epoch
            utils.update_model_adam(model, accu_grads, moments, epoch_nr, batch_size=batch_size, lr=learning_rate, alpha_moments=adam_alpha_moment, alpha_accugrads=adam_alpha_accugrad)

        losses.append(epoch_loss)

        if display_details:
            if write_loss_to_txt: res.write_loss(epoch_loss, as_txt=True, epoch_nr=epoch)
            else: res.write_loss(epoch_loss)
            end_t = time.time() ; end_clock = time.asctime(time.localtime(end_t)).split(' ')[3]
            print(f'@ {end_clock} : epoch {epoch+1} / {num_epochs} completed. PET: {round((end_t - start_t),0)}')

    return model, accu_grads, moments, losses



def process_fn_alt(fn_input):

    model, data = fn_input
    x_vocab, x_oct, x_dur, x_vol, y_vocab, y_oct, y_dur, y_vol = data
    generative_length = len(y_vocab)

    inp, trg = [], []

    for _ in range(len(x_vocab)):
        vect = []
        [vect.extend(e) for e in [x_vocab[_], x_oct[_], x_dur[_], x_vol[_]]]
        inp.append(Tensor(vect))

    for _ in range(len(y_vocab)):
        vect = []
        [vect.extend(e) for e in [y_vocab[_], y_oct[_], y_dur[_], y_vol[_]]]
        trg.append(Tensor(vect))

    response = utils.forward_prop_train(model, inp, gen_iterations=generative_length, drop_in=drop_in, drop_mid=drop_mid, drop_out=drop_out)

    resp0, resp1, resp2, resp3 = [], [], [], []
    for resp_t in response:
        resp0.append(resp_t[0])    # response[:,0]
        resp1.append(resp_t[1])    # response[:,1]
        resp2.append(resp_t[2])    # response[:,2]
        resp3.append(resp_t[3])    # response[:,3]

    loss_nodes = loss_fn(response, trg, cube=cube_distance)

    Vanilla.update_gradients(loss_nodes)

    loss_len = len(loss_nodes)
    loss = [float(sum(e)) for e in [loss_nodes[:int(loss_len/4)],
                                    loss_nodes[int(loss_len/4): int(loss_len/2)],
                                    loss_nodes[int(loss_len/2): 3 * int(loss_len/4)],
                                    loss_nodes[int(3*loss_len/4):]]]

    grads = Vanilla.return_grads(model)

    return loss, grads


if __name__ == '__main__':

    torch.set_default_tensor_type('torch.FloatTensor')

    data = res.load_data(data_path,data_size)
    IOdims = res.vocab_size

    if write_loss_to_txt:
        res.initialize_loss_txt()

    # here is a sample datapoint (X & Y)..
    print('X:')
    for thing in data[0][0:4]: print(thing)
    print('Y:')
    for thing in data[0][4:]: print(thing)

    if train_basic:

        # RMS basic training

        model = res.load_model()
        if model is None: model = Vanilla.create_model(IOdims,layer_sizes,IOdims)

        accu_grads = load_accugrads(model)

        model, accu_grads, losses = train_rms(
            model,
            accu_grads,
            data,
            num_epochs=epochs,
            display_details=True)

        res.save_model(model)
        save_accugrads(accu_grads)

    else:

        # RMS advanced / ADAM training

        model = res.load_model()
        if model is None: model = Vanilla.create_model(IOdims, layer_sizes, IOdims)

        accu_grads = load_accugrads(model)
        moments = load_moments(model)

        model, accu_grads, moments, losses = train_adam(
            model,
            accu_grads,
            moments,
            data,
            num_epochs=epochs,
            display_details=True)

        res.save_model(model)
        save_accugrads(accu_grads)
        save_moments(moments)
