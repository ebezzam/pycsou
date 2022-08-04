import numpy as np
import pytest

import pycsou.abc as pyca
import pycsou.runtime as pycrt
import pycsou.util as pycu
import pycsou.util.ptype as pyct
import pycsou_tests.operator.conftest as conftest


class L1Norm(pyca.ProxFunc):
    # f: \bR^{M} -> \bR
    #      x     -> \norm{x}{1}
    def __init__(self, M: int = None):
        super().__init__(shape=(1, M))
        if M is None:
            self._lipschitz = np.inf
        else:
            self._lipschitz = np.sqrt(M)

    @pycrt.enforce_precision(i="arr")
    def apply(self, arr):
        xp = pycu.get_array_module(arr)
        y = xp.linalg.norm(arr, ord=1, axis=-1, keepdims=True).astype(arr.dtype)
        return y

    @pycrt.enforce_precision(i=("arr", "tau"))
    def prox(self, arr, tau):
        xp = pycu.get_array_module(arr)
        y = xp.fmax(0, xp.fabs(arr) - tau) * xp.sign(arr)
        return y


class TestL1Norm(conftest.ProxFuncT):
    @pytest.fixture(params=[None, 5])
    def dim(self, request) -> int:
        return request.param

    @pytest.fixture
    def op(self, dim):
        return L1Norm(M=dim)

    @pytest.fixture
    def data_shape(self, op, dim):
        return (1, dim)

    @pytest.fixture(
        params=[  # 2 evaluation points
            dict(
                in_=dict(arr=np.zeros((5,))),
                out=np.zeros((1,)),
            ),
            dict(
                in_=dict(arr=np.arange(-3, 2)),
                out=np.array([7]),
            ),
        ]
    )
    def data_apply(self, request):
        return request.param

    @pytest.fixture(
        params=[  # 2 evaluation points
            dict(
                in_=dict(
                    arr=np.zeros((5,)),
                    tau=1,
                ),
                out=np.zeros((5,)),
            ),
            dict(
                in_=dict(
                    arr=np.arange(-3, 2),
                    tau=1,
                ),
                out=np.array([-2, -1, 0, 0, 0]),
            ),
        ]
    )
    def data_prox(self, request):
        return request.param

    @pytest.fixture
    def data_math_lipschitz(self, dim):
        N_test, dim = 5, self._sanitize(dim, 3)
        return self._random_array((N_test, dim))


class TestL1NormMoreau(conftest.DiffFuncT):
    @pytest.fixture(params=[4, None])
    def dim(self, request):
        return request.param

    @pytest.fixture
    def mu(self) -> int:
        return 2

    @pytest.fixture
    def op_orig(self, dim):
        return L1Norm(M=dim)

    @pytest.fixture
    def op(self, op_orig, mu):
        return op_orig.moreau_envelope(mu=mu)

    @pytest.fixture
    def data_shape(self, dim):
        return (1, dim)

    @pytest.fixture
    def data_apply(self, op_orig, mu):
        dim = self._sanitize(op_orig.dim, 3)
        x = self._random_array((dim,), seed=7)
        y = op_orig.prox(x, mu)
        z = op_orig.apply(y) + (0.5 / mu) * (np.linalg.norm(y - x) ** 2)
        return dict(
            in_=dict(arr=x),
            out=z,
        )

    @pytest.fixture
    def data_math_lipschitz(self, dim):
        N_test, dim = 6, self._sanitize(dim, 3)
        return self._random_array((N_test, dim), seed=5)

    @pytest.fixture
    def data_math_diff_lipschitz(self, dim):
        N_test, dim = 6, self._sanitize(dim, 3)
        return self._random_array((N_test, dim), seed=6)

    @pytest.fixture
    def data_grad(self, op_orig, mu):
        dim = self._sanitize(op_orig.dim, 3)
        x = self._random_array((dim,), seed=7)
        y = (x - op_orig.prox(x, mu)) / mu
        return dict(
            in_=dict(arr=x),
            out=y,
        )
