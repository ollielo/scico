import pytest

import numpy as np
import os

import jax
from scico import random
from scico import flax as sflax
from scico.flax.train.input_pipeline import prepare_data
from scico.flax.train.train import create_cnst_lr_schedule, create_cosine_lr_schedule, TrainState, compute_metrics

os.environ["XLA_FLAGS"] = "--xla_force_host_platform_device_count=8"

class SetupTest:
    def __init__(self):
        datain = np.arange(80)
        datain_test = np.arange(80, 112)
        dataout = np.zeros(80)
        dataout[:40] = 1
        dataout_test = np.zeros(40)
        dataout_test[:20] = 1

        self.train_ds_simple = {"image": datain, "label": dataout}
        self.test_ds_simple = {"image": datain_test, "label": dataout_test}

        # More complex data structure
        self.N = 128 # Signal size
        self.chn = 1 # Number of channels
        self.bsize = 16 # Batch size
        self.x, key = random.randn((4*self.bsize, self.N, self.N, self.chn), seed=4321)

        xt, key = random.randn((32, self.N, self.N, self.chn), key=key)

        self.train_ds = {"image": self.x, "label": self.x}
        self.test_ds = {"image": xt, "label": xt}

        self.dconf: sflax.ConfigDict = {'seed': 0,
             'depth': 2,
             'num_filters': 16,
             'block_depth': 2,
             'opt_type': 'ADAM',
             'momentum': 0.9,
             'batch_size': 16,
             'num_epochs': 2,
             'base_learning_rate': 1e-3,
             'warmup_epochs': 0,
             'num_train_steps': -1,
             'steps_per_eval': -1,
             'steps_per_epoch': 1,
             'log_every_steps': 1000
            }

@pytest.fixture(scope="module")
def testobj():
    yield SetupTest()

@pytest.mark.parametrize("local_batch", [8, 16, 24])
def test_dstrain(testobj, local_batch):

    key = jax.random.PRNGKey(seed=1234)

    train_iter = sflax.create_input_iter(
        key,
        testobj.train_ds_simple,
        local_batch,
    )

    nproc = jax.device_count()
    ll = []
    num_steps = 40
    for step, batch in zip(range(num_steps), train_iter):
        for j in range(nproc):
            ll.append(batch["image"][j])

    ll_ = np.array(jax.device_get(ll)).flatten()
    ll_ar = np.array(list(set(np.sort(ll_))))

    np.testing.assert_allclose(ll_ar, np.arange(80))


@pytest.mark.parametrize("local_batch", [8, 16, 32])
def test_dstest(testobj, local_batch):

    key = jax.random.PRNGKey(seed=1234)

    train_iter = sflax.create_input_iter(key,
        testobj.test_ds_simple,
        local_batch,
        train=False)

    nproc = jax.device_count()
    ll = []
    num_steps = 20
    for step, batch in zip(range(num_steps), train_iter):
        for j in range(nproc):
            ll.append(batch["image"][j])

    ll_ = np.array(jax.device_get(ll)).flatten()
    ll_ar = np.array(list(set(np.sort(ll_))))

    np.testing.assert_allclose(ll_ar, np.arange(80, 112))


def test_prepare_data(testobj):

    xbtch = prepare_data(testobj.x)
    local_device_count = jax.local_device_count()
    shrdsz = testobj.x.shape[0] // local_device_count
    assert xbtch.shape == (local_device_count, shrdsz, testobj.N, testobj.N, testobj.chn)


def test_train_metrics(testobj):
    xbtch = prepare_data(testobj.x)

    xbtch = xbtch / jax.numpy.sqrt(jax.numpy.var(xbtch, axis=(1,2,3,4)))
    ybtch = xbtch + 1

    p_eval = jax.pmap(compute_metrics, axis_name='batch')
    eval_metrics = p_eval(ybtch, xbtch)
    #mtrcs = p_eval(ybtch, xbtch)
    mtrcs = jax.tree_map(lambda x: x.mean(), eval_metrics)
    assert np.abs(mtrcs['loss']) < 0.51
    assert mtrcs['snr'] < 5e-4


def test_cnst_learning_rate(testobj):
    step = 1
    cnst_sch = create_cnst_lr_schedule(testobj.dconf)
    lr = cnst_sch(step)
    assert lr == testobj.dconf['base_learning_rate']

def test_cos_learning_rate(testobj):
    step = 1
    sch = create_cosine_lr_schedule(testobj.dconf)
    lr = sch(step)
    decay_steps = testobj.dconf['num_epochs'] - testobj.dconf['warmup_epochs']
    cosine_decay = 0.5 * (1 + np.cos(np.pi * step / decay_steps))
    np.testing.assert_allclose(lr, testobj.dconf['base_learning_rate'] * cosine_decay, rtol=1e-06)


@pytest.mark.parametrize("model_cls", [sflax.DnCNNNet, sflax.ResNet, sflax.UNet])
def test_dataset_test_iter(testobj, model_cls):
    depth = testobj.dconf['depth']
    model = model_cls(depth, testobj.chn,
        testobj.dconf['num_filters']
    )
    if isinstance(model, sflax.DnCNNNet):
        depth = 3
        model = sflax.DnCNNNet(depth, testobj.chn,
            testobj.dconf['num_filters']
        )
    try:
        state = sflax.train_and_evaluate(
            testobj.dconf,
            './',
            model,
            testobj.train_ds,
            testobj.test_ds,
        )
    except Exception as e:
        print(e)
        assert 0

